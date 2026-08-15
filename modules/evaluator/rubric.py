"""五维 Rubric + LLM-as-a-Judge 打分引擎。

五维：
1. 定位（Positioning）    — 目标用户、核心场景是否清晰
2. 差异化（Differentiation）— 与竞品相比的独特价值
3. 护城河（Moat）          — 防御能力 / 平台风险 / 不可绕过性
4. 工程健康度（Engineering）— 代码质量、测试、CI/CD、依赖
5. 可持续性（Sustainability）— 社区活跃度、商业模式、长期可维护性

每维 0-2 分（不合格 / 基本达标 / 良好），加否决项（幻觉检测）。
"""

import json
import re

from logger import get_logger

from .collector import RepoMeta

logger = get_logger(__name__)

DIMENSIONS: dict[str, dict] = {
    "positioning": {
        "name": "定位",
        "name_en": "Positioning",
        "weight": 0.20,
        "definition": "目标用户是否清晰？核心使用场景是否明确？README 能否让新用户理解产品做什么？",
        "scoring": {
            "0": "目标用户模糊，说不清谁会用这个产品；README 缺少示例或场景描述",
            "1": "目标用户基本清楚，但描述偏泛；README 有说明但缺少具体使用示例或对比",
            "2": "README 有即时代码示例 + 明确使用场景 + 与竞品的区别说明",
        },
        "anchors": {
            "READM长度": {"0": "<500字 或无 README", "1": "500-2000 字", "2": ">2000 字且有代码示例"},
        },
    },
    "differentiation": {
        "name": "差异化",
        "name_en": "Differentiation",
        "weight": 0.25,
        "definition": "与竞品相比有什么独特价值？是『做得更好』还是『做得不同』？是否比竞品有明显优势？",
        "scoring": {
            "0": "与竞品功能高度重叠，README 未提及差异点；所有竞品都能做同样的事",
            "1": "有差异但主要体现在功能数量（更全而非更深）；竞品通过增加功能可追平",
            "2": "有结构性差异（性能/安全/架构级别）；竞品无法通过简单扩展达到同等水平",
        },
        "anchors": {
            "与竞品Stars比": {"0": "所有竞品 stars 均高于目标", "1": "与竞品 stars 接近", "2": "显著高于竞品 stars"},
        },
    },
    "moat": {
        "name": "护城河",
        "name_en": "Moat",
        "weight": 0.25,
        "definition": "防御能力如何？stars/forks 规模是否形成马太效应？技术栈是否有维护成本壁垒？",
        "scoring": {
            "0": "stars<500 且 forks<50；功能简单、大平台可轻易复现；无技术壁垒",
            "1": "stars 500-5000；有一定网络效应但技术壁垒有限；核心功能可能被替代",
            "2": "stars>5000 或 forks>500；形成了社区生态或技术壁垒（如多语言/多平台适配成本）",
        },
        "anchors": {
            "stars阈值": {"0": "<500", "1": "500-5,000", "2": ">5,000"},
            "forks阈值": {"0": "<50", "1": "50-500", "2": ">500"},
        },
    },
    "engineering": {
        "name": "工程健康度",
        "name_en": "Engineering Health",
        "weight": 0.15,
        "definition": "commit 频率和 issue 响应是否健康？代码质量如何？",
        "scoring": {
            "0": "近 90 天无 commit；issue 关闭率 <30%；无 CI 信号",
            "1": "近 90 天有 commit 但不持续（活跃<15天）；issue 关闭率 30-70%；有维护但不活跃",
            "2": "近 90 天活跃 >15 天；issue 关闭率 >70%；持续高频迭代",
        },
        "anchors": {
            "活跃天数(90d)": {"0": "0-5 天", "1": "5-15 天", "2": ">15 天"},
            "issue关闭率": {"0": "<30%", "1": "30-70%", "2": ">70%"},
        },
    },
    "sustainability": {
        "name": "可持续性",
        "name_en": "Sustainability",
        "weight": 0.15,
        "definition": "项目能否长期存活？是否有组织/基金会支持？stars 增长趋势如何？是否已停止维护？",
        "scoring": {
            "0": "项目已归档或最后更新超过 1 年；单人维护无外部贡献者；stars 停滞",
            "1": "有小团队维护；stars 缓慢增长；有开源社区但无明确资金来源",
            "2": "有组织/基金会/公司支持；stars 持续增长；有明确 funding 渠道（GitHub Sponsors/OpenCollective 等）",
        },
        "anchors": {
            "最后更新": {"0": ">12 个月未更新", "1": "1-12 个月内有更新但低频", "2": "持续活跃更新"},
            "组织归属": {"0": "个人仓库", "1": "小团队", "2": "知名组织/基金会/公司"},
        },
    },
}

