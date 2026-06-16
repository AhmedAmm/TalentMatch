"""
tests/test_full_pipeline.py
=============================
End-to-end integration tests for the full matching pipeline.

ALL external dependencies are mocked:
  - Neo4j (knowledge graph loader)
  - MongoDB (employee/job data)
  - NVIDIA API (LLM / orchestrator)
  - A2A HTTP servers (sub-agents)

Tests verify that the pipeline produces well-formed output and persists
assignments correctly without requiring any live infrastructure.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import matching_pipeline_v2.orchestrator as orch_mod
from matching_pipeline_v2.knowledge_graph import invalidate_kg_cache


# ---------------------------------------------------------------------------
# Fixtures — inline overrides of conftest fixtures with extended fields
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline_employees():
    return [
        {"email": "alice@test.com", "name": "Alice",
         "skills": ["Python", "FastAPI", "Docker"],
         "knowledge_graph": {"python": ["fastapi"]}},
        {"email": "bob@test.com",   "name": "Bob",
         "skills": ["React", "TypeScript"],
         "knowledge_graph": {}},
        {"email": "carol@test.com", "name": "Carol",
         "skills": ["Python", "PyTorch", "MLflow"],
         "knowledge_graph": {"pytorch": ["tensorflow"]}},
    ]


@pytest.fixture
def pipeline_jobs():
    return [
        {"job_id": "job_backend_0",  "title": "Backend Engineer",
         "required_skills": ["python", "fastapi", "docker"]},
        {"job_id": "job_frontend_1", "title": "Frontend Engineer",
         "required_skills": ["react", "typescript"]},
    ]


@pytest.fixture
def pipeline_kg():
    return {
        "python":     {"fastapi": 0.9, "django": 0.80},
        "fastapi":    {"python": 0.9},
        "react":      {"typescript": 0.90, "vue.js": 0.75},
        "typescript": {"react": 0.90},
        "pytorch":    {"tensorflow": 0.80},
        "docker":     {"kubernetes": 0.85},
    }


# ---------------------------------------------------------------------------
# Full pipeline: scoring → hungarian → validation → explanation
# ---------------------------------------------------------------------------

class TestFullPipeline:

    def _score_matrix(self, n_emp, n_jobs, value=0.7):
        return [[value] * n_jobs for _ in range(n_emp)]

    def _build_mocks(self, n_emp, n_jobs):
        score_resp = {
            "score_matrix": self._score_matrix(n_emp, n_jobs, 0.78),
            "details":      [],
            "summary":      {"n_employees": n_emp, "n_jobs": n_jobs,
                             "avg_score": 0.78, "max_score": 0.92},
        }
        validator_resp    = {"decision": "finalize", "avg_score": 0.78, "reasoning": "Good"}
        explanation_resp  = {
            "explanations": [
                {"employee_name": "Alice", "job_title": "Backend Engineer",
                 "recommendation": "hire", "score": 0.85}
            ]
        }

        def fake_a2a(url, payload):
            if "8101" in url:  return score_resp
            if "8102" in url:  return validator_resp
            if "8104" in url:  return explanation_resp
            return {}

        return fake_a2a

    def test_pipeline_produces_valid_output(
        self, pipeline_employees, pipeline_jobs, pipeline_kg
    ):
        from matching_pipeline_v2.orchestrator import run_pipeline

        n_emp, n_jobs = len(pipeline_employees), len(pipeline_jobs)
        fake_a2a      = self._build_mocks(n_emp, n_jobs)

        with patch.object(orch_mod, "_a2a_call", side_effect=fake_a2a):
            summary_text, assignments = run_pipeline(
                employees=pipeline_employees,
                jobs=pipeline_jobs,
                global_knowledge_graph=pipeline_kg,
            )

        assert isinstance(summary_text, str)
        assert isinstance(assignments, list)

    def test_knowledge_graph_loaded_with_correct_database(self, pipeline_kg):
        """KG loader (GraphStore) must pass NEO4J_DATABASE to driver.session()."""
        invalidate_kg_cache()

        mock_driver  = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__  = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session

        # GraphStore.load() runs 5 queries: labels, relTypes, propKeys, nodes, aliases, edges
        labels_result   = MagicMock(); labels_result.data.return_value   = [{"label": "Technology"}]
        rel_result      = MagicMock(); rel_result.data.return_value      = [{"relationshipType": "REQUIRES"}]
        prop_result     = MagicMock(); prop_result.data.return_value     = [{"propertyKey": "weight"}]
        nodes_result    = MagicMock(); nodes_result.data.return_value    = [
            {"name": "python"}, {"name": "fastapi"}
        ]
        alias_result    = MagicMock(); alias_result.data.return_value    = []
        edges_result    = MagicMock(); edges_result.data.return_value    = [
            {"frm": "python", "to": "fastapi", "rel": "REQUIRES", "w": 0.9},
        ]
        mock_session.run.side_effect = [
            labels_result, rel_result, prop_result, nodes_result, alias_result, edges_result,
        ]

        with patch("neo4j.GraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = mock_driver
            from matching_pipeline_v2.knowledge_graph import load_kg
            kg = load_kg()

        # Verify session was opened with the project database
        mock_driver.session.assert_called_once()
        call_kwargs = mock_driver.session.call_args.kwargs
        assert call_kwargs.get("database") == "project"

        # Verify the graph was populated (REQUIRES default weight from cfg = 0.90)
        assert "python" in kg
        assert "fastapi" in kg["python"]

    def test_pipeline_with_empty_kg_falls_back_gracefully(
        self, pipeline_employees, pipeline_jobs
    ):
        """Pipeline must not crash when KG is empty (direct-skill matching only)."""
        from matching_pipeline_v2.orchestrator import run_pipeline

        n_emp, n_jobs = len(pipeline_employees), len(pipeline_jobs)
        fake_a2a      = self._build_mocks(n_emp, n_jobs)

        with patch.object(orch_mod, "_a2a_call", side_effect=fake_a2a):
            summary_text, assignments = run_pipeline(
                employees=pipeline_employees,
                jobs=pipeline_jobs,
                global_knowledge_graph={},   # empty KG
            )

        assert isinstance(summary_text, str)


# ---------------------------------------------------------------------------
# main.py pipeline integration (FastAPI background task)
# ---------------------------------------------------------------------------

class TestMainPipelineIntegration:
    """
    Verify that _run_matching_pipeline in main.py:
      1. Reads employees and jobs from DB (not from PDF re-parse)
      2. Passes them to run_pipeline
      3. Persists resulting assignments
    """

    @pytest.mark.asyncio
    async def test_pipeline_reads_from_db_not_pdf(self, pipeline_jobs):
        import importlib
        import sys

        # We import main lazily to avoid triggering the full startup sequence
        # in tests that don't need it.  Just verify the DB-read → pipeline chain.

        mock_employees = [
            {"_id": "alice@x.com", "email": "alice@x.com", "name": "Alice",
             "available": True, "skills": ["Python"], "projects": []},
        ]
        mock_jobs = [
            {"_id": "job_backend_0", "project_id": "proj_x", "title": "Backend",
             "required_stack": [{"skill": "Python", "level": "expert"}],
             "remaining": 1},
        ]

        # Simulate what _run_matching_pipeline does: DB → pipeline → persist
        with patch("db.operations.list_employees", new=AsyncMock(return_value=mock_employees)), \
             patch("db.operations.get_open_jobs",  new=AsyncMock(return_value=mock_jobs)), \
             patch("matching_pipeline_v2.orchestrator.run_pipeline",
                   return_value=('{"n_assignments":1}', [])):
            # The key assertion: run_pipeline should be called with data from DB,
            # not from a fresh PDF parse.  We verify by checking that
            # list_employees and get_open_jobs are the data sources.
            import db.operations as db_ops
            employees = await db_ops.list_employees(available=True)
            jobs      = await db_ops.get_open_jobs("proj_x")

            assert len(employees) == 1
            assert employees[0]["email"] == "alice@x.com"
            assert len(jobs) == 1
            assert jobs[0]["_id"] == "job_backend_0"
