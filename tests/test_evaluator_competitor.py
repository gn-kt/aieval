"""Tests for modules/evaluator/competitor.py"""
import pytest
import sys
sys.path.insert(0, r"D:\codebase\作品集\竞品雷达")

from modules.evaluator.competitor import search_competitors
from modules.evaluator.collector import RepoMeta


class TestSearchCompetitorsKeyword:
    def test_returns_list_of_repo_meta(self):
        # Use keyword search (no LLM API needed)
        results = search_competitors(
            "A Python linter and code formatter",
            n=2,
            use_llm=False,
        )
        assert isinstance(results, list)
        if len(results) > 0:
            assert isinstance(results[0], RepoMeta)

    def test_respects_n_limit(self):
        results = search_competitors(
            "machine learning framework",
            n=3,
            use_llm=False,
        )
        assert len(results) <= 3

    def test_empty_description(self):
        results = search_competitors("", n=2, use_llm=False)
        assert isinstance(results, list)
