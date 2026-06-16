"""
matching_pipeline_v2/knowledge_graph.py
=========================================
Neo4j knowledge-graph loader — single full-graph query, RAM-resident.

This module is the direct equivalent of the old pipeline's
``core/graph_store.py``: one Cypher query loads ALL Technology nodes (even
isolated ones) and ALL relationships into Python dicts.  Every subsequent
neighbour lookup is served from RAM.

Public API
----------
  get_graph_store()         → singleton GraphStore (load once, cache forever)
  invalidate_kg_cache()     → drop the cache so the next call re-queries Neo4j
  get_kg()                  → backward-compatible WeightedKG view (bidirectional)
  merge_with_personal(...)  → overlay an employee's personal adjacency on the global KG

GraphStore methods (mirror old pipeline)
-----------------------------------------
  store.label                — detected node label (e.g. "Technology")
  store.has_weight           — whether edges carry a `weight` property
  store.node_names           — list of every Technology node name (lowercased)
  store.alias_map            — {alias_lower: canonical_lower}
  store.get_neighbours(names)
        Returns rows {frm, to, rel, w} for BOTH outgoing AND incoming edges.
        Used for employee BFS (bfs_profile) — bidirectional traversal.
  store.get_neighbours_job(names)
        Returns rows {frm, to, rel, w} for OUTGOING REQUIRES/EXTENDS/IMPLEMENTS only.
        Used for job BFS (bfs_job) — directional, semantic-only traversal.

Edge weights
------------
  TRANSFERABLE_TO / EQUIVALENT_IN  → use the edge's explicit `weight` property
  All other relationship types     → per-type default from cfg.NEO4J_EDGE_WEIGHTS
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import TypeAlias

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
WeightedKG: TypeAlias = dict[str, dict[str, float]]

# Candidate node labels to probe (first match wins, same order as old pipeline)
_LABEL_CANDIDATES: tuple[str, ...] = ("Technology", "Tech", "Skill", "Node", "Tool")

# Relationship types used by bfs_job (mirrors old kg_score.get_neighbours_job)
_JOB_REL_TYPES: frozenset[str] = frozenset({"REQUIRES", "EXTENDS", "IMPLEMENTS"})


# ---------------------------------------------------------------------------
# GraphStore class (drop-in equivalent of old graph_store.GraphStore)
# ---------------------------------------------------------------------------

class GraphStore:
    """
    In-memory snapshot of the entire Neo4j tech graph.

    Loaded once via ``GraphStore.load()``; subsequent neighbour lookups
    are pure-Python dict reads.  The class API mirrors the old pipeline's
    GraphStore exactly so scoring code can be ported 1:1.
    """

    def __init__(
        self,
        label: str | None,
        has_weight: bool,
        rel_types: list[str],
        alias_map: dict[str, str],
        node_names: list[str],
        adj_out: dict[str, list[tuple[str, str, float]]],
        adj_in:  dict[str, list[tuple[str, str, float]]],
    ) -> None:
        self.label      = label
        self.has_weight = has_weight
        self.rel_types  = rel_types
        self.alias_map  = alias_map
        self.node_names = node_names
        self._adj_out   = adj_out
        self._adj_in    = adj_in

    # ---------------------------------------------------------------------
    # Neighbour lookups (drop-in for old kg_score functions)
    # ---------------------------------------------------------------------

    def get_neighbours(self, names: list[str]) -> list[dict]:
        """
        Bidirectional neighbour list — used by employee BFS (bfs_profile).

        Returns rows: {frm, to, rel, w}.  Mirrors old pipeline:
            MATCH (a)-[r]->(b) RETURN ...
            UNION
            MATCH (a)<-[r]-(b) RETURN ...
        """
        seen: set[tuple[str, str, str]] = set()
        results: list[dict] = []
        for name in names:
            for to, rel, w in self._adj_out.get(name, []):
                key = (name, to, rel)
                if key not in seen:
                    seen.add(key)
                    results.append({"frm": name, "to": to, "rel": rel, "w": w})
            for frm, rel, w in self._adj_in.get(name, []):
                # In the old pipeline, incoming edges are returned with frm = name,
                # to = the other end (logical "we're reaching that node from name").
                key = (name, frm, rel)
                if key not in seen:
                    seen.add(key)
                    results.append({"frm": name, "to": frm, "rel": rel, "w": w})
        return results

    def get_neighbours_job(self, names: list[str]) -> list[dict]:
        """
        Outgoing REQUIRES/EXTENDS/IMPLEMENTS only — used by job BFS (bfs_job).

        Mirrors old pipeline:
            MATCH (a)-[r]->(b)
            WHERE type(r) IN ["REQUIRES", "EXTENDS", "IMPLEMENTS"]
            RETURN ...
        """
        results: list[dict] = []
        for name in names:
            for to, rel, w in self._adj_out.get(name, []):
                if rel in _JOB_REL_TYPES:
                    results.append({"frm": name, "to": to, "rel": rel, "w": w})
        return results

    # ---------------------------------------------------------------------
    # Backward-compat: WeightedKG view (bidirectional, weight only)
    # ---------------------------------------------------------------------

    def to_weighted_kg(self) -> WeightedKG:
        """
        Build a flat ``{src: {dst: weight}}`` dict that captures BOTH directions.

        The weight stored is the resolved edge weight (already accounts for
        EDGE_WEIGHTS map and TRANSFERABLE_TO explicit weight property).  When
        multiple edges connect the same pair, the strongest weight is kept.
        """
        kg: WeightedKG = {}
        for src, edges in self._adj_out.items():
            bucket = kg.setdefault(src, {})
            for to, _rel, w in edges:
                if to == src:
                    continue
                bucket[to] = max(bucket.get(to, 0.0), w)
        # Reverse direction: incoming edges become outgoing in the WeightedKG view.
        for dst, edges in self._adj_in.items():
            bucket = kg.setdefault(dst, {})
            for frm, _rel, w in edges:
                if frm == dst:
                    continue
                bucket[frm] = max(bucket.get(frm, 0.0), w)
        return kg

    def stats(self) -> str:
        n_edges = sum(len(v) for v in self._adj_out.values())
        return (
            f"GraphStore(label={self.label!r}, nodes={len(self.node_names)}, "
            f"edges={n_edges}, has_weight={self.has_weight})"
        )

    # ---------------------------------------------------------------------
    # Loader (factory)
    # ---------------------------------------------------------------------

    @classmethod
    def load(cls) -> "GraphStore":
        """Run the full load pipeline against Neo4j (no caching here — see get_graph_store)."""
        import matching_pipeline_v2.config as cfg

        try:
            from neo4j import GraphDatabase
        except ImportError:
            logger.warning("[KG] neo4j package not installed — using empty graph.")
            return cls(None, False, [], {}, [], {}, {})

        try:
            driver = GraphDatabase.driver(
                cfg.NEO4J_URI, auth=(cfg.NEO4J_USER, cfg.NEO4J_PASSWORD)
            )
            driver.verify_connectivity()
        except Exception as exc:
            logger.warning("[KG] Cannot reach Neo4j (%s) — using empty graph.", exc)
            return cls(None, False, [], {}, [], {}, {})

        db = cfg.NEO4J_DATABASE
        try:
            with driver.session(database=db) as session:
                # ── 1. Schema detection ──────────────────────────────────
                labels = {
                    r["label"]
                    for r in session.run("CALL db.labels() YIELD label RETURN label").data()
                }
                rel_types = [
                    r["relationshipType"]
                    for r in session.run(
                        "CALL db.relationshipTypes() YIELD relationshipType "
                        "RETURN relationshipType"
                    ).data()
                ]
                prop_keys = {
                    r["propertyKey"]
                    for r in session.run(
                        "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey"
                    ).data()
                }

                label = _detect_label(labels)
                has_weight = "weight" in prop_keys
                lf = f":{label}" if label else ""

                logger.info(
                    "[KG] Connecting to database=%r  label=%r  has_weight=%s",
                    db, label, has_weight,
                )

                # ── 2. ALL nodes (including isolated ones) ───────────────
                if label:
                    node_rows = session.run(
                        f"MATCH (t:{label}) WHERE t.name IS NOT NULL "
                        "RETURN toLower(trim(t.name)) AS name"
                    ).data()
                else:
                    node_rows = session.run(
                        "MATCH (t) WHERE t.name IS NOT NULL "
                        "RETURN toLower(trim(t.name)) AS name"
                    ).data()
                node_names = sorted({r["name"] for r in node_rows if r.get("name")})

                # ── 3. Alias map ─────────────────────────────────────────
                alias_rows = session.run(
                    f"MATCH (t{lf}) WHERE t.aliases IS NOT NULL "
                    "RETURN toLower(trim(t.name)) AS name, t.aliases AS aliases"
                ).data()
                alias_map: dict[str, str] = {}
                for row in alias_rows:
                    name = row.get("name", "")
                    raw  = row.get("aliases", "") or ""
                    if not name:
                        continue
                    for alias in raw.split(","):
                        alias = alias.strip().lower()
                        if alias:
                            alias_map[alias] = name

                # ── 4. ALL edges in one query ────────────────────────────
                weight_expr = "coalesce(r.weight, 1.0)" if has_weight else "1.0"
                edge_rows = session.run(
                    f"""
                    MATCH (a{lf})-[r]->(b{lf})
                    RETURN
                        toLower(trim(a.name)) AS frm,
                        toLower(trim(b.name)) AS to,
                        type(r)               AS rel,
                        {weight_expr}         AS w
                    """
                ).data()
        finally:
            driver.close()

        # ── 5. Build adjacency indices ───────────────────────────────────
        adj_out: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
        adj_in:  dict[str, list[tuple[str, str, float]]] = defaultdict(list)

        edge_defaults = cfg.NEO4J_EDGE_WEIGHTS

        for row in edge_rows:
            frm = row.get("frm") or ""
            to  = row.get("to")  or ""
            rel = (row.get("rel") or "").upper()
            raw_w = row.get("w")

            if not frm or not to or frm == to:
                continue

            # Resolve weight: explicit for self-weighted types, else default
            if rel in ("TRANSFERABLE_TO", "EQUIVALENT_IN") and raw_w is not None:
                weight = float(raw_w)
            else:
                weight = edge_defaults.get(rel, 0.60)

            adj_out[frm].append((to, rel, weight))
            adj_in[to].append((frm, rel, weight))

        # Ensure every node appears as a key in adj_out (even isolated ones)
        for name in node_names:
            adj_out.setdefault(name, [])

        store = cls(
            label      = label,
            has_weight = has_weight,
            rel_types  = rel_types,
            alias_map  = alias_map,
            node_names = node_names,
            adj_out    = dict(adj_out),
            adj_in     = dict(adj_in),
        )

        n_edges = sum(len(v) for v in adj_out.values())
        logger.info(
            "[KG] Loaded: %d nodes | %d directed edges | bidirectional reachable=%d",
            len(node_names), n_edges, n_edges + sum(len(v) for v in adj_in.values()),
        )
        return store


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store_cache: GraphStore | None = None
_kg_cache:    WeightedKG | None = None


def get_graph_store() -> GraphStore:
    """Return the loaded GraphStore (cache after first call)."""
    global _store_cache
    if _store_cache is None:
        _store_cache = GraphStore.load()
    return _store_cache


def get_kg() -> WeightedKG:
    """
    Return the bidirectional WeightedKG view (backward-compatible).

    The old code used a flat ``{src: {dst: weight}}`` dict; this preserves
    that interface while the GraphStore underneath retains rel_type info
    for the scoring agent's directional BFS.
    """
    global _kg_cache
    if _kg_cache is None:
        _kg_cache = get_graph_store().to_weighted_kg()
    return _kg_cache


def invalidate_kg_cache() -> None:
    """Drop both caches so the next call re-queries Neo4j."""
    global _store_cache, _kg_cache
    _store_cache = None
    _kg_cache    = None
    logger.info("[KG] Cache invalidated — next call will reload from Neo4j.")


# ---------------------------------------------------------------------------
# Personal KG overlay (unchanged interface)
# ---------------------------------------------------------------------------

def merge_with_personal(
    global_kg: WeightedKG,
    personal_kg: dict[str, list[str]],
) -> WeightedKG:
    """
    Overlay an employee's personal adjacency list on top of the global KG.

    Personal edges always carry weight 1.0 (employee-declared, fully trusted).
    The global KG is never mutated.
    """
    # Always return a fresh copy so callers can mutate it freely
    merged: WeightedKG = {k: dict(v) for k, v in global_kg.items()}
    if not personal_kg:
        return merged

    for skill, neighbours in personal_kg.items():
        key = skill.strip().lower()
        if not key:
            continue
        bucket = merged.setdefault(key, {})
        for nb in neighbours:
            nb_key = nb.strip().lower()
            if nb_key and bucket.get(nb_key, 0.0) < 1.0:
                bucket[nb_key] = 1.0
    return merged


# ---------------------------------------------------------------------------
# Internal helpers (kept public for tests)
# ---------------------------------------------------------------------------

def _detect_label(available_labels: set[str]) -> str | None:
    """Return the first matching candidate label, or None if none found."""
    for candidate in _LABEL_CANDIDATES:
        if candidate in available_labels:
            return candidate
    return sorted(available_labels)[0] if available_labels else None


def _load_edges(session, label, has_weight, edge_defaults) -> WeightedKG:
    """
    Backward-compat helper: build a WeightedKG by querying edges directly.

    Used by the old test suite that mocked the session and called this function.
    For production code, GraphStore.load() is preferred.
    """
    label_filter = f":{label}" if label else ""
    weight_expr  = "coalesce(r.weight, 1.0)" if has_weight else "1.0"

    cypher = f"""
    MATCH (a{label_filter})-[r]->(b{label_filter})
    RETURN
        toLower(trim(a.name)) AS src,
        toLower(trim(b.name)) AS dst,
        type(r)               AS rel_type,
        {weight_expr}         AS raw_weight
    """
    kg: WeightedKG = {}
    for rec in session.run(cypher).data():
        src      = rec.get("src") or ""
        dst      = rec.get("dst") or ""
        rel_type = (rec.get("rel_type") or "").upper()
        raw_w    = rec.get("raw_weight")
        if not src or not dst or src == dst:
            continue
        if rel_type in ("TRANSFERABLE_TO", "EQUIVALENT_IN") and raw_w is not None:
            weight = float(raw_w)
        else:
            weight = edge_defaults.get(rel_type, 0.60)
        bucket = kg.setdefault(src, {})
        bucket[dst] = max(bucket.get(dst, 0.0), weight)
        # Also add reverse direction for bidirectional employee BFS
        rev = kg.setdefault(dst, {})
        rev[src] = max(rev.get(src, 0.0), weight)
    return kg


def load_kg() -> WeightedKG:
    """
    Backward-compatible loader — returns the WeightedKG view directly.

    Internally delegates to GraphStore.load() then exposes the bidirectional
    flat-dict view used by the existing scoring/search code.
    """
    return GraphStore.load().to_weighted_kg()
