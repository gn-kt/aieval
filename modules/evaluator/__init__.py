"""Agent 产品竞争力评测引擎 —— LLM-as-a-Judge + 五维 Rubric。

四步流水线：
1. collector   → GitHub API 采集项目元数据（README/issues/commits）
2. competitor  → 自动搜索 3-5 个竞品做横向对比
3. rubric      → 五维 Rubric + LLM-as-a-Judge 逐项打分
4. reporter    → 生成结构化评估报告
"""

from .collector import RepoMeta, collect_repo
from .competitor import search_competitors
from .reporter import generate_report
from .rubric import DIMENSIONS, evaluate_product

__all__ = [
    "DIMENSIONS",
    "RepoMeta",
    "collect_repo",
    "evaluate_product",
    "generate_report",
    "search_competitors",
]
