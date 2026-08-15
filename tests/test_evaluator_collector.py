"""Tests for modules/evaluator/collector.py"""
import pytest

from modules.evaluator.collector import _parse_github_url, RepoMeta


class TestParseGithubUrl:
    def test_standard_url(self):
        result = _parse_github_url("https://github.com/astral-sh/ruff")
        assert result == ("astral-sh", "ruff")

    def test_url_with_trailing_slash(self):
        result = _parse_github_url("https://github.com/owner/repo/")
        assert result == ("owner", "repo")

    def test_url_with_git_suffix(self):
        result = _parse_github_url("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_url_with_fragment(self):
        result = _parse_github_url("https://github.com/owner/repo#readme")
        assert result == ("owner", "repo")

    def test_invalid_url(self):
        result = _parse_github_url("https://gitlab.com/owner/repo")
        assert result is None

    def test_empty_string(self):
        result = _parse_github_url("")
        assert result is None

    def test_not_a_url(self):
        result = _parse_github_url("just-a-string")
        assert result is None

    def test_ssh_style_url(self):
        result = _parse_github_url("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")


class TestRepoMeta:
    def test_default_values(self):
        meta = RepoMeta(owner="o", repo="r", full_name="o/r")
        assert meta.owner == "o"
        assert meta.repo == "r"
        assert meta.stars == 0
        assert meta.topics == []
        assert meta.error == ""

    def test_url_property(self):
        meta = RepoMeta(owner="o", repo="r", full_name="o/r")
        assert meta.url == "https://github.com/o/r"

    def test_error_field(self):
        meta = RepoMeta(owner="", repo="", full_name="", error="Invalid URL")
        assert meta.error == "Invalid URL"

    def test_collect_invalid_url(self):
        from modules.evaluator.collector import collect_repo
        result = collect_repo("not-a-github-url")
        assert result.error != ""
        assert result.full_name == ""
