"""Tests for modules/evaluator/rubric.py"""
import json
import pytest

from modules.evaluator.rubric import (
    DIMENSIONS,
    _parse_result,
    _fallback_parse,
    _build_prompt,
    SYSTEM_PROMPT,
)
from modules.evaluator.collector import RepoMeta


class TestDimensions:
    def test_five_dimensions(self):
        assert len(DIMENSIONS) == 5

    def test_weights_sum_to_one(self):
        total = sum(d["weight"] for d in DIMENSIONS.values())
        assert abs(total - 1.0) < 0.01

    def test_each_dimension_has_required_fields(self):
        for key, dim in DIMENSIONS.items():
            assert "name" in dim
            assert "name_en" in dim
            assert "weight" in dim
            assert "definition" in dim
            assert "scoring" in dim
            assert "0" in dim["scoring"]
            assert "1" in dim["scoring"]
            assert "2" in dim["scoring"]

    def test_dimension_keys(self):
        expected = {"positioning", "differentiation", "moat", "engineering", "sustainability"}
        assert set(DIMENSIONS.keys()) == expected


class TestParseResult:
    def test_valid_json(self):
        json_str = json.dumps({
            "scores": {
                "positioning": {"score": 2, "evidence": ["Clear README"]},
                "differentiation": {"score": 1, "evidence": ["Some unique features"]},
                "moat": {"score": 2, "evidence": ["Hard to replicate"]},
                "engineering": {"score": 1, "evidence": ["Has CI"]},
                "sustainability": {"score": 0, "evidence": ["Solo maintainer"]},
            },
            "overall_summary": "Good but needs community",
            "top_strengths": ["positioning", "moat"],
            "top_weaknesses": ["sustainability"],
            "veto": {"triggered": False, "reason": ""},
        })
        result = _parse_result(json_str, DIMENSIONS)
        assert result["weighted_total"] > 0
        assert len(result["scores"]) == 5
        assert result["scores"]["positioning"]["score"] == 2
        assert result["veto"]["triggered"] is False

    def test_json_wrapped_in_text(self):
        json_str = 'Here is my evaluation:\n```json\n{"scores":{"positioning":{"score":1,"evidence":["ok"]},"differentiation":{"score":0,"evidence":[]},"moat":{"score":1,"evidence":[]},"engineering":{"score":0,"evidence":[]},"sustainability":{"score":0,"evidence":[]}},"overall_summary":"test","top_strengths":[],"top_weaknesses":[],"veto":{"triggered":false,"reason":""}}\n```\nDone.'
        result = _parse_result(json_str, DIMENSIONS)
        assert len(result["scores"]) == 5
        assert result["veto"]["triggered"] is False

    def test_invalid_json_falls_back(self):
        result = _parse_result("This is not JSON at all", DIMENSIONS)
        assert len(result["scores"]) == 5
        assert result["overall_summary"] != ""

    def test_missing_dimensions_default_to_zero(self):
        json_str = json.dumps({"scores": {}, "overall_summary": "", "top_strengths": [], "top_weaknesses": [], "veto": {"triggered": False, "reason": ""}})
        result = _parse_result(json_str, DIMENSIONS)
        for dim in result["scores"].values():
            assert dim["score"] == 0


class TestBuildPrompt:
    def test_includes_project_info(self):
        meta = RepoMeta(
            owner="test", repo="demo", full_name="test/demo",
            description="A test project", stars=100, language="Python",
        )
        prompt = _build_prompt(meta, [])
        assert "test/demo" in prompt
        assert "A test project" in prompt
        assert "Stars" in prompt

    def test_includes_competitors(self):
        meta = RepoMeta(owner="test", repo="demo", full_name="test/demo")
        comp = RepoMeta(owner="comp", repo="x", full_name="comp/x", description="Competitor", stars=50)
        prompt = _build_prompt(meta, [comp])
        assert "comp/x" in prompt
        assert "Competitor" in prompt

    def test_no_readme_placeholder(self):
        meta = RepoMeta(owner="test", repo="demo", full_name="test/demo")
        prompt = _build_prompt(meta, [])
        assert "(无 README)" in prompt


class TestSystemPrompt:
    def test_contains_output_format(self):
        assert "scores" in SYSTEM_PROMPT
        assert "overall_summary" in SYSTEM_PROMPT
        assert "veto" in SYSTEM_PROMPT

    def test_contains_scoring_rules(self):
        assert "宁低勿高" in SYSTEM_PROMPT
        assert "2 分" in SYSTEM_PROMPT
        assert "1 分" in SYSTEM_PROMPT
        assert "0 分" in SYSTEM_PROMPT
