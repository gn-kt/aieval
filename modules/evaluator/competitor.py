"""竞品搜索 —— 基于项目描述自动发现 3-5 个竞品仓库并采集元数据。"""
import re

from config import GITHUB_TOKEN, GITHUB_VERIFY_SSL
from logger import get_logger

from .collector import RepoMeta, collect_repo

logger = get_logger(__name__)


def _llm_suggest_competitors(description: str, n: int = 5) -> list[str]:
    """用 LLM 分析项目描述 → 给出竞品搜索关键词。"""
    from core import llm

    prompt = f"""你是开源项目分析专家。下面是目标项目的一句话描述，请给出 {n} 个最可能与之竞争的开源项目。

目标项目描述：{description}

要求：
1. 项目必须是真实存在的著名开源项目（GitHub 上 star 较多）
2. 每个项目用一行，只输出 "owner/repo — 一句话说明"
3. 只输出项目名，不要其他任何内容

竞品项目："""

    result = llm.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )
    lines = result["content"].strip().split("\n")
    competitors = []
    for line in lines:
        match = re.match(r"([\w.\-]+/[\w.\-]+)", line.strip())
        if match:
            competitors.append(match.group(1))
        if len(competitors) >= n:
            break
    return competitors


def _keyword_search_competitors(description: str, n: int = 5) -> list[str]:
    """用 GitHub Search API 按关键词搜索近似项目。"""
    import httpx

    client = httpx.Client(
        base_url="https://api.github.com",
        headers={"Accept": "application/vnd.github+json"},
        timeout=15,
        verify=GITHUB_VERIFY_SSL,
        follow_redirects=True,
    )
    token = GITHUB_TOKEN
    if token:
        client.headers["Authorization"] = f"Bearer {token}"

    words = re.findall(r"[\w]+", description.lower())
    stop_words = {"a", "an", "the", "is", "and", "or", "for", "of", "to", "in", "with", "on", "that", "this"}
    keywords = [w for w in words if len(w) > 2 and w not in stop_words][:5]
    query = "+".join(keywords) if keywords else "ai+agent+tool"
    url = f"/search/repositories?q={query}&sort=stars&order=desc&per_page={n + 3}"

    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        repos = []
        for item in data.get("items", []):
            repos.append(item["full_name"])
            if len(repos) >= n:
                break
        return repos
    except Exception as exc:
        logger.warning("GitHub search failed: %s", exc)
        return []


def search_competitors(
    project_description: str,
    n: int = 5,
    *,
    use_llm: bool = True,
    exclude_full_name: str | None = None,
) -> list[RepoMeta]:
    """搜索竞品并采集元数据。

    Args:
        project_description: 项目的一句话描述。
        n: 竞品数量（默认 5）。
        use_llm: 是否用 LLM 推荐竞品名（否则用关键词搜索）。

    Returns:
        list[RepoMeta]: 每个竞品的完整元数据。
    """
    if use_llm:
        candidates = _llm_suggest_competitors(project_description, n=n)
        if not candidates:
            candidates = _keyword_search_competitors(project_description, n=n)
    else:
        candidates = _keyword_search_competitors(project_description, n=n)

    competitors: list[RepoMeta] = []
    for full_name in candidates:
        # 过滤掉目标仓库自己（LLM 可能把目标列为竞品）
        if exclude_full_name and full_name.lower() == exclude_full_name.lower():
            continue
        meta = collect_repo(f"https://github.com/{full_name}")
        competitors.append(meta)
        if len(competitors) >= n:
            break

    return competitors
