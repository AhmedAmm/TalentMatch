"""
tests/test_project_parser.py
==============================
Unit tests for po_parser/project_parser.py

No PDF or LLM calls are made — both are mocked at their boundaries.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from po_parser.project_parser import (
    _chunk_text,
    _merge_partials,
    _upsert_job,
    _fuzzy_title_match,
    _parse_llm_response,
    _flatten_non_functional,
    _flatten_technology_stack,
    _generate_project_id,
    _MAX_CHUNK_CHARS,
    _JOB_TITLE_SIMILARITY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_returned_as_single_chunk(self):
        text   = "Short text."
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_at_paragraph_boundary(self):
        para1  = "A" * 60
        para2  = "B" * 60
        text   = f"{para1}\n\n{para2}"
        chunks = _chunk_text(text, max_chars=80)
        assert len(chunks) == 2
        assert para1 in chunks[0]
        assert para2 in chunks[1]

    def test_does_not_split_inside_paragraph(self):
        # One huge paragraph — kept as one chunk even if > max_chars
        text   = "Word " * 200          # 1 000 chars, no double-newline
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) == 1

    def test_empty_text_returns_one_empty_chunk(self):
        chunks = _chunk_text("", max_chars=100)
        assert chunks == [""]


# ---------------------------------------------------------------------------
# _fuzzy_title_match
# ---------------------------------------------------------------------------

class TestFuzzyTitleMatch:
    def test_identical_titles_match(self):
        assert _fuzzy_title_match("Backend Engineer", "Backend Engineer") is True

    def test_partial_overlap_above_threshold(self):
        # "Tech Lead" ∩ "Tech Lead / Architecte IA" → 2/4 = 0.5
        assert _fuzzy_title_match("Tech Lead", "Tech Lead / Architecte IA") is True

    def test_completely_different_titles_do_not_match(self):
        assert _fuzzy_title_match("Frontend Developer", "DevOps Engineer") is False

    def test_case_insensitive(self):
        assert _fuzzy_title_match("backend engineer", "Backend Engineer") is True

    def test_empty_titles(self):
        assert _fuzzy_title_match("", "") is True
        assert _fuzzy_title_match("", "Something") is False


# ---------------------------------------------------------------------------
# _upsert_job
# ---------------------------------------------------------------------------

class TestUpsertJob:
    def _make_job(self, title: str, description: str = "") -> dict:
        return {"title": title, "description": description}

    def test_adds_new_unique_job(self):
        jobs = []
        job  = self._make_job("Backend Engineer", "desc")
        _upsert_job(jobs, job, job["title"])
        assert len(jobs) == 1

    def test_does_not_add_fuzzy_duplicate(self):
        jobs = [self._make_job("Tech Lead")]
        new  = self._make_job("Tech Lead / Architecte IA", "longer description here")
        _upsert_job(jobs, new, new["title"])
        assert len(jobs) == 1

    def test_keeps_entry_with_longer_description(self):
        jobs = [self._make_job("Tech Lead", "short")]
        new  = self._make_job("Tech Lead / Architecte IA", "much longer description")
        _upsert_job(jobs, new, new["title"])
        assert jobs[0]["description"] == "much longer description"

    def test_distinct_titles_both_added(self):
        jobs = [self._make_job("Backend Engineer")]
        _upsert_job(jobs, self._make_job("Frontend Engineer"), "Frontend Engineer")
        assert len(jobs) == 2


# ---------------------------------------------------------------------------
# _merge_partials
# ---------------------------------------------------------------------------

class TestMergePartials:
    def _base_partial(self, **overrides) -> dict:
        base = {
            "project":              {"name": "", "client": "", "description": ""},
            "functional_needs":     [],
            "non_functional_needs": [],
            "technology_stack":     [],
            "jobs":                 [],
        }
        base.update(overrides)
        return base

    def test_project_metadata_first_non_empty_wins(self):
        p1 = self._base_partial(project={"name": "MyApp", "client": "", "description": ""})
        p2 = self._base_partial(project={"name": "",      "client": "Acme", "description": ""})
        result = _merge_partials([p1, p2])
        assert result["project"]["name"]   == "MyApp"
        assert result["project"]["client"] == "Acme"

    def test_functional_needs_deduped(self):
        p1 = self._base_partial(functional_needs=["Login", "Export"])
        p2 = self._base_partial(functional_needs=["login", "Dashboard"])
        result = _merge_partials([p1, p2])
        lower = [n.lower() for n in result["functional_needs"]]
        assert lower.count("login") == 1
        assert "export" in lower
        assert "dashboard" in lower

    def test_technology_stack_merged_by_layer(self):
        p1 = self._base_partial(technology_stack=[
            {"layer": "Backend", "technologies": ["Python"]}
        ])
        p2 = self._base_partial(technology_stack=[
            {"layer": "Backend", "technologies": ["FastAPI"]}
        ])
        result = _merge_partials([p1, p2])
        backend = next(l for l in result["technology_stack"] if l["layer"] == "Backend")
        assert set(backend["technologies"]) == {"Python", "FastAPI"}

    def test_jobs_fuzzy_deduped(self):
        job1 = {"title": "Tech Lead",                "description": "short"}
        job2 = {"title": "Tech Lead / Architecte IA","description": "longer description text"}
        p1   = self._base_partial(jobs=[job1])
        p2   = self._base_partial(jobs=[job2])
        result = _merge_partials([p1, p2])
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["description"] == "longer description text"

    def test_distinct_jobs_both_kept(self):
        p1 = self._base_partial(jobs=[{"title": "Backend Engineer", "description": ""}])
        p2 = self._base_partial(jobs=[{"title": "DevOps Engineer",  "description": ""}])
        result = _merge_partials([p1, p2])
        assert len(result["jobs"]) == 2


# ---------------------------------------------------------------------------
# _flatten helpers
# ---------------------------------------------------------------------------

class TestFlattenNonFunctional:
    def test_dict_items_formatted(self):
        items  = [{"category": "Performance", "description": "fast response"}]
        result = _flatten_non_functional(items)
        assert result == ["Performance: fast response"]

    def test_strings_passed_through(self):
        assert _flatten_non_functional(["scalability"]) == ["scalability"]

    def test_empty_list(self):
        assert _flatten_non_functional([]) == []


class TestFlattenTechnologyStack:
    def test_layer_tech_pairs_formatted(self):
        items  = [{"layer": "Backend", "technologies": ["Python", "FastAPI"]}]
        result = _flatten_technology_stack(items)
        assert "Backend/Python" in result
        assert "Backend/FastAPI" in result

    def test_strings_passed_through(self):
        assert _flatten_technology_stack(["Python"]) == ["Python"]


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    def test_valid_json(self):
        raw = '{"project": {"name": "Test"}}'
        assert _parse_llm_response(raw) == {"project": {"name": "Test"}}

    def test_strips_markdown_fences(self):
        raw = "```json\n{\"key\": 1}\n```"
        assert _parse_llm_response(raw) == {"key": 1}

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_llm_response("not json at all")


# ---------------------------------------------------------------------------
# _generate_project_id
# ---------------------------------------------------------------------------

class TestGenerateProjectId:
    def test_basic_slug(self):
        # hyphens are treated as separators → "e_commerce_platform"
        assert _generate_project_id("E-Commerce Platform") == "proj_e_commerce_platform"

    def test_lowercase_and_replace_special(self):
        assert _generate_project_id("SmartStaff!") == "proj_smartstaff"

    def test_leading_trailing_underscores_stripped(self):
        pid = _generate_project_id("  My App  ")
        assert not pid.startswith("proj__")
        assert not pid.endswith("_")


# ---------------------------------------------------------------------------
# parse_project_pdf (integration-level — Docling + LLM mocked)
# ---------------------------------------------------------------------------

class TestParseProjectPdf:
    def test_single_chunk_flow(self, tmp_path):
        fake_pdf = tmp_path / "report.pdf"
        fake_pdf.touch()

        extracted_text = "Project: MyApp\n\nJob: Backend Engineer\n\nstack: Python"
        llm_response   = json.dumps({
            "project":              {"name": "MyApp", "client": "Acme", "description": "desc"},
            "functional_needs":     ["Login"],
            "non_functional_needs": [{"category": "Performance", "description": "fast"}],
            "technology_stack":     [{"layer": "Backend", "technologies": ["Python"]}],
            "jobs":                 [{"title": "Backend Engineer", "description": "Python dev",
                                      "headcount": 1, "seniority": "mid", "type": "full-time",
                                      "estimated_duration_months": 6,
                                      "required_stack": [{"skill": "Python", "level": "expert"}],
                                      "responsibilities": ["Build APIs"]}],
        })

        with patch("po_parser.project_parser.extract_text_from_pdf", return_value=extracted_text), \
             patch("po_parser.project_parser.ask_llm", return_value=llm_response), \
             patch("po_parser.project_parser._MAX_CHUNK_CHARS", 999_999):  # force single chunk
            from po_parser.project_parser import parse_project_pdf
            result = parse_project_pdf(str(fake_pdf))

        assert result["project"]["name"] == "MyApp"
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["title"] == "Backend Engineer"
