import json as _json
import os
import re

from celery import shared_task
from dotenv import load_dotenv
from logger import get_logger

from config import DATABASE_URL

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logger = get_logger(__name__)

ADVISOR_SYSTEM_PROMPT = """你是竞品雷达产品竞争力评测顾问。你的知识基于五维 Rubric 评测体系：

1. **定位 (Positioning)** — 目标用户和场景是否清晰？README 能否让人快速理解？
2. **差异化 (Differentiation)** — 与竞品相比的独特价值是什么？是结构性差异还是功能堆叠？
3. **护城河 (Moat)** — 防御能力：stars/forks 规模、技术壁垒、大平台复制成本
4. **工程健康度 (Engineering)** — commit 频率、issue 关闭率、CI/CD 成熟度
5. **可持续性 (Sustainability)** — 组织支持、社区活跃度、商业模式

评分标准：0=不合格, 1=基本达标, 2=良好。硬阈值校准规则：
- 护城河：stars<500→0, <5000→1
- 工程：活跃天数<5→0, <15→1；issue 关闭率<30%→0, <70%→1
- 可持续：>12 月未更新→0

你的职责：
- 解读评测结果，解释为什么某个项目在某维度得低分
- 给出具体的、可操作的产品改进建议
- 帮助对比多个项目，分析优劣势
- 如果上下文中有评测数据，必须引用具体数字（如 stars 数、活跃天数等）
- 回答简洁，控制在 400 字以内"""


def _build_advisor_context(evaluations: list[dict], question: str) -> str:
    if not evaluations:
        return question

    parts = ["以下是最近评测的项目数据，请结合这些数据回答用户问题：\n"]
    for i, ev in enumerate(evaluations, 1):
        parts.append(
            f"{i}. {ev['repo']} | 综合得分: {ev['score']:.2f}/2.00 | "
            f"定位:{ev['positioning']} 差异化:{ev['differentiation']} "
            f"护城河:{ev['moat']} 工程:{ev['engineering']} 可持续:{ev['sustainability']}"
        )
        if ev.get("summary"):
            parts.append(f"   总结: {ev['summary']}")
        if ev.get("strengths"):
            parts.append(f"   优势: {ev['strengths']}")
        if ev.get("weaknesses"):
            parts.append(f"   短板: {ev['weaknesses']}")
        parts.append("")

    parts.append(f"用户问题：{question}")
    return "\n".join(parts)


