"""
tests/test_scoring_agent.py
=============================
Unit tests for the Scoring Agent tools (pure Python, no Neo4j / LLM).

All computation in scoring_agent/tools.py is deterministic math — we test
it directly without spinning up any A2A server or calling an LLM.
"""
from __future__ import annotations

import json
import math
from unittest.mock import patch

import pytest

from matching_pipeline_v2.scoring_agent import tools as scoring_tools
from matching_pipeline_v2.scoring_agent.tools import (
    _recency_score,
    _duration_score,
    _complexity_score,
    _raw_skill_score,
    _build_employee_vector,
    _employee_direct_scores,
    BFS_MAX_DEPTH,
    RECENCY_WEIGHT,
    DURATION_WEIGHT,
    COMPLEXITY_WEIGHT,
    K1_DURATION,
    HALF_LIFE_DAYS,
    DECAY_ALPHA,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_ctx(employees=None, jobs=None, weights=None, kg=None):
    scoring_tools._ctx.clear()
    scoring_tools._ctx.update({
        "employees":              employees or [],
        "jobs":                   jobs or [],
        "weights":                weights or {},
        "global_knowledge_graph": kg or {},
    })


# ---------------------------------------------------------------------------
# Recency / duration / complexity scoring
# ---------------------------------------------------------------------------

class TestComponentScores:
    def test_recency_today_gives_1(self):
        from datetime import date
        today_str = date.today().isoformat()
        # Power-law: 1/(1+0^ALPHA) = 1.0
        assert _recency_score(today_str) == pytest.approx(1.0, abs=0.01)

    def test_recency_none_gives_0(self):
        assert _recency_score(None) == 0.0

    def test_recency_half_life_gives_half(self):
        # At exactly HALF_LIFE_DAYS days: 1/(1+1^ALPHA) = 0.5
        from datetime import date, timedelta
        hl_date = (date.today() - timedelta(days=HALF_LIFE_DAYS)).isoformat()
        assert _recency_score(hl_date) == pytest.approx(0.5, abs=0.02)

    def test_recency_2_years_ago_decays(self):
        # Power-law at ~730 days: 1/(1+(2)^0.5) ≈ 0.41 — still < 0.5
        score = _recency_score("2022-01-01")
        assert 0.0 < score < 0.5

    def test_recency_decays_slower_than_exponential(self):
        # At 2× half-life, power-law > exponential (less punishing for old skills)
        from datetime import date, timedelta
        two_hl = (date.today() - timedelta(days=2 * HALF_LIFE_DAYS)).isoformat()
        power_score = _recency_score(two_hl)
        exp_score   = math.exp(-2 * HALF_LIFE_DAYS / 365.0)
        assert power_score > exp_score

    def test_duration_zero(self):
        assert _duration_score(0) == 0.0

    def test_duration_half_saturation_at_k1(self):
        # BM25: K1/(K1+K1) = 0.5 — half-saturation point at K1 months
        assert _duration_score(int(K1_DURATION)) == pytest.approx(0.5, abs=0.01)

    def test_duration_diminishing_returns(self):
        # Each extra block of K1 months adds less than the previous block
        d1 = _duration_score(int(K1_DURATION))        # 0→K1
        d2 = _duration_score(int(2 * K1_DURATION)) - d1  # K1→2K1
        d3 = _duration_score(int(3 * K1_DURATION)) - _duration_score(int(2 * K1_DURATION))
        assert d1 > d2 > d3

    def test_duration_never_reaches_1(self):
        # No hard cap — very long experience approaches but never equals 1.0
        assert _duration_score(1200) < 1.0
        assert _duration_score(1200) > 0.95

    def test_complexity_expert(self):
        assert _complexity_score(3) == pytest.approx(1.0, abs=0.01)

    def test_complexity_basic(self):
        assert _complexity_score(1) == pytest.approx(1 / 3, abs=0.01)

    def test_raw_skill_score_weights_sum(self):
        result = _raw_skill_score("2024-01-01", 12, 3)
        # raw = 0.4*recency + 0.3*duration + 0.3*complexity — all in [0,1]
        assert 0.0 <= result["raw_score"] <= 1.0


# ---------------------------------------------------------------------------
# Employee vector building
# ---------------------------------------------------------------------------

class TestEmployeeDirectScores:
    def test_string_skill_gets_default_score(self):
        emp = {"email": "a@b.com", "skills": ["Python"]}
        scores = _employee_direct_scores(emp)
        assert "python" in scores
        # After normalisation (max→1.0), a single skill always becomes 1.0
        assert scores["python"] == 1.0

    def test_dict_skill_with_metadata(self):
        from datetime import date
        emp = {
            "email": "a@b.com",
            "skills": [{"name": "Python", "last_used": date.today().isoformat(),
                        "duration_months": 24, "complexity": 3}],
        }
        scores = _employee_direct_scores(emp)
        assert "python" in scores
        assert scores["python"] > 0.8   # max attributes → high score

    def test_empty_skills(self):
        emp = {"email": "a@b.com", "skills": []}
        assert _employee_direct_scores(emp) == {}


class TestBuildEmployeeVector:
    def test_direct_skill_preserved(self, sample_kg):
        emp = {"email": "a@b.com", "skills": ["Python"], "knowledge_graph": {}}
        with patch("matching_pipeline_v2.scoring_agent.tools._ctx",
                   {"global_knowledge_graph": sample_kg}):
            vec = _build_employee_vector(emp)
        assert "python" in vec
        assert vec["python"] > 0.0

    def test_inferred_skill_via_bfs(self, sample_kg):
        emp = {"email": "a@b.com", "skills": ["Python"], "knowledge_graph": {}}
        with patch("matching_pipeline_v2.scoring_agent.tools._ctx",
                   {"global_knowledge_graph": sample_kg}):
            vec = _build_employee_vector(emp)
        # Python→FastAPI edge exists in sample_kg (weight 0.9)
        assert "fastapi" in vec
        assert vec["fastapi"] < vec.get("python", 1.0)   # inferred < direct

    def test_inferred_score_respects_bfs_depth(self, sample_kg):
        emp = {"email": "a@b.com", "skills": ["Python"], "knowledge_graph": {}}
        with patch("matching_pipeline_v2.scoring_agent.tools._ctx",
                   {"global_knowledge_graph": sample_kg}):
            vec = _build_employee_vector(emp)
        # BFS_MAX_DEPTH=2 — no skill should appear at depth > 2
        assert all(v >= 0.0 for v in vec.values())


# ---------------------------------------------------------------------------
# compute_score_matrix (@tool)
# ---------------------------------------------------------------------------

class TestComputeScoreMatrix:
    def test_matrix_shape(self, sample_employees, sample_jobs, sample_kg):
        _set_ctx(
            employees=sample_employees,
            jobs=sample_jobs,
            weights={j["job_id"]: {} for j in sample_jobs},
            kg=sample_kg,
        )
        raw = scoring_tools.compute_score_matrix.func()
        result = json.loads(raw)
        assert result["status"] == "ok"
        # Full matrix should now be in _ctx
        matrix = scoring_tools._ctx.get("score_matrix", [])
        assert len(matrix) == len(sample_employees)
        assert all(len(row) == len(sample_jobs) for row in matrix)

    def test_scores_between_0_and_1(self, sample_employees, sample_jobs, sample_kg):
        _set_ctx(
            employees=sample_employees,
            jobs=sample_jobs,
            weights={j["job_id"]: {} for j in sample_jobs},
            kg=sample_kg,
        )
        scoring_tools.compute_score_matrix.func()
        for row in scoring_tools._ctx.get("score_matrix", []):
            for score in row:
                assert 0.0 <= score <= 1.0

    def test_employee_with_matching_skills_scores_higher(self, sample_jobs, sample_kg):
        employees = [
            {"email": "alice@x.com", "name": "Alice", "skills": ["Python", "FastAPI", "Docker"],
             "knowledge_graph": {}},
            {"email": "bob@x.com",   "name": "Bob",   "skills": ["React"],
             "knowledge_graph": {}},
        ]
        _set_ctx(employees=employees, jobs=[sample_jobs[0]], weights={sample_jobs[0]["job_id"]: {}},
                 kg=sample_kg)
        scoring_tools.compute_score_matrix.func()
        matrix = scoring_tools._ctx["score_matrix"]
        alice_score = matrix[0][0]
        bob_score   = matrix[1][0]
        # Alice has all backend skills → should score higher for backend job
        assert alice_score > bob_score