SYSTEM_PROMPT = """你是严格的产品竞争力评估专家。用五维 Rubric 对目标项目打分。

【核心原则：宁低勿高】
- 2 分（良好）= 该维度有明确证据表明超越基准，不是"还不错"而是"突出"
- 1 分（基本达标）= 该维度处于正常水平，没有明显短板也没有突出亮点
- 0 分（不合格）= 该维度有明确缺陷或信息不足

【定量锚定阈值（优先使用，除非有强烈反证）】

定位 (Positioning) — 20%:
- 0: README<500字或无示例 / 说不清谁用
- 1: README 500-2000字，有基本说明但无对比
- 2: README>2000字且有代码示例+场景描述+竞品对比

差异化 (Differentiation) — 25%:
- 0: 竞品 stars 均远超目标 / 无可见独特价值
- 1: 有差异点但集中在功能数量 / stars 与竞品接近
- 2: 有性能/架构级差异 / stars 显著高于竞品

护城河 (Moat) — 25%:
- 0: stars<500 且 forks<50
- 1: stars 500-5000 或 forks 50-500
- 2: stars>5000 或 forks>500（马太效应已形成）

工程健康度 (Engineering) — 15%:
- 0: 活跃天数(90d)<5 或 issue关闭率<30%
- 1: 活跃天数 5-15 或 issue关闭率 30-70%
- 2: 活跃天数>15 且 issue关闭率>70%

可持续性 (Sustainability) — 15%:
- 0: 最后更新>12个月 / 个人仓库 / 已归档
- 1: 最后更新 1-12个月 / 小团队 / 无资助
- 2: 持续活跃 / 知名组织或基金会 / 有 funding

【打分规则】
1. 优先参照定量阈值。如果数据落在 1 分区间，不要给 2 分，除非有极其强烈的结构性证据
2. 每条证据必须引用项目数据（stars数、活跃天数、issue率等具体数字）
3. 竞品对比时：若竞品在多个维度数据优于目标，相应维度必须降分

【否决项检查】
- README 是否有明显夸大/不实声明？
- 项目元数据是否存在矛盾（如 stars 高但无 commit 活动）？

【输出格式】严格只输出 JSON：
{
  "scores": {
    "positioning": {"score": 0, "evidence": ["具体证据"]},
    "differentiation": {"score": 0, "evidence": ["具体证据"]},
    "moat": {"score": 0, "evidence": ["具体证据"]},
    "engineering": {"score": 0, "evidence": ["具体证据"]},
    "sustainability": {"score": 0, "evidence": ["具体证据"]}
  },
  "overall_summary": "50-100字总结，包含最关键发现",
  "top_strengths": ["优势维度名"],
  "top_weaknesses": ["短板维度名"],
  "suggestions": [
    {"dimension": "维度名", "issue": "问题描述", "fix": "具体改进建议", "priority": "高/中/低"}
  ],
  "directions": ["发展方向1：一句话描述", "发展方向2：一句话描述"],
  "veto": {"triggered": false, "reason": ""}
}

【关于 suggestions】：
- 针对每个得分 ≤1 的维度，给出至少 1 条具体改进建议
- 每条建议必须引用实际数据（如"issue关闭率仅 20%，建议建立 SLA 机制确保 issue 48 小时内响应"）
- priority 根据问题严重程度标记：0分=高, 1分=中

【关于 directions】：
- 基于项目当前定位和差异化优势，给出 2-3 个可行的未来发展方向
- 每个方向一句话，具体可执行，不是空泛的口号
- 例如"支持 VSCode 插件市场发布"而非"扩大生态"
"""

