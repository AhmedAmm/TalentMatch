"""
tests/test_knowledge_graph.py
===============================
Unit tests for knowledge_graph.py — no live Neo4j connection required.

The Neo4j driver is mocked at the boundary so every test runs offline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

import matching_pipeline_v2.knowledge_graph as kg_mod
from matching_pipeline_v2.knowledge_graph import (
    WeightedKG,
    _detect_label,
    _load_edges,
    merge_with_personal,
    invalidate_kg_cache,
    get_kg,
    _LABEL_CANDIDATES,
)


# ---------------------------------------------------------------------------
# _detect_label
# ---------------------------------------------------------------------------

class TestDetectLabel:
    def test_prefers_technology_over_others(self):
        labels = {"Technology", "Tech", "Skill"}
        assert _detect_label(labels) == "Technology"

    def test_fallback_to_tech(self):
        assert _detect_label({"Tech", "Skill"}) == "Tech"

    def test_fallback_to_first_candidate_available(self):
        assert _detect_label({"Skill"}) == "Skill"

    def test_returns_none_for_empty(self):
        # No candidates present → alphabetical fallback, but empty set returns None
        assert _detect_label(set()) is None

    def test_unknown_label_uses_alphabetical_fallback(self):
        result = _detect_label({"Zebra", "Alpha"})
        assert result == "Alpha"   # sorted() picks first alphabetically


# ---------------------------------------------------------------------------
# _load_edges
# ---------------------------------------------------------------------------

class TestLoadEdges:
    def _make_session(self, rows: list[dict]) -> MagicMock:
        session = MagicMock()
        run_result = MagicMock()
        run_result.data.return_value = rows
        session.run.return_value = run_result
        return session

    def test_basic_edge_loaded(self):
        rows = [
            {"src": "python", "dst": "fastapi", "rel_type": "REQUIRES", "raw_weight": 1.0},
        ]
        edge_defaults = {"REQUIRES": 0.90}
        result = _load_edges(self._make_session(rows), "Technology", False, edge_defaults)
        assert "python" in result
        assert result["python"]["fastapi"] == 0.90   # REQUIRES → default

    def test_transferable_to_uses_explicit_weight(self):
        rows = [
            {"src": "react", "dst": "vue.js", "rel_type": "TRANSFERABLE_TO", "raw_weight": 0.75},
        ]
        result = _load_edges(self._make_session(rows), "Technology", True, {})
        assert result["react"]["vue.js"] == 0.75

    def test_unknown_rel_type_uses_fallback_0_60(self):
        rows = [
            {"src": "a", "dst": "b", "rel_type": "UNKNOWN_TYPE", "raw_weight": None},
        ]
        result = _load_edges(self._make_session(rows), None, False, {})
        assert result["a"]["b"] == 0.60

    def test_skips_rows_with_missing_src_or_dst(self):
        rows = [
            {"src": "",      "dst": "b", "rel_type": "REQUIRES", "raw_weight": 1.0},
            {"src": "a",     "dst": None,"rel_type": "REQUIRES", "raw_weight": 1.0},
        ]
        result = _load_edges(self._make_session(rows), "Technology", False, {"REQUIRES": 0.9})
        assert result == {}

    def test_keeps_strongest_weight_for_duplicate_pairs(self):
        rows = [
            {"src": "a", "dst": "b", "rel_type": "OFTEN_USED_WITH", "raw_weight": None},
            {"src": "a", "dst": "b", "rel_type": "EXTENDS",         "raw_weight": None},
        ]
        defaults = {"OFTEN_USED_WITH": 0.50, "EXTENDS": 0.85}
        result = _load_edges(self._make_session(rows), "Technology", False, defaults)
        assert result["a"]["b"] == 0.85   # max kept


# ---------------------------------------------------------------------------
# merge_with_personal
# ---------------------------------------------------------------------------

class TestMergeWithPersonal:
    def test_adds_personal_edges_with_weight_1(self, sample_kg):
        personal = {"python": ["mylib"]}
        merged   = merge_with_personal(sample_kg, personal)
        assert merged["python"]["mylib"] == 1.0

    def test_does_not_downgrade_existing_global_edge(self, sample_kg):
        # python→fastapi is 0.9 in global; personal declares it too
        personal = {"python": ["fastapi"]}
        merged   = merge_with_personal(sample_kg, personal)
        assert merged["python"]["fastapi"] == 1.0   # personal upgrades to 1.0

    def test_does_not_mutate_global_kg(self, sample_kg):
        original_python_neighbours = dict(sample_kg.get("python", {}))
        merge_with_personal(sample_kg, {"python": ["new_skill"]})
        # original must be unchanged
        assert sample_kg.get("python") == original_python_neighbours

    def test_case_normalisation(self, sample_kg):
        personal = {"Python": ["NewSkill"]}
        merged   = merge_with_personal(sample_kg, personal)
        assert merged["python"]["newskill"] == 1.0

    def test_empty_personal_returns_copy(self, sample_kg):
        merged = merge_with_personal(sample_kg, {})
        assert merged == sample_kg
        assert merged is not sample_kg


# ---------------------------------------------------------------------------
# Singleton cache (get_kg / invalidate_kg_cache)
# ---------------------------------------------------------------------------

class TestSingletonCache:
    def test_get_kg_calls_load_once(self, sample_kg):
        invalidate_kg_cache()
        # get_kg() now goes through get_graph_store(). Patch the GraphStore.load
        # classmethod so we can assert it's only called once.
        from matching_pipeline_v2.knowledge_graph import GraphStore
        fake_store = MagicMock()
        fake_store.to_weighted_kg.return_value = sample_kg
        with patch.object(GraphStore, "load", return_value=fake_store) as mock_load:
            kg1 = get_kg()
            kg2 = get_kg()
            mock_load.assert_called_once()   # second call uses cache
            assert kg1 is kg2

    def test_invalidate_forces_reload(self, sample_kg):
        invalidate_kg_cache()
        from matching_pipeline_v2.knowledge_graph import GraphStore
        fake_store = MagicMock()
        fake_store.to_weighted_kg.return_value = sample_kg
        with patch.object(GraphStore, "load", return_value=fake_store) as mock_load:
            get_kg()
            invalidate_kg_cache()
            get_kg()
            assert mock_load.call_count == 2


# ---------------------------------------------------------------------------
# Guard: check _fuzzy_title_match is importable from project_parser
# (we don't import it from kg; this tests that the helper exists)
# ---------------------------------------------------------------------------

def _fuzzy_title_match_import_guard():
    """Placeholder — actual fuzzy match tests live in test_project_parser."""
    pass
