"""
tests/test_orchestrator.py
============================
Unit tests for the matching_pipeline_v2 orchestrator (deterministic version).

The orchestrator is now plain Python: it calls A2A sub-agents in a fixed
sequence and runs the Hungarian algorithm locally.  All A2A calls are
mocked so tests run offline.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import matching_pipeline_v2.orchestrator as orch_mod
from matching_pipeline_v2.orchestrator import (
    _state,
    _step_hungarian,
    _step_scorer,
    _step_validator,
    _step_explanation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_state():
    _state.clear()
    _state.update({
        "employees":              [],
        "jobs":                   [],
        "global_knowledge_graph": {},
        "explanations":           [],
        "assignments":            [],
        "weights":                {},
    })


def _make_score_matrix(n_emp: int, n_jobs: int, value: float = 0.7) -> list[list[float]]:
    return [[value] * n_jobs for _ in range(n_emp)]


# ---------------------------------------------------------------------------
# _step_hungarian  (local — no mocking needed)
# ---------------------------------------------------------------------------

class TestStepHungarian:
    def test_no_score_matrix_returns_false(self):
        _reset_state()
        ok = _step_hungarian()
        assert ok is False

    def test_assigns_each_employee_to_one_job(self, sample_employees, sample_jobs):
        _reset_state()
        _state["employees"] = sample_employees[:2]
        _state["jobs"]      = sample_jobs
        _state["score_matrix"]  = _make_score_matrix(2, 2, value=0.8)
        _state["score_details"] = []

        ok = _step_hungarian()
        assert ok is True
        assignments = _state.get("assignments", [])
        assert len(assignments) == 2
        # No employee assigned twice
        emails = [a["employee_email"] for a in assignments]
        assert len(emails) == len(set(emails))

    def test_scores_clamped_between_0_and_1(self, sample_employees, sample_jobs):
        _reset_state()
        _state["employees"]    = sample_employees[:1]
        _state["jobs"]         = sample_jobs[:1]
        _state["score_matrix"] = [[1.5]]   # deliberately out of range
        _state["score_details"] = []

        _step_hungarian()
        for a in _state["assignments"]:
            assert 0.0 <= a["score"] <= 1.0

    def test_multi_post_job_creates_multiple_assignments(self, sample_employees, sample_jobs):
        """A job with headcount=2 should accept two employees."""
        _reset_state()
        _state["employees"] = sample_employees[:3]
        # First job has headcount=2
        jobs = [{**sample_jobs[0], "headcount": 2}, sample_jobs[1]]
        _state["jobs"]          = jobs
        _state["score_matrix"]  = _make_score_matrix(3, 2, value=0.8)
        _state["score_details"] = []

        _step_hungarian()
        assignments = _state["assignments"]
        # Both slots of job 0 + one of job 1 = 3 assignments
        assert len(assignments) == 3
        # job_0 should appear twice (different employees)
        job0_assignees = [a["employee_email"] for a in assignments if a["job_id"] == jobs[0]["job_id"]]
        assert len(job0_assignees) == 2
        assert len(set(job0_assignees)) == 2  # different employees


# ---------------------------------------------------------------------------
# _step_scorer  (mocks A2A)
# ---------------------------------------------------------------------------

class TestStepScorer:
    def test_stores_score_matrix_in_state(self, sample_employees, sample_jobs, sample_kg):
        _reset_state()
        _state["employees"]              = sample_employees
        _state["jobs"]                   = sample_jobs
        _state["global_knowledge_graph"] = sample_kg
        _state["weights"]                = {j["job_id"]: {} for j in sample_jobs}

        fake_response = {
            "score_matrix": _make_score_matrix(3, 2),
            "details":      [],
            "summary":      {"n_employees": 3, "n_jobs": 2, "avg_score": 0.7, "max_score": 0.9},
        }

        with patch.object(orch_mod, "_a2a_call", return_value=fake_response):
            ok = _step_scorer()

        assert ok is True
        assert len(_state["score_matrix"]) == 3

    def test_error_response_returns_false(self):
        _reset_state()
        _state.update({"employees": [], "jobs": [], "global_knowledge_graph": {}, "weights": {}})
        with patch.object(orch_mod, "_a2a_call", return_value={"error": "timeout"}):
            ok = _step_scorer()
        assert ok is False


# ---------------------------------------------------------------------------
# _step_validator  (mocks A2A)
# ---------------------------------------------------------------------------

class TestStepValidator:
    def test_finalize_decision_stored(self):
        _reset_state()
        _state["assignments"] = [{"employee_email": "a@b.com", "job_id": "j1", "score": 0.85}]
        _state["jobs"]        = [{"job_id": "j1", "required_skills": []}]

        finalize_response = {"decision": "finalize", "avg_score": 0.85, "reasoning": "Good"}
        with patch.object(orch_mod, "_a2a_call", return_value=finalize_response):
            decision = _step_validator()
        assert decision == "finalize"
        assert _state["decision"] == "finalize"

    def test_adjust_decision_stores_adjustment_report(self):
        _reset_state()
        _state["assignments"] = [{"employee_email": "a@b.com", "job_id": "j1", "score": 0.35}]
        _state["jobs"]        = [{"job_id": "j1", "required_skills": ["python"]}]

        adjust_response = {
            "decision":          "adjust",
            "avg_score":         0.35,
            "reasoning":         "Low",
            "adjustment_report": {"recommended_alpha": 0.5},
        }
        with patch.object(orch_mod, "_a2a_call", return_value=adjust_response):
            decision = _step_validator()
        assert decision == "adjust"
        assert _state.get("adjustment_report") is not None

    def test_error_defaults_to_finalize(self):
        _reset_state()
        _state["assignments"] = []
        _state["jobs"]        = []
        with patch.object(orch_mod, "_a2a_call", return_value={"error": "boom"}):
            decision = _step_validator()
        assert decision == "finalize"


# ---------------------------------------------------------------------------
# run_pipeline (end-to-end deterministic — A2A all mocked)
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def _build_a2a_mock(self, n_emp: int, n_jobs: int):
        score_response = {
            "score_matrix": _make_score_matrix(n_emp, n_jobs, 0.75),
            "details":      [],
            "summary":      {"n_employees": n_emp, "n_jobs": n_jobs,
                             "avg_score": 0.75, "max_score": 0.90},
        }
        validator_response = {
            "decision":   "finalize",
            "avg_score":  0.75,
            "reasoning":  "Most assignments cover the core skills.",
            "xai_report": {},
        }
        explanation_response = {
            "explanations": [
                {
                    "employee_email":  "alice@example.com",
                    "employee_name":   "Alice Martin",
                    "job_id":          "job_backend_0",
                    "job_title":       "Backend Engineer",
                    "recommendation":  "hire",
                    "summary":         "Strong fit. VERDICT: Hire.",
                }
            ]
        }

        def fake_a2a(url, payload):
            if "8101" in url:  return score_response
            if "8102" in url:  return validator_response
            if "8104" in url:  return explanation_response
            return {}

        return fake_a2a

    def test_pipeline_returns_assignments(self, sample_employees, sample_jobs, sample_kg):
        from matching_pipeline_v2.orchestrator import run_pipeline

        fake_a2a = self._build_a2a_mock(len(sample_employees), len(sample_jobs))
        with patch.object(orch_mod, "_a2a_call", side_effect=fake_a2a):
            summary_text, assignments = run_pipeline(
                employees=sample_employees,
                jobs=sample_jobs,
                global_knowledge_graph=sample_kg,
            )

        assert isinstance(summary_text, str)
        assert isinstance(assignments, list)
        # Summary is parseable JSON with the expected keys
        summary = json.loads(summary_text)
        assert "iterations" in summary
        assert "n_assignments" in summary
        assert "decision" in summary
        assert summary["decision"] == "finalize"

    def test_pipeline_stops_on_finalize(self, sample_employees, sample_jobs, sample_kg):
        """When validator returns finalize on iteration 1, no further iterations."""
        from matching_pipeline_v2.orchestrator import run_pipeline

        fake_a2a = self._build_a2a_mock(len(sample_employees), len(sample_jobs))
        with patch.object(orch_mod, "_a2a_call", side_effect=fake_a2a):
            summary_text, _ = run_pipeline(
                employees=sample_employees,
                jobs=sample_jobs,
                global_knowledge_graph=sample_kg,
            )

        summary = json.loads(summary_text)
        assert summary["iterations"] == 1
