"""
tests/test_search_service.py
==============================
Unit tests for the search_service scoring and filtering logic.

All external I/O (KG, DB) is mocked — tests run fully offline.
"""
from __future__ import annotations

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from matching_pipeline_v2.search_service import (
    _required_skills,
    _build_employee_vector,
    _score_employee,
    _build_explanation,
    _score_all,
    search_employees_for_job,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_KG: dict = {
    "python":  {"fastapi": 0.90, "django": 0.80},
    "fastapi": {"python":  0.90},
    "react":   {"typescript": 0.85, "vue.js": 0.75},
}

SAMPLE_EMP = {
    "email": "alice@test.com",
    "name":  "Alice",
    "skills": [
        {"name": "Python",  "last_used": "2024-01-01", "duration_months": 24, "complexity": 3},
        {"name": "FastAPI", "last_used": "2024-01-01", "duration_months": 12, "complexity": 2},
    ],
    "knowledge_graph": {},
}

SAMPLE_JOB_DB = {
    "_id":   "job_backend_0",
    "title": "Backend Engineer",
    "required_stack": [
        {"skill": "Python",  "level": "expert"},
        {"skill": "FastAPI", "level": "intermediate"},
        {"skill": "Docker",  "level": "beginner"},
    ],
}

SAMPLE_JOB_PIPELINE = {
    "_id":             "job_backend_0",
    "title":           "Backend Engineer",
    "required_skills": ["python", "fastapi", "docker"],
}


# ---------------------------------------------------------------------------
# _required_skills
# ---------------------------------------------------------------------------

class TestRequiredSkills:
    def test_db_format(self):
        skills = _required_skills(SAMPLE_JOB_DB)
        assert skills == ["python", "fastapi", "docker"]

    def test_pipeline_format(self):
        skills = _required_skills(SAMPLE_JOB_PIPELINE)
        assert skills == ["python", "fastapi", "docker"]

    def test_deduplication(self):
        job = {"required_skills": ["Python", "python", "PYTHON"]}
        assert _required_skills(job) == ["python"]

    def test_none_entries_skipped(self):
        job = {"required_stack": [None, {"skill": "Python", "level": "expert"}, None]}
        assert _required_skills(job) == ["python"]

    def test_empty_job(self):
        assert _required_skills({}) == []


# ---------------------------------------------------------------------------
# _build_employee_vector
# ---------------------------------------------------------------------------

class TestBuildEmployeeVector:
    def test_direct_skills_present(self):
        vec = _build_employee_vector(SAMPLE_EMP, SAMPLE_KG)
        assert "python" in vec
        assert "fastapi" in vec
        assert vec["python"] > 0
        assert vec["fastapi"] > 0

    def test_bfs_infers_django_from_python(self):
        vec = _build_employee_vector(SAMPLE_EMP, SAMPLE_KG)
        # django is a 1-hop neighbour of python (weight 0.8)
        assert "django" in vec
        assert vec["django"] > 0

    def test_scores_clamped_positive(self):
        vec = _build_employee_vector(SAMPLE_EMP, SAMPLE_KG)
        assert all(v >= 0 for v in vec.values())

    def test_empty_skills(self):
        emp = {"email": "x@x.com", "skills": [], "knowledge_graph": {}}
        vec = _build_employee_vector(emp, SAMPLE_KG)
        assert vec == {}


# ---------------------------------------------------------------------------
# _score_employee
# ---------------------------------------------------------------------------

class TestScoreEmployee:
    def test_perfect_direct_match(self):
        required = ["python", "fastapi"]
        result = _score_employee(SAMPLE_EMP, required, SAMPLE_KG)
        assert result["matching_score"] > 0
        assert "python"  in result["matched_skills"]
        assert "fastapi" in result["matched_skills"]
        assert result["missing_skills"] == []

    def test_partial_match_has_missing(self):
        required = ["python", "fastapi", "docker"]
        result = _score_employee(SAMPLE_EMP, required, SAMPLE_KG)
        assert "docker" in result["missing_skills"]

    def test_inferred_via_kg(self):
        required = ["django"]
        result = _score_employee(SAMPLE_EMP, required, SAMPLE_KG)
        # django is reachable from python via KG → inferred, not matched
        assert "django" in result["inferred_skills"]
        assert result["matching_score"] > 0

    def test_no_required_skills_returns_zero(self):
        result = _score_employee(SAMPLE_EMP, [], SAMPLE_KG)
        assert result["matching_score"] == 0.0

    def test_score_in_range(self):
        required = ["python", "fastapi", "docker"]
        result = _score_employee(SAMPLE_EMP, required, SAMPLE_KG)
        assert 0.0 <= result["matching_score"] <= 1.0

    def test_score_formula_bfs_job_vector(self):
        """Score uses BFS-expanded job vector clipped to [0, 1]; verify formula."""
        from matching_pipeline_v2.search_service import _build_job_vector
        required = ["python"]
        job_vec  = _build_job_vector(required, SAMPLE_KG)
        emp_vec  = _build_employee_vector(SAMPLE_EMP, SAMPLE_KG)
        dot  = sum(emp_vec.get(s, 0.0) * c for s, c in job_vec.items())
        norm = math.sqrt(sum(c ** 2 for c in job_vec.values()))
        # clip matches old pipeline's np.clip(adequacy, 0.0, 1.0)
        expected = round(min(max(dot / norm, 0.0), 1.0), 4) if norm > 0 else 0.0
        result   = _score_employee(SAMPLE_EMP, required, SAMPLE_KG)
        assert result["matching_score"] == expected


# ---------------------------------------------------------------------------
# _build_explanation
# ---------------------------------------------------------------------------

class TestBuildExplanation:
    def _base_result(self) -> dict:
        return _score_employee(SAMPLE_EMP, ["python", "fastapi", "docker"], SAMPLE_KG)

    def test_contains_employee_name(self):
        r   = self._base_result()
        txt = _build_explanation(
            SAMPLE_EMP, "Backend Engineer", r["matching_score"],
            r["matched_skills"], r["inferred_skills"], r["missing_skills"],
            SAMPLE_KG,
        )
        assert "Alice" in txt

    def test_contains_recommendation_label(self):
        r   = self._base_result()
        txt = _build_explanation(
            SAMPLE_EMP, "Backend Engineer", r["matching_score"],
            r["matched_skills"], r["inferred_skills"], r["missing_skills"],
            SAMPLE_KG,
        )
        assert any(lbl in txt for lbl in ("HIRE", "CONSIDER", "PASS", "STRONG HIRE"))

    def test_gaps_mentioned_when_present(self):
        r   = self._base_result()
        txt = _build_explanation(
            SAMPLE_EMP, "Backend Engineer", r["matching_score"],
            r["matched_skills"], r["inferred_skills"], r["missing_skills"],
            SAMPLE_KG,
        )
        if r["missing_skills"]:
            assert "Gap" in txt or "gap" in txt

    def test_pass_for_zero_score(self):
        txt = _build_explanation(
            SAMPLE_EMP, "SomeJob", 0.0, [], [], ["haskell", "erlang"], SAMPLE_KG,
        )
        assert "PASS" in txt


# ---------------------------------------------------------------------------
# _score_all
# ---------------------------------------------------------------------------

class TestScoreAll:
    def test_returns_sorted_by_score(self):
        employees = [
            {**SAMPLE_EMP},
            {"email": "bob@test.com", "name": "Bob", "skills": [], "knowledge_graph": {}},
        ]
        required = ["python", "fastapi"]
        results  = _score_all(employees, SAMPLE_JOB_DB, required)
        scores   = [r["matching_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_result_keys_present(self):
        results = _score_all([SAMPLE_EMP], SAMPLE_JOB_DB, ["python"])
        r = results[0]
        for key in ("id", "name", "email", "employee_id", "employee_name",
                    "matching_score", "matched_skills", "inferred_skills",
                    "missing_skills", "explanation"):
            assert key in r, f"Missing key: {key}"

    def test_explanation_is_nonempty_string(self):
        results = _score_all([SAMPLE_EMP], SAMPLE_JOB_DB, ["python"])
        assert isinstance(results[0]["explanation"], str)
        assert len(results[0]["explanation"]) > 0


# ---------------------------------------------------------------------------
# search_employees_for_job  (async, DB mocked)
# ---------------------------------------------------------------------------

class TestSearchEmployeesForJob:
    @pytest.mark.asyncio
    async def test_filters_unavailable_employees(self):
        available_emp = {**SAMPLE_EMP, "available": True}
        job = {**SAMPLE_JOB_DB}

        with patch("db.operations.get_job",             new=AsyncMock(return_value=job)), \
             patch("db.operations.list_employees",       new=AsyncMock(return_value=[available_emp])), \
             patch("db.operations.get_project_assigned_employee_ids",
                   new=AsyncMock(return_value=set())), \
             patch("matching_pipeline_v2.search_service._get_kg", return_value=SAMPLE_KG):

            results = await search_employees_for_job("job_backend_0", "proj_x")

        assert len(results) == 1
        assert results[0]["employee_id"] == "alice@test.com"

    @pytest.mark.asyncio
    async def test_excludes_already_assigned(self):
        available_emp = {**SAMPLE_EMP, "available": True}
        job = {**SAMPLE_JOB_DB}

        with patch("db.operations.get_job",             new=AsyncMock(return_value=job)), \
             patch("db.operations.list_employees",       new=AsyncMock(return_value=[available_emp])), \
             patch("db.operations.get_project_assigned_employee_ids",
                   new=AsyncMock(return_value={"alice@test.com"})), \
             patch("matching_pipeline_v2.search_service._get_kg", return_value=SAMPLE_KG):

            results = await search_employees_for_job("job_backend_0", "proj_x")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_job(self):
        with patch("db.operations.get_job", new=AsyncMock(return_value=None)):
            results = await search_employees_for_job("no_such_job", "proj_x")
        assert results == []

    @pytest.mark.asyncio
    async def test_score_percentage_added(self):
        available_emp = {**SAMPLE_EMP, "available": True}
        job = {**SAMPLE_JOB_DB}

        with patch("db.operations.get_job",             new=AsyncMock(return_value=job)), \
             patch("db.operations.list_employees",       new=AsyncMock(return_value=[available_emp])), \
             patch("db.operations.get_project_assigned_employee_ids",
                   new=AsyncMock(return_value=set())), \
             patch("matching_pipeline_v2.search_service._get_kg", return_value=SAMPLE_KG):

            results = await search_employees_for_job("job_backend_0", "proj_x")

        assert "score_percentage" in results[0]
        assert results[0]["score_percentage"] == round(results[0]["matching_score"] * 100)

    @pytest.mark.asyncio
    async def test_respects_exclude_ids(self):
        available_emp = {**SAMPLE_EMP, "available": True}
        job = {**SAMPLE_JOB_DB}

        with patch("db.operations.get_job",             new=AsyncMock(return_value=job)), \
             patch("db.operations.list_employees",       new=AsyncMock(return_value=[available_emp])), \
             patch("db.operations.get_project_assigned_employee_ids",
                   new=AsyncMock(return_value=set())), \
             patch("matching_pipeline_v2.search_service._get_kg", return_value=SAMPLE_KG):

            results = await search_employees_for_job(
                "job_backend_0", "proj_x",
                exclude_ids={"alice@test.com"},
            )

        assert results == []
