"""
tests/test_validation_agent.py
================================
Unit tests for the Validation Agent tools (pure Python, no LLM).

analyze_assignment_quality and structure_adjustment_report are called
directly without any A2A server or LangGraph.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from matching_pipeline_v2.validation_agent import tools as val_tools
from matching_pipeline_v2.validation_agent.tools import (
    analyze_assignment_quality,
    structure_adjustment_report,
)


def _set_ctx(assignments=None, jobs=None, kg=None, score_details=None):
    val_tools._ctx.clear()
    val_tools._ctx.update({
        "assignments":            assignments or [],
        "jobs":                   jobs or [],
        "global_knowledge_graph": kg or {},
        "score_details":          score_details or [],
    })


# ---------------------------------------------------------------------------
# analyze_assignment_quality
# ---------------------------------------------------------------------------

class TestAnalyzeAssignmentQuality:
    def test_no_assignments_returns_zero_avg(self):
        _set_ctx(assignments=[], jobs=[])
        result = json.loads(analyze_assignment_quality.func())
        assert result["avg_score"] == 0.0
        assert result["overall_quality"] == "no_assignments"

    def test_good_assignments_finalize_worthy(self, sample_assignments, sample_jobs, sample_kg):
        _set_ctx(
            assignments=[
                {**a, "employee_email": a["employee_email"],
                 "score": a["score"],
                 "matched_skills": a["matched_skills"],
                 "missing_skills": a["missing_skills"]}
                for a in sample_assignments
            ],
            jobs=sample_jobs,
            kg=sample_kg,
        )
        result = json.loads(analyze_assignment_quality.func())
        assert "avg_score" in result
        assert result["avg_score"] >= 0.0

    def test_returns_collective_gaps_key(self, sample_jobs, sample_kg):
        assignments = [
            {"employee_email": "a@b.com", "job_id": sample_jobs[0]["job_id"],
             "score": 0.3, "matched_skills": [], "missing_skills": ["python", "docker"]},
        ]
        _set_ctx(assignments=assignments, jobs=sample_jobs, kg=sample_kg)
        result = json.loads(analyze_assignment_quality.func())
        assert "collective_gaps" in result


# ---------------------------------------------------------------------------
# structure_adjustment_report
# ---------------------------------------------------------------------------

class TestStructureAdjustmentReport:
    def _make_xai_report(self, avg_score=0.4) -> str:
        return json.dumps({
            "avg_score":       avg_score,
            "collective_gaps": {"job_backend_0": ["kubernetes", "terraform"]},
            "job_reports": [
                {
                    "job_id":            "job_backend_0",
                    "collective_gaps":   ["kubernetes"],
                    "assignments": [
                        {"employee_email": "a@b.com", "score": 0.4,
                         "missing_skills": ["kubernetes"], "semantic_gaps": []},
                    ],
                }
            ],
        })

    def test_returns_valid_json(self):
        val_tools._ctx.clear()
        result_str = structure_adjustment_report.func(self._make_xai_report())
        result     = json.loads(result_str)
        assert "recommended_alpha" in result
        assert "gap_priorities_per_job" in result

    def test_invalid_input_returns_error(self):
        val_tools._ctx.clear()
        result = json.loads(structure_adjustment_report.func("NOT JSON"))
        assert "error" in result

    def test_alpha_increases_with_worse_gaps(self):
        low_gap  = json.loads(structure_adjustment_report.func(self._make_xai_report(avg_score=0.7)))
        high_gap = json.loads(structure_adjustment_report.func(self._make_xai_report(avg_score=0.2)))
        # Worse average score → higher recommended alpha (more aggressive boost)
        assert high_gap.get("recommended_alpha", 0) >= low_gap.get("recommended_alpha", 0)