def _build_prompt(project: RepoMeta, competitors: list[RepoMeta]) -> str:
    readme_preview = project.readme[:3000] if project.readme else "(无 README)"
    parts = [
        "=== 目标项目 ===",
        f"仓库：{project.full_name}",
        f"描述：{project.description}",
        f"Stars：{project.stars} | Forks：{project.forks} | Open Issues：{project.open_issues}",
        f"语言：{project.language} | 许可证：{project.license_name}",
        f"Topics：{', '.join(project.topics) if project.topics else '—'}",
        f"创建：{project.created_at} | 最近更新：{project.updated_at} | 最后commit：{project.last_commit_at}",
        f"活跃天数(90d)：{project.commit_days_active_90d} | 最近100条commit数：{project.recent_commits_count}",
        f"Issue统计：open={project.open_issue_stats.get('open','?')} closed={project.open_issue_stats.get('closed','?')} 关闭率={project.open_issue_stats.get('close_rate','?')}%",
        "",
        "=== README（前3000字）===",
        readme_preview,
    ]

    if competitors:
        parts.append("\n=== 竞品 ===")
        for i, c in enumerate(competitors, 1):
            parts.append(
                f"竞品{i}：{c.full_name} | Stars:{c.stars} Forks:{c.forks} | "
                f"活跃:{c.commit_days_active_90d}d | 描述:{c.description[:80]}"
            )

    parts.append(f"\n注意：stars={project.stars}，活跃90d={project.commit_days_active_90d}天，issue关闭率={project.open_issue_stats.get('close_rate','?')}%。请按定量锚定阈值打分，宁低勿高。")

    return "\n".join(parts)


def evaluate_product(
    project: RepoMeta,
    competitors: list[RepoMeta] | None = None,
    *,
    with_usage: bool = False,
) -> dict:
    """LLM-as-a-Judge 五维评估 + 硬阈值校准。

    Args:
        project: 目标项目元数据。
        competitors: 竞品列表（可为空）。
        with_usage: True 时返回完整 dict（含 usage/latency），否则返回纯评估结果。

    Returns:
        dict with keys: scores, overall_summary, top_strengths, top_weaknesses, veto,
                        weighted_total, dimensions (含 name/weight/score)。
    """
    from core import llm

    competitors = competitors or []
    prompt = _build_prompt(project, competitors)

    result = llm.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
        timeout=60,
    )

    evaluation = _parse_result(result["content"], DIMENSIONS)
    evaluation = _apply_hard_thresholds(evaluation, project, competitors)

    if with_usage:
        return {"evaluation": evaluation, "usage": result["usage"], "latency_ms": result["latency_ms"]}
    return evaluation


