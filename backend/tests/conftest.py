"""
tests/conftest.py
==================
Shared pytest fixtures for the matching pipeline test suite.

All heavy external dependencies (Neo4j, MongoDB, NVIDIA API, A2A HTTP
servers) are mocked at the boundary so tests run offline and instantly.
"""
from __future__ import annotations

import json
import sys
import os

import pytest

# Make the backend root importable from every test file
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Auto-cleanup: reset the KG singleton cache before every test
# ---------------------------------------------------------------------------
# Without this, a test that mocks GraphDatabase and warms the cache pollutes
# subsequent tests (they see the mocked nodes instead of the test's own KG).

@pytest.fixture(autouse=True)
def _reset_kg_cache():
    try:
        from matching_pipeline_v2.knowledge_graph import invalidate_kg_cache
        invalidate_kg_cache()
    except Exception:
        pass
    yield
    try:
        from matching_pipeline_v2.knowledge_graph import invalidate_kg_cache
        invalidate_kg_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Minimal data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_employees() -> list[dict]:
    return [
        {
            "email":           "alice@example.com",
            "name":            "Alice Martin",
            "available":       True,
            "skills":          ["Python", "FastAPI", "Docker"],
            "knowledge_graph": {"python": ["fastapi", "flask"]},
        },
        {
            "email":           "bob@example.com",
            "name":            "Bob Dupont",
            "available":       True,
            "skills":          ["React", "TypeScript", "Node.js"],
            "knowledge_graph": {},
        },
        {
            "email":           "carol@example.com",
            "name":            "Carol Petit",
            "available":       True,
            "skills":          ["Python", "PyTorch", "MLflow"],
            "knowledge_graph": {"pytorch": ["tensorflow"]},
        },
    ]


@pytest.fixture
def sample_jobs() -> list[dict]:
    return [
        {
            "job_id":          "job_backend_0",
            "title":           "Backend Engineer",
            "required_skills": ["python", "fastapi", "docker"],
        },
        {
            "job_id":          "job_frontend_1",
            "title":           "Frontend Engineer",
            "required_skills": ["react", "typescript"],
        },
    ]


@pytest.fixture
def sample_kg() -> dict:
    """Small in-memory knowledge graph for unit tests (no Neo4j required)."""
    return {
        "python":     {"fastapi": 0.9, "flask": 0.85, "django": 0.80},
        "fastapi":    {"python": 0.9},
        "react":      {"vue.js": 0.75, "typescript": 0.90},
        "typescript": {"javascript": 0.95, "react": 0.90},
        "pytorch":    {"tensorflow": 0.80, "python": 0.95},
        "docker":     {"kubernetes": 0.85},
    }


@pytest.fixture
def sample_assignments(sample_employees, sample_jobs) -> list[dict]:
    return [
        {
            "employee_email": sample_employees[0]["email"],
            "job_id":         sample_jobs[0]["job_id"],
            "score":          0.82,
            "matched_skills": ["python", "fastapi"],
            "inferred_skills": ["flask"],
            "missing_skills": [],
        },
        {
            "employee_email": sample_employees[1]["email"],
            "job_id":         sample_jobs[1]["job_id"],
            "score":          0.91,
            "matched_skills": ["react", "typescript"],
            "inferred_skills": [],
            "missing_skills": [],
        },
    ]
