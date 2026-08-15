"""GitHub API 采集器 —— 获取项目 README / Issues / Commits 元数据。"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from config import GITHUB_TOKEN, GITHUB_VERIFY_SSL
from logger import get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
_COLLECTOR_CLIENT: httpx.Client | None = None


@dataclass
class RepoMeta:
    owner: str
    repo: str
    full_name: str
    description: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str = ""
    topics: list[str] = field(default_factory=list)
    license_name: str = ""
    readme: str = ""
    recent_commits_count: int = 0
    commit_days_active_90d: int = 0
    last_commit_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    open_issue_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"


def _get_client() -> httpx.Client:
    global _COLLECTOR_CLIENT
    if _COLLECTOR_CLIENT is None:
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        _COLLECTOR_CLIENT = httpx.Client(
            base_url=GITHUB_API,
            headers=headers,
            timeout=30,
            verify=GITHUB_VERIFY_SSL,
            follow_redirects=True,
        )
    return _COLLECTOR_CLIENT


def _parse_github_url(repo_url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[:/]([^/]+)/([^/\s#]+?)(?:\.git)?(?:#.*)?$", repo_url.rstrip("/"))
    if not m:
        return None
    return m.group(1), m.group(2)


def collect_repo(repo_url: str) -> RepoMeta:
    """采集单个 GitHub 仓库的元数据。

    Returns:
        RepoMeta: 含 README / issues 统计 / 提交频率 / 语言 / 话题等。
        若采集失败，error 字段非空。
    """
    parsed = _parse_github_url(repo_url)
    if not parsed:
        return RepoMeta(owner="", repo="", full_name="", error=f"Invalid GitHub URL: {repo_url}")
    owner, repo = parsed
    full_name = f"{owner}/{repo}"
    meta = RepoMeta(owner=owner, repo=repo, full_name=full_name)
    client = _get_client()

    def _get(path: str) -> dict | None:
        try:
            resp = client.get(path)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                meta.error = "GitHub API rate limit exceeded. Set GITHUB_TOKEN to increase limit."
                return None
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("GitHub API failed %s: %s", path, exc)
            return None

    repo_data = _get(f"/repos/{full_name}")
    if repo_data is None:
        meta.error = meta.error or f"Repo not found: {full_name}"
        return meta

    meta.description = (repo_data.get("description") or "").strip()
    meta.stars = repo_data.get("stargazers_count", 0)
    meta.forks = repo_data.get("forks_count", 0)
    meta.open_issues = repo_data.get("open_issues_count", 0)
    meta.language = repo_data.get("language") or ""
    meta.topics = repo_data.get("topics", [])
    meta.license_name = (repo_data.get("license") or {}).get("spdx_id", "")
    meta.created_at = (repo_data.get("created_at") or "")[:10]
    meta.updated_at = (repo_data.get("updated_at") or "")[:10]
    # 最后代码活动时间用 pushed_at 兜底（即使 90 天内无 commit，可持续性判断仍有效）
    meta.last_commit_at = (repo_data.get("pushed_at") or "")[:10]

    readme_data = _get(f"/repos/{full_name}/readme")
    if readme_data:
        try:
            import base64
            meta.readme = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="replace")
        except Exception:
            pass

    # 活跃天数必须限定在最近 90 天内统计，否则高频项目会被误判为“不活跃”
    since_90d = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits_data = _get(f"/repos/{full_name}/commits?since={since_90d}&per_page=100")
    if commits_data and isinstance(commits_data, list):
        meta.recent_commits_count = len(commits_data)
        commit_dates: set[str] = set()
        for c in commits_data:
            date_str = (c.get("commit", {}).get("committer", {}).get("date", "") or "")[:10]
            if date_str:
                commit_dates.add(date_str)
        meta.commit_days_active_90d = len(commit_dates)

    # 关闭率统一用 Search API 的 type:issue 口径（open/closed 均不含 PR），
    # 避免与 repo 元数据的 open_issues_count（含 PR）混算导致系统性偏低
    open_count = 0
    closed_count = 0
    for state in ("open", "closed"):
        issues_data = _get(f"/search/issues?q=repo:{full_name}+type:issue+state:{state}&per_page=1")
        if issues_data:
            total_count = issues_data.get("total_count", 0)
            meta.open_issue_stats[state] = total_count
            if state == "closed":
                closed_count = total_count
            else:
                open_count = total_count
    total_issues = open_count + closed_count
    meta.open_issue_stats["close_rate"] = round(closed_count / total_issues * 100, 1) if total_issues > 0 else 0

    return meta