def _apply_hard_thresholds(evaluation: dict, project: RepoMeta, competitors: list[RepoMeta]) -> dict:
    """硬阈值校准：LLM 打分后，用量化数据强制封顶。

    规则：
    - 护城河：stars<500 → max 0 / stars<5000 → max 1
    - 工程：活跃天数<5 → max 0 / <15 → max 1
    - 工程：issue关闭率<30% → max 0 / <70% → max 1
    - 可持续性：>12个月未更新 → max 0
    - 差异化：所有竞品 stars 均 > 目标 → max 1
    """
    scores = evaluation.get("scores", {})
    calibrations: list[str] = []

    moat = scores.get("moat", {})
    if project.stars < 500 and moat.get("score", 0) > 0:
        moat["score"] = 0
        calibrations.append(f"护城河: stars={project.stars}<500 → 上限0")
    elif project.stars < 5000 and moat.get("score", 0) > 1:
        moat["score"] = 1
        calibrations.append(f"护城河: stars={project.stars}<5000 → 上限1")

    eng = scores.get("engineering", {})
    if project.commit_days_active_90d < 5 and eng.get("score", 0) > 0:
        eng["score"] = 0
        calibrations.append(f"工程: 活跃{project.commit_days_active_90d}d<5 → 上限0")
    elif project.commit_days_active_90d < 15 and eng.get("score", 0) > 1:
        eng["score"] = 1
        calibrations.append(f"工程: 活跃{project.commit_days_active_90d}d<15 → 上限1")

    close_rate = project.open_issue_stats.get("close_rate", 0)
    if close_rate and close_rate < 30 and eng.get("score", 0) > 0:
        eng["score"] = 0
        calibrations.append(f"工程: issue关闭率{close_rate}%<30% → 上限0")
    elif close_rate and close_rate < 70 and eng.get("score", 0) > 1:
        eng["score"] = 1
        calibrations.append(f"工程: issue关闭率{close_rate}%<70% → 上限1")

    sust = scores.get("sustainability", {})
    if project.last_commit_at:
        try:
            from datetime import datetime, timezone
            last = datetime.strptime(project.last_commit_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            months_since = (datetime.now(timezone.utc) - last).days / 30
            if months_since > 12 and sust.get("score", 0) > 0:
                sust["score"] = 0
                calibrations.append(f"可持续性: {months_since:.0f}月未更新 → 上限0")
        except (ValueError, TypeError):
            pass

    diff = scores.get("differentiation", {})
    if competitors and diff.get("score", 0) > 1:
        max_comp_stars = max((c.stars for c in competitors if not c.error), default=0)
        if max_comp_stars > project.stars * 2:
            diff["score"] = 1
            calibrations.append(f"差异化: 竞品stars({max_comp_stars}) > 目标({project.stars})×2 → 上限1")

    if calibrations:
        wt = sum(
            d["weight"] * d["score"]
            for d in scores.values()
        )
        evaluation["weighted_total"] = round(wt, 3)
        evaluation["_calibrations"] = calibrations
        logger.info("Hard thresholds applied: %s", "; ".join(calibrations))

    return evaluation


def _parse_result(text: str, dimensions: dict) -> dict:
    json_text = text.strip()
    match = re.search(r"\{[\s\S]*\}", json_text)
    if match:
        json_text = match.group(0)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.warning("LLM output is not valid JSON, falling back to text parse")
        return _fallback_parse(text, dimensions)

    scores = data.get("scores", {})
    weighted_total = 0.0
    dim_results = {}

    for key, dim in dimensions.items():
        dim_score = scores.get(key, {})
        score_value = dim_score.get("score", 0) if isinstance(dim_score, dict) else 0
        # 钳制到 0-2，防止 LLM 输出超界（如 3/5 分）导致总分 >2.00
        try:
            score_value = max(0, min(2, int(score_value)))
        except (TypeError, ValueError):
            score_value = 0
        weight = dim["weight"]
        weighted_total += score_value * weight
        dim_results[key] = {
            "name": dim["name"],
            "name_en": dim["name_en"],
            "weight": weight,
            "score": score_value,
            "max_score": 2,
            "evidence": dim_score.get("evidence", []) if isinstance(dim_score, dict) else [],
        }

    return {
        "scores": dim_results,
        "weighted_total": round(weighted_total, 3),
        "overall_summary": data.get("overall_summary", ""),
        "top_strengths": data.get("top_strengths", []),
        "top_weaknesses": data.get("top_weaknesses", []),
        "suggestions": data.get("suggestions", []),
        "directions": data.get("directions", []),
        "veto": data.get("veto", {"triggered": False, "reason": ""}),
        "raw_llm_output": text,
    }


def _fallback_parse(text: str, dimensions: dict) -> dict:
    dim_results = {}
    weighted_total = 0.0
    for key, dim in dimensions.items():
        score = 0
        pattern = rf'{dim["name"]}|{dim["name_en"]}'
        section = re.split(pattern, text, flags=re.IGNORECASE)
        if len(section) > 1:
            digits = re.findall(r"[0-2]", section[1][:200])
            if digits:
                score = int(digits[0])
        dim_results[key] = {
            "name": dim["name"],
            "name_en": dim["name_en"],
            "weight": dim["weight"],
            "score": score,
            "max_score": 2,
            "evidence": [],
        }
        weighted_total += score * dim["weight"]

    return {
        "scores": dim_results,
        "weighted_total": round(weighted_total, 3),
        "overall_summary": "(解析失败，请查看原始输出)",
        "top_strengths": [],
        "top_weaknesses": [],
        "suggestions": [],
        "directions": [],
        "veto": {"triggered": False, "reason": ""},
        "raw_llm_output": text,
    }