def _query_evaluation_by_repo(repo_url: str) -> dict | None:
    try:
        import asyncio

        from models import EvaluationRecord
        from sqlalchemy import desc, select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def _fetch():
            async with factory() as db:
                result = await db.execute(
                    select(EvaluationRecord)
                    .where(EvaluationRecord.repo_url == repo_url)
                    .order_by(desc(EvaluationRecord.created_at))
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    return {
                        "repo": row.repo_full_name,
                        "url": row.repo_url,
                        "score": row.weighted_total or 0.0,
                        "positioning": row.score_positioning or 0,
                        "differentiation": row.score_differentiation or 0,
                        "moat": row.score_moat or 0,
                        "engineering": row.score_engineering or 0,
                        "sustainability": row.score_sustainability or 0,
                        "summary": row.overall_summary or "",
                        "strengths": row.top_strengths or "",
                        "weaknesses": row.top_weaknesses or "",
                    }
                return None
            await engine.dispose()

        return asyncio.run(_fetch())
    except Exception as e:
        logger.warning("Failed to query evaluation by repo: %s", e)
        return None


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=5,
    soft_time_limit=120,
    time_limit=180,
    name="tasks.run_text_evaluation",
)
def run_text_evaluation(self, description: str, n_competitors: int = 3) -> dict:
    from core import llm
    from modules.evaluator.collector import RepoMeta
    from modules.evaluator.rubric import DIMENSIONS

    prompt = f"""你是产品竞争力评估专家。用户描述了一个产品，请用五维 Rubric 打分（0-2 分/维）。

产品描述：{description}

请先分析这个产品属于哪个领域，列出 3-5 个已知竞品（真实存在的产品名称）。
然后按五维评分：
1. 定位 — 目标用户和场景是否清晰？
2. 差异化 — 与竞品比有什么独特价值？
3. 护城河 — 防御能力、市场壁垒？
4. 工程健康度 — 根据描述推断开发活跃度？
5. 可持续性 — 商业模式、长期可行性？

输出格式：严格只输出 JSON：
{{
  "domain": "产品领域",
  "competitors": ["竞品1", "竞品2", "竞品3"],
  "scores": {{
    "positioning": {{"score": 0, "evidence": ["..."], "name": "定位", "name_en": "Positioning"}},
    "differentiation": {{"score": 0, "evidence": ["..."], "name": "差异化", "name_en": "Differentiation"}},
    "moat": {{"score": 0, "evidence": ["..."], "name": "护城河", "name_en": "Moat"}},
    "engineering": {{"score": 0, "evidence": ["..."], "name": "工程健康度", "name_en": "Engineering Health"}},
    "sustainability": {{"score": 0, "evidence": ["..."], "name": "可持续性", "name_en": "Sustainability"}}
  }},
  "overall_summary": "100字总结",
  "top_strengths": [],
  "top_weaknesses": [],
  "suggestions": [
    {{"dimension": "维度名", "issue": "问题描述", "fix": "具体改进建议", "priority": "高"}}
  ],
  "directions": ["发展方向1", "发展方向2"],
  "veto": {{"triggered": false, "reason": ""}}
}}"""

    try:
        result = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2500,
            timeout=90,
        )

        text = result["content"].strip()
        m = re.search(r'\{[\s\S]*\}', text)
        data = _json.loads(m.group(0)) if m else {}

        scores = data.get("scores", {})
        evaluation = {
            "scores": {},
            "weighted_total": 0.0,
            "overall_summary": data.get("overall_summary", ""),
            "top_strengths": data.get("top_strengths", []),
            "top_weaknesses": data.get("top_weaknesses", []),
            "suggestions": data.get("suggestions", []),
            "directions": data.get("directions", []),
            "veto": data.get("veto", {"triggered": False, "reason": ""}),
        }

        for key, dim in DIMENSIONS.items():
            s = scores.get(key, {})
            try:
                score = max(0, min(2, int(s.get("score", 0)))) if isinstance(s, dict) else 0
            except (TypeError, ValueError):
                score = 0
            evaluation["scores"][key] = {
                "name": dim["name"],
                "name_en": dim["name_en"],
                "weight": dim["weight"],
                "score": score,
                "max_score": 2,
                "evidence": s.get("evidence", []) if isinstance(s, dict) else [],
            }
            evaluation["weighted_total"] += score * dim["weight"]
        evaluation["weighted_total"] = round(evaluation["weighted_total"], 3)

        project = RepoMeta(owner="text", repo="custom", full_name="Custom Project")
        project.description = description
        competitors_meta = [
            {"full_name": c, "description": "", "stars": 0, "forks": 0, "commit_days_active_90d": 0, "last_commit_at": ""}
            for c in data.get("competitors", [])
        ]

        report_md = f"""# 产品竞争力评估报告

> 目标：自定义产品描述
> 综合得分：{evaluation['weighted_total']:.2f}/2.00

## 产品描述
{description}

## 领域
{data.get('domain', '未知')}

## 五维评分
| 维度 | 得分 | 评级 |
|------|:--:|:--:|
"""
        for key, dim in evaluation["scores"].items():
            rating = {0: "不合格", 1: "基本达标", 2: "良好"}[dim["score"]]
            report_md += f"| {dim['name']} | {dim['score']}/2 | {rating} |\n"

        report_md += f"\n## 总结\n{evaluation['overall_summary']}\n"

        if evaluation["top_strengths"]:
            report_md += f"\n**优势**: {', '.join(evaluation['top_strengths'])}\n"
        if evaluation["top_weaknesses"]:
            report_md += f"\n**短板**: {', '.join(evaluation['top_weaknesses'])}\n"
        if data.get("competitors"):
            report_md += f"\n**竞品**: {', '.join(data['competitors'])}\n"
        report_md += "\n---\n*由竞品雷达评测引擎生成*"

        try:
            import asyncio

            from models import EvaluationRecord
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
            factory = async_sessionmaker(engine, expire_on_commit=False)

            async def _save():
                async with factory() as db:
                    db.add(EvaluationRecord(
                        repo_url="text://" + description[:50],
                        repo_full_name="Custom Project",
                        weighted_total=evaluation["weighted_total"],
                        score_positioning=evaluation["scores"].get("positioning", {}).get("score", 0),
                        score_differentiation=evaluation["scores"].get("differentiation", {}).get("score", 0),
                        score_moat=evaluation["scores"].get("moat", {}).get("score", 0),
                        score_engineering=evaluation["scores"].get("engineering", {}).get("score", 0),
                        score_sustainability=evaluation["scores"].get("sustainability", {}).get("score", 0),
                        overall_summary=evaluation["overall_summary"],
                        top_strengths=_json.dumps(evaluation["top_strengths"], ensure_ascii=False),
                        top_weaknesses=_json.dumps(evaluation["top_weaknesses"], ensure_ascii=False),
                        report_markdown=report_md,
                    ))
                    await db.commit()
                await engine.dispose()

            asyncio.run(_save())
        except Exception:
            logger.warning("Failed to persist text evaluation to DB", exc_info=True)

        logger.info("Text evaluation completed: score=%.2f", evaluation["weighted_total"])
        return {
            "status": "done",
            "result": {
                "evaluation": evaluation,
                "project_meta": {
                    "full_name": "Custom Project",
                    "description": description,
                    "stars": 0, "forks": 0, "open_issues": 0,
                    "language": data.get("domain", ""), "topics": [],
                    "license_name": "", "created_at": "", "updated_at": "",
                    "commit_days_active_90d": 0, "last_commit_at": "",
                    "issue_stats": {},
                },
                "competitors_meta": competitors_meta,
                "report_markdown": report_md,
            },
        }
    except Exception as exc:
        logger.error("Text evaluation failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=5,
    soft_time_limit=180,
    time_limit=300,
    name="tasks.run_evaluation",
)
def run_evaluation(self, repo_url: str, description: str = "", n_competitors: int = 5) -> dict:
    from modules.evaluator.collector import collect_repo
    from modules.evaluator.competitor import search_competitors
    from modules.evaluator.reporter import generate_report
    from modules.evaluator.rubric import evaluate_product

    try:
        project = collect_repo(repo_url)
        if project.error:
            return {"status": "failed", "result": {"error": project.error}}

        competitors = search_competitors(
            project_description=description or project.description,
            n=n_competitors,
            exclude_full_name=project.full_name,
        )

        result = evaluate_product(project, competitors, with_usage=True)
        evaluation = result["evaluation"]
        report = generate_report(evaluation, project, competitors)

        try:
            import asyncio
            import json

            from models import EvaluationRecord
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            scores = evaluation.get("scores", {})
            engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
            factory = async_sessionmaker(engine, expire_on_commit=False)

            async def _save():
                async with factory() as db:
                    db.add(EvaluationRecord(
                        user_id=None,
                        repo_url=repo_url,
                        repo_full_name=project.full_name,
                        weighted_total=evaluation.get("weighted_total", 0),
                        score_positioning=scores.get("positioning", {}).get("score", 0),
                        score_differentiation=scores.get("differentiation", {}).get("score", 0),
                        score_moat=scores.get("moat", {}).get("score", 0),
                        score_engineering=scores.get("engineering", {}).get("score", 0),
                        score_sustainability=scores.get("sustainability", {}).get("score", 0),
                        overall_summary=evaluation.get("overall_summary", ""),
                        top_strengths=json.dumps(evaluation.get("top_strengths", []), ensure_ascii=False),
                        top_weaknesses=json.dumps(evaluation.get("top_weaknesses", []), ensure_ascii=False),
                        report_markdown=report,
                    ))
                    await db.commit()
                await engine.dispose()

            asyncio.run(_save())
            logger.info("Evaluation persisted to DB: repo=%s score=%.2f",
                          project.full_name, evaluation.get("weighted_total", 0))
        except Exception:
            logger.warning("Failed to persist evaluation to DB: repo=%s", project.full_name, exc_info=True)

        logger.info("Evaluation completed: task_id=%s repo=%s score=%.2f",
                      self.request.id, project.full_name, evaluation.get("weighted_total", 0))

        return {
            "status": "done",
            "result": {
                "evaluation": evaluation,
                "project_meta": {
                    "full_name": project.full_name,
                    "description": project.description,
                    "stars": project.stars,
                    "forks": project.forks,
                    "open_issues": project.open_issues,
                    "language": project.language,
                    "topics": project.topics,
                    "license_name": project.license_name,
                    "created_at": project.created_at,
                    "updated_at": project.updated_at,
                    "commit_days_active_90d": project.commit_days_active_90d,
                    "last_commit_at": project.last_commit_at,
                    "issue_stats": project.open_issue_stats,
                },
                "competitors_meta": [
                    {
                        "full_name": c.full_name,
                        "description": c.description,
                        "stars": c.stars,
                        "forks": c.forks,
                        "commit_days_active_90d": c.commit_days_active_90d,
                        "last_commit_at": c.last_commit_at,
                    }
                    for c in competitors if not c.error
                ],
                "report_markdown": report,
            },
        }
    except Exception as exc:
        logger.error("Evaluation failed: task_id=%s repo=%s error=%s",
                      self.request.id, repo_url, exc)
        raise self.retry(exc=exc)
