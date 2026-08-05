"""评估报告生成器 —— 将 Rubric 评分转换为结构化 Markdown 报告。"""
from datetime import datetime, timezone

from .collector import RepoMeta


def generate_report(evaluation: dict, project: RepoMeta, competitors: list[RepoMeta] | None = None) -> str:
    """生成结构化 Markdown 评估报告。

    Args:
        evaluation: rubric.evaluate_product 的返回值。
        project: 目标项目元数据。
        competitors: 竞品列表。

    Returns:
        str: 完整的 Markdown 报告。
    """
    competitors = competitors or []
    scores = evaluation.get("scores", {})
    weighted_total = evaluation.get("weighted_total", 0)
    overall_summary = evaluation.get("overall_summary", "")
    strengths = evaluation.get("top_strengths", [])
    weaknesses = evaluation.get("top_weaknesses", [])
    veto = evaluation.get("veto", {})
    suggestions = evaluation.get("suggestions", [])
    directions = evaluation.get("directions", [])

    lines = [
        "# 产品竞争力评估报告",
        "",
        f"> 评估时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> 目标项目：[{project.full_name}]({project.url})",
        f"> 综合得分：**{weighted_total:.2f} / 2.00**",
        "",
    ]

    if veto.get("triggered"):
        lines.append(f"> !! **否决项触发**：{veto.get('reason', '')}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 项目概况",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| Stars | {project.stars} |",
        f"| Forks | {project.forks} |",
        f"| Open Issues | {project.open_issues} |",
        f"| 主语言 | {project.language} |",
        f"| 许可证 | {project.license_name or '—'} |",
        f"| Topics | {', '.join(project.topics) if project.topics else '—'} |",
        f"| 创建时间 | {project.created_at} |",
        f"| 最近更新 | {project.updated_at} |",
        f"| 最近 commit 活跃天数(90d) | {project.commit_days_active_90d} |",
        f"| Issue 关闭率 | {project.open_issue_stats.get('close_rate', '—')}% |",
        "",
        "---",
        "",
        "## 五维评分",
        "",
        "| 维度 | 权重 | 得分 | 评级 |",
        "|------|:----:|:----:|:----:|",
    ]

    for key, dim in scores.items():
        score = dim["score"]
        rating = {0: "不合格", 1: "基本达标", 2: "良好"}.get(score, "—")
        star = {0: "[*  ]", 1: "[** ]", 2: "[***]"}.get(score, "—")
        lines.append(f"| {dim['name']}（{dim['name_en']}） | {dim['weight']*100:.0f}% | {star} | {rating} |")

    lines += [
        "",
        "---",
        "",
        "## 各维度详情",
        "",
    ]

    for key, dim in scores.items():
        evidence = dim.get("evidence", [])
        lines += [
            f"### {dim['name']}（{dim['name_en']}） — {dim['score']}/2",
            "",
            f"权重：{dim['weight']*100:.0f}%",
            "",
        ]
        if evidence:
            lines.append("**证据**：")
            for e in evidence:
                lines.append(f"- {e}")
        else:
            lines.append("（无具体证据）")
        lines.append("")

    if competitors:
        lines += [
            "---",
            "",
            "## 竞品对比",
            "",
            "| 项目 | Stars | Forks | 活跃天数(90d) | 描述 |",
            "|------|:-----:|:-----:|:------------:|------|",
        ]
        lines.append(f"| **{project.full_name}** (目标) | {project.stars} | {project.forks} | {project.commit_days_active_90d} | {project.description[:50]} |")
        for c in competitors:
            lines.append(f"| {c.full_name} | {c.stars} | {c.forks} | {c.commit_days_active_90d} | {c.description[:50]} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 总结",
        "",
        f"**综合评分**：{weighted_total:.2f}/2.00",
        "",
    ]

    if overall_summary:
        lines.append(f"> {overall_summary}")
        lines.append("")

    if strengths:
        lines.append("**优势维度**：")
        for s in strengths:
            lines.append(f"- [+] {s}")
        lines.append("")

    if weaknesses:
        lines.append("**待改进维度**：")
        for w in weaknesses:
            lines.append(f"- [!] {w}")
        lines.append("")

    if suggestions:
        lines += [
            "---",
            "",
            "## 优化建议",
            "",
            "| 维度 | 问题 | 改进建议 | 优先级 |",
            "|------|------|---------|:--:|",
        ]
        for s in suggestions:
            if isinstance(s, dict):
                lines.append(f"| {s.get('dimension', '—')} | {s.get('issue', '—')} | {s.get('fix', '—')} | {s.get('priority', '—')} |")
        lines.append("")

    if directions:
        lines += [
            "---",
            "",
            "## 发展方向",
            "",
        ]
        for i, d in enumerate(directions, 1):
            lines.append(f"{i}. {d}")
        lines.append("")

    lines += [
        "---",
        "",
        "*报告由 AgentForge 评测引擎自动生成 | LLM-as-a-Judge + 五维 Rubric*",
    ]

    return "\n".join(lines)
