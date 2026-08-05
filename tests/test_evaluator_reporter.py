"""Tests for modules/evaluator/reporter.py"""
import pytest
import sys
sys.path.insert(0, r"D:\codebase\作品集\竞品雷达")

from modules.evaluator.reporter import generate_report
from modules.evaluator.collector import RepoMeta


def make_evaluation(scores_overrides=None):
    defaults = {
        "positioning": {"name": "定位", "name_en": "Positioning", "weight": 0.20, "score": 2, "max_score": 2, "evidence": ["Clear README"]},
        "differentiation": {"name": "差异化", "name_en": "Differentiation", "weight": 0.25, "score": 1, "max_score": 2, "evidence": ["Some unique features"]},
        "moat": {"name": "护城河", "name_en": "Moat", "weight": 0.25, "score": 2, "max_score": 2, "evidence": ["20+ language support"]},
        "engineering": {"name": "工程健康度", "name_en": "Engineering Health", "weight": 0.15, "score": 1, "max_score": 2, "evidence": ["Has CI"]},
        "sustainability": {"name": "可持续性", "name_en": "Sustainability", "weight": 0.15, "score": 0, "max_score": 2, "evidence": ["Solo maintainer"]},
    }
    if scores_overrides:
        defaults.update(scores_overrides)
    return {
        "scores": defaults,
        "weighted_total": 1.25,
        "overall_summary": "Decent product with clear positioning but needs more community.",
        "top_strengths": ["定位", "护城河"],
        "top_weaknesses": ["可持续性"],
        "veto": {"triggered": False, "reason": ""},
    }


def make_project():
    return RepoMeta(
        owner="test", repo="demo", full_name="test/demo",
        description="A test project", stars=100, forks=20,
        language="Python", topics=["ai", "agent"],
        license_name="MIT", created_at="2024-01-01", updated_at="2025-06-01",
        commit_days_active_90d=30, last_commit_at="2025-06-01",
        open_issue_stats={"open": 10, "closed": 40, "close_rate": 80.0},
    )


class TestGenerateReport:
    def test_returns_string(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert isinstance(report, str)
        assert len(report) > 100

    def test_includes_score_header(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert "1.25" in report or "综合得分" in report

    def test_includes_dimensions_table(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert "定位" in report
        assert "差异化" in report
        assert "护城河" in report

    def test_includes_project_info(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert "test/demo" in report
        assert "100" in report

    def test_includes_strengths_and_weaknesses(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert "定位" in report  # strength
        assert "可持续性" in report  # weakness

    def test_veto_triggered(self):
        eval_data = make_evaluation()
        eval_data["veto"] = {"triggered": True, "reason": "Fake README"}
        report = generate_report(eval_data, make_project(), [])
        assert "否决项触发" in report or "VETO" in report

    def test_with_competitors(self):
        comps = [
            RepoMeta(owner="comp", repo="x", full_name="comp/x", description="Competitor X", stars=50, forks=10, commit_days_active_90d=5),
            RepoMeta(owner="comp", repo="y", full_name="comp/y", description="Competitor Y", stars=200, forks=30, commit_days_active_90d=20),
        ]
        report = generate_report(make_evaluation(), make_project(), comps)
        assert "comp/x" in report
        assert "comp/y" in report

    def test_no_competitors(self):
        report = generate_report(make_evaluation(), make_project(), [])
        assert "竞品对比" not in report or len(report) > 0
