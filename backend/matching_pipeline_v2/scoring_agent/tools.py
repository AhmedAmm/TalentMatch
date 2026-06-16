"""
matching_pipeline_v2/scoring_agent/tools.py
=============================================
LangChain tools used by the Scoring Agent's ReAct brain.

Scoring formulas
================

Skill scoring (per direct skill an employee holds):
    raw_score = 0.40 × recency + 0.30 × duration + 0.30 × complexity
    coefficient = raw_score / max(raw_scores)        # normalise so best skill = 1.0

Recency  — power-law decay (Wixted & Ebbesen 1991; better fit than pure exponential):
    recency = 1 / (1 + (days_since / HALF_LIFE_DAYS) ^ DECAY_ALPHA)
    HALF_LIFE_DAYS = 365, DECAY_ALPHA = 0.5

Duration — BM25-style saturation (Robertson & Walker 1994; diminishing returns):
    duration = months / (months + K1_DURATION)
    K1_DURATION = 12  (saturation knee at ~12 months; no hard cap)

BFS expansion (employee profile, bidirectional):
    Use store.get_neighbours(names)         # both directions, all rel types
    new_score = parent × HOP_DECAY × EDGE_W[rel] × neo4j_weight
        HOP_DECAY = 0.55
        MAX_HOPS  = 4
        EDGE_W: see _EDGE_W below

BFS expansion (job vector, directional):
    Use store.get_neighbours_job(names)     # outgoing REQUIRES/EXTENDS/IMPLEMENTS only
    Same per-hop formula.

Adequacy (final pair score):
    norm     = ‖job_vec‖₂
    adequacy = dot(profile_vec, job_vec / norm)
    score    = clip(adequacy, 0.0, 1.0)

This is exactly the formulas from the old pipeline's:
  • profil_score.py   (frequency / recency / complexity / responsibility scoring)
  • kg_score.py       (BFS engine + EDGE_W + HOP_DECAY)
  • matching_agent.py (compute_adequacy_matrix)
"""
from __future__ import annotations

import json
import math
from collections import deque
from datetime import datetime, timezone
from typing import Any

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hyper-parameters (verbatim from old pipeline kg_score.py)
# ---------------------------------------------------------------------------
MAX_HOPS:  int   = 4
HOP_DECAY: float = 0.55

# Per-relationship-type transfer weights (verbatim from old kg_score.EDGE_W)
_EDGE_W: dict[str, float] = {
    "EXTENDS":         1.00,
    "REQUIRES":        1.00,
    "EQUIVALENT_IN":   0.95,
    "TRANSFERABLE_TO": 0.85,
    "EVOLVED_INTO":    0.80,
    "PART_OF":         0.75,
    "IMPLEMENTS":      0.65,
    "BRIDGES":         0.70,
    "OFTEN_USED_WITH": 0.60,
}

# Skill-score component weights
RECENCY_WEIGHT:    float = 0.40
DURATION_WEIGHT:   float = 0.40
COMPLEXITY_WEIGHT: float = 0.20

# Recency: power-law decay — 1 / (1 + (days/HALF_LIFE)^ALPHA)
# ALPHA=0.5 (square-root) gives negatively-accelerated decline matching
# Wixted & Ebbesen (1991) empirical fits across many forgetting datasets.
HALF_LIFE_DAYS: int   = 365
DECAY_ALPHA:    float = 0.5

# Duration: BM25-style saturation — months / (months + K1)
# K1=12 places the half-saturation point at 12 months; beyond that each
# extra month adds progressively less, mirroring BM25 TF saturation
# (Robertson & Walker 1994, Okapi BM25).
K1_DURATION: float = 12.0

# Backward-compat aliases used elsewhere in the codebase
BFS_MAX_DEPTH = MAX_HOPS

# ---------------------------------------------------------------------------
# Request context — populated by the A2A handler before agent invocation
# ---------------------------------------------------------------------------
_ctx: dict[str, Any] = {}


def set_context(data: dict) -> None:
    """
    Inject the A2A request payload.

    Expected keys:
      employees              : list of employee dicts
      jobs                   : list of job dicts
      weights                : { job_id: { skill: coeff } }  (initial coefficients)
      global_knowledge_graph : WeightedKG view (bidirectional)
    """
    _ctx.clear()
    _ctx.update(data)


# ---------------------------------------------------------------------------
# GraphStore accessor — falls back to building one from the WeightedKG dict
# ---------------------------------------------------------------------------

class _DictKGShim:
    """
    Lightweight GraphStore stand-in built from a WeightedKG ``{src: {dst: w}}``
    dict.  Used when the real Neo4j-backed GraphStore is empty (e.g. during
    unit tests where only a sample_kg dict is provided in _ctx).

    All edges are treated as REQUIRES (so they pass both the bidirectional
    profile BFS and the directional job BFS).
    """

    def __init__(self, kg: dict[str, dict[str, float]]):
        self._kg = kg or {}

    def get_neighbours(self, names: list[str]) -> list[dict]:
        rows: list[dict] = []
        for n in names:
            for to, w in self._kg.get(n, {}).items():
                rows.append({"frm": n, "to": to, "rel": "REQUIRES", "w": float(w)})
        return rows

    def get_neighbours_job(self, names: list[str]) -> list[dict]:
        # Same edges as profile BFS — sample_kg dict has no rel-type info
        return self.get_neighbours(names)


def _get_store():
    """
    Return the GraphStore for BFS lookups.

    Resolution order:
      1. Real Neo4j-backed GraphStore if it has nodes loaded (production path —
         preserves rel_type info so bfs_job correctly filters to REQUIRES /
         EXTENDS / IMPLEMENTS).
      2. _DictKGShim built from ``_ctx['global_knowledge_graph']`` (test path —
         lets unit tests pass a plain WeightedKG dict via set_context()).
    """
    from matching_pipeline_v2.knowledge_graph import get_graph_store
    store = get_graph_store()
    if store.node_names:
        return store
    kg_dict = _ctx.get("global_knowledge_graph") or {}
    return _DictKGShim(kg_dict)


# ---------------------------------------------------------------------------
# Per-skill component scoring (verbatim formulas from old profil_score.py)
# ---------------------------------------------------------------------------

def _recency_score(last_used: str | None) -> float:
    """Power-law decay: 1 / (1 + (days/HALF_LIFE)^ALPHA). None → 0.0."""
    if last_used is None:
        return 0.0
    try:
        lu = datetime.fromisoformat(str(last_used))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
        days = max((datetime.now(timezone.utc) - lu).days, 0)
        return round(1.0 / (1.0 + (days / HALF_LIFE_DAYS) ** DECAY_ALPHA), 4)
    except (ValueError, TypeError):
        return 0.0


def _duration_score(months: int) -> float:
    """BM25-style saturation: months / (months + K1). No hard cap."""
    m = float(months or 0)
    return round(m / (m + K1_DURATION), 4)


def _complexity_score(level: int) -> float:
    return round((level or 1) / 3.0, 4)


def _raw_skill_score(last_used, duration_months, complexity) -> dict:
    rec = _recency_score(last_used)
    dur = _duration_score(duration_months)
    cmp = _complexity_score(complexity)
    raw = round(
        RECENCY_WEIGHT    * rec
        + DURATION_WEIGHT  * dur
        + COMPLEXITY_WEIGHT * cmp,
        4,
    )
    return {
        "raw_score":            raw,
        "recency_component":    rec,
        "duration_component":   dur,
        "complexity_component": cmp,
    }


def _employee_direct_scores(employee: dict) -> dict[str, float]:
    """
    Compute normalised direct-skill scores (max → 1.0).

    Mirrors old pipeline profil_score.extract_engineer_skills which always
    normalises so the strongest skill anchors at 1.0.
    """
    scores: dict[str, float] = {}
    for skill in employee.get("skills", []):
        if isinstance(skill, str):
            name, last_used, duration, complexity = skill, None, 0, 1
        else:
            name       = skill.get("name", "")
            last_used  = skill.get("last_used")
            duration   = skill.get("duration_months", 0)
            complexity = skill.get("complexity", 1)
        if name:
            key = name.strip().lower()
            scores[key] = _raw_skill_score(last_used, duration, complexity)["raw_score"]

    if scores:
        max_score = max(scores.values())
        if max_score > 0:
            scores = {k: round(v / max_score, 4) for k, v in scores.items()}
    return scores


# ---------------------------------------------------------------------------
# BFS engines (mirrors old kg_score._bfs_core)
# ---------------------------------------------------------------------------

def _bfs_core(
    seeds: dict[str, float],
    neighbour_fn,
    max_hops: int = MAX_HOPS,
) -> dict[str, float]:
    """
    Layered BFS from seed nodes; mirrors old kg_score._bfs_core.

    Args:
        seeds        : {skill: starting_coefficient}
        neighbour_fn : function(layer_names) → list[{frm, to, rel, w}]
                       (use store.get_neighbours for profiles or
                        store.get_neighbours_job for jobs)
        max_hops     : MAX_HOPS (default 4)

    Returns:
        {skill: best_coefficient_reached}
    """
    if not seeds:
        return {}

    best: dict[str, float] = dict(seeds)
    queue: deque[tuple[str, float, int]] = deque(
        (s, c, 0) for s, c in seeds.items()
    )

    while queue:
        # Process the whole current "layer" in one neighbour call (matches old impl)
        layer: list[tuple[str, float, int]] = []
        while queue:
            layer.append(queue.popleft())

        layer_names = list({node for node, _, _ in layer})
        edges_by_node: dict[str, list[dict]] = {}
        for row in neighbour_fn(layer_names):
            edges_by_node.setdefault(row["frm"], []).append(row)

        for node, coeff, hop in layer:
            if hop >= max_hops:
                continue
            for e in edges_by_node.get(node, []):
                rel = (e.get("rel") or "").upper()
                w   = float(e.get("w") or 1.0)
                edge_w = _EDGE_W.get(rel, 0.5)
                new_c = round(coeff * HOP_DECAY * edge_w * w, 6)
                target = e["to"]
                if new_c > best.get(target, 0.0):
                    best[target] = new_c
                    queue.append((target, new_c, hop + 1))

    return best


def _build_employee_vector(employee: dict) -> dict[str, float]:
    """
    Bidirectional BFS over the KG starting from the employee's direct skills.

    Direct skills are normalised to max=1.0, then BFS expands using
    store.get_neighbours (both directions, all rel types).
    """
    direct = _employee_direct_scores(employee)
    if not direct:
        return {}

    store = _get_store()

    # Personal-KG overlay: any employee-declared edge counts as weight 1.0
    personal_edges: dict[str, list[str]] = employee.get("knowledge_graph", {}) or {}
    has_personal = bool(personal_edges)

    if has_personal:
        # Build a small wrapper that also yields personal edges as REQUIRES (weight 1.0)
        personal_lookup: dict[str, set[str]] = {
            k.strip().lower(): {n.strip().lower() for n in v if isinstance(n, str)}
            for k, v in personal_edges.items()
        }

        def neighbour_fn(names: list[str]) -> list[dict]:
            rows = store.get_neighbours(names)
            seen = {(r["frm"], r["to"], r["rel"]) for r in rows}
            for n in names:
                for neighbour in personal_lookup.get(n, set()):
                    key = (n, neighbour, "REQUIRES")
                    if key not in seen and neighbour:
                        seen.add(key)
                        rows.append({"frm": n, "to": neighbour, "rel": "REQUIRES", "w": 1.0})
            return rows
    else:
        def neighbour_fn(names: list[str]) -> list[dict]:
            return store.get_neighbours(names)

    return _bfs_core(direct, neighbour_fn)


def _build_job_vector(
    required_skills: list[str],
    seed_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Directional BFS over the KG starting from the job's required skills.

    Uses store.get_neighbours_job (outgoing REQUIRES/EXTENDS/IMPLEMENTS only).
    Seeds default to 1.0 unless ``seed_weights`` overrides them (CoeffTuner
    boosts gap skills via this map).
    """
    if not required_skills:
        return {}

    seed_weights = seed_weights or {}
    seeds: dict[str, float] = {
        s: max(float(seed_weights.get(s, 1.0)), 0.0)
        for s in required_skills
    }

    store = _get_store()
    return _bfs_core(seeds, store.get_neighbours_job)


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

@tool
def score_employee_skills(employee_email: str, job_id: str) -> str:
    """
    Inspect the per-skill component scores for one employee.

    For each skill in the profile, returns:
      raw_score, recency_component, duration_component, complexity_component

    Use this for debugging individual employee scoring.
    For the full score matrix, call compute_score_matrix.

    Args:
        employee_email: employee's unique email
        job_id:         target job (logging context only)
    """
    logger.info("[ScoringAgent] Tool called: score_employee_skills(employee=%s, job=%s)", employee_email, job_id)
    emp = next((e for e in _ctx.get("employees", []) if e["email"] == employee_email), None)
    if emp is None:
        logger.warning("[ScoringAgent] score_employee_skills: employee %r not found", employee_email)
        return json.dumps({"error": f"Employee {employee_email!r} not found"})

    skill_scores = {}
    n_skills = len(emp.get("skills", []))
    logger.debug("[ScoringAgent] score_employee_skills: %d skills found for %s", n_skills, employee_email)
    for skill in emp.get("skills", []):
        if isinstance(skill, str):
            name, last_used, duration, complexity = skill, None, 0, 1
        else:
            name       = skill.get("name", "")
            last_used  = skill.get("last_used")
            duration   = skill.get("duration_months", 0)
            complexity = skill.get("complexity", 1)
        if name:
            skill_scores[name.strip().lower()] = _raw_skill_score(
                last_used, duration, complexity
            )

    return json.dumps({
        "employee_email": employee_email,
        "job_id":         job_id,
        "skill_scores":   skill_scores,
    })


@tool
def expand_employee_knowledge_graph(employee_email: str) -> str:
    """
    BFS-expand an employee's knowledge graph using the KG.

    Starts from every directly-known skill (seed = normalised raw_score) and
    traverses up to MAX_HOPS=4 hops bidirectionally through the global KG +
    the employee's personal adjacency list.

    Each hop multiplies the score by HOP_DECAY × EDGE_W[rel_type] × neo4j_weight.

    Returns a map of every reachable skill → final coefficient.
    """
    logger.info("[ScoringAgent] Tool called: expand_employee_knowledge_graph(employee=%s)", employee_email)
    emp = next((e for e in _ctx.get("employees", []) if e["email"] == employee_email), None)
    if emp is None:
        logger.warning("[ScoringAgent] expand_employee_knowledge_graph: employee %r not found", employee_email)
        return json.dumps({"error": f"Employee {employee_email!r} not found"})

    vec = _build_employee_vector(emp)
    direct_set = {
        (s if isinstance(s, str) else s.get("name", "")).strip().lower()
        for s in emp.get("skills", [])
    }
    inferred = {k: v for k, v in vec.items() if k not in direct_set}
    logger.info(
        "[ScoringAgent] expand_employee_knowledge_graph: %s → %d direct, %d inferred skills",
        employee_email, len(direct_set & set(vec.keys())), len(inferred),
    )
    return json.dumps({
        "employee_email":     employee_email,
        "direct_skill_count": len(direct_set & set(vec.keys())),
        "inferred_count":     len(inferred),
        "inferred_skills":    inferred,
    })


@tool
def expand_job_requirements(job_id: str) -> str:
    """
    Show the BFS-expanded requirement vector for a job.

    Seeds are the required skills (each at coefficient 1.0 unless boosted by
    CoeffTuner).  BFS uses outgoing REQUIRES/EXTENDS/IMPLEMENTS edges.
    """
    logger.info("[ScoringAgent] Tool called: expand_job_requirements(job=%s)", job_id)
    job = next((j for j in _ctx.get("jobs", []) if j["job_id"] == job_id), None)
    if job is None:
        logger.warning("[ScoringAgent] expand_job_requirements: job %r not found", job_id)
        return json.dumps({"error": f"Job {job_id!r} not found"})

    required = [s.strip().lower() for s in job.get("required_skills", [])]
    weights  = _ctx.get("weights", {}).get(job_id, {})
    vec      = _build_job_vector(required, weights)
    logger.info(
        "[ScoringAgent] expand_job_requirements: job=%s  required=%d  vector_size=%d  weights=%s",
        job_id, len(required), len(vec), weights or "default(1.0)",
    )
    return json.dumps({
        "job_id":          job_id,
        "job_title":       job.get("title", ""),
        "required_skills": required,
        "vector_size":     len(vec),
        "top_skills":      dict(sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:20]),
    })


@tool
def compute_score_matrix() -> str:
    """
    Build the full (employees × jobs) adequacy score matrix.

    Procedure (identical to old pipeline matching_agent.compute_adequacy_matrix):
      1. Build employee profile vectors (bidirectional BFS, max-normalised seeds).
      2. Build job vectors (directional BFS from required skills).
      3. Adequacy = dot(profile, job / ‖job‖) clipped to [0, 1].
      4. Record matched / inferred / missing skills per pair.

    Stores the full matrix and details in _ctx (server reads them after the
    agent returns).  Returns ONLY a compact summary to the LLM to avoid 413
    payload errors.
    """
    employees = _ctx.get("employees", [])
    jobs      = _ctx.get("jobs", [])
    weights   = _ctx.get("weights", {})
    logger.info(
        "[ScoringAgent] Tool called: compute_score_matrix()  employees=%d  jobs=%d  weighted_jobs=%d",
        len(employees), len(jobs),
        sum(1 for jid, w in weights.items() if any(v != 1.0 for v in w.values())),
    )
    for job in jobs:
        jid = job["job_id"]
        w   = weights.get(jid, {})
        boosted = {s: v for s, v in w.items() if v != 1.0}
        if boosted:
            logger.info("[ScoringAgent]   job=%s  boosted_weights=%s", jid, boosted)

    if not employees or not jobs:
        _ctx["score_matrix"]  = []
        _ctx["score_details"] = []
        return json.dumps({
            "status":  "ok",
            "summary": {"n_employees": 0, "n_jobs": 0, "avg_score": 0.0, "max_score": 0.0},
        })

    # ── Build all employee vectors first (one BFS per employee) ────────────
    profile_vecs: list[dict[str, float]] = []
    profile_direct_sets: list[set[str]] = []
    for emp in employees:
        profile_vecs.append(_build_employee_vector(emp))
        profile_direct_sets.append({
            (s if isinstance(s, str) else s.get("name", "")).strip().lower()
            for s in emp.get("skills", [])
        })

    # ── Build all job vectors (one BFS per job) ────────────────────────────
    job_vecs: list[dict[str, float]] = []
    job_required: list[list[str]] = []
    job_norms: list[float] = []
    for job in jobs:
        required = [s.strip().lower() for s in job.get("required_skills", [])]
        seed_w   = weights.get(job["job_id"], {})
        vec      = _build_job_vector(required, seed_w)
        norm     = math.sqrt(sum(c * c for c in vec.values())) or 1.0
        job_vecs.append(vec)
        job_required.append(required)
        job_norms.append(norm)

    # ── Compute adequacy matrix ────────────────────────────────────────────
    score_matrix: list[list[float]] = []
    details:      list[dict]        = []

    for i, emp in enumerate(employees):
        emp_vec       = profile_vecs[i]
        emp_direct    = profile_direct_sets[i]
        row: list[float] = []

        for j, job in enumerate(jobs):
            jid      = job["job_id"]
            required = job_required[j]
            job_vec  = job_vecs[j]
            norm     = job_norms[j]

            if not required:
                row.append(0.0)
                details.append({
                    "employee":        emp["email"],
                    "job":             jid,
                    "score":           0.0,
                    "matched_skills":  [],
                    "inferred_skills": [],
                    "missing_skills":  [],
                })
                continue

            # dot(profile, job_norm)
            dot = 0.0
            for skill, coeff in job_vec.items():
                p = emp_vec.get(skill, 0.0)
                if p:
                    dot += p * (coeff / norm)
            score = round(min(max(dot, 0.0), 1.0), 4)

            matched  = [s for s in required if s in emp_direct]
            inferred = [s for s in required if s not in emp_direct and emp_vec.get(s, 0.0) > 0]
            missing  = [s for s in required if emp_vec.get(s, 0.0) == 0.0]

            row.append(score)
            details.append({
                "employee":        emp["email"],
                "job":             jid,
                "score":           score,
                "matched_skills":  matched,
                "inferred_skills": inferred,
                "missing_skills":  missing,
            })

        score_matrix.append(row)

    all_scores = [s for row in score_matrix for s in row]
    summary = {
        "n_employees": len(employees),
        "n_jobs":      len(jobs),
        "avg_score":   round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0,
        "max_score":   round(max(all_scores), 3) if all_scores else 0.0,
    }

    _ctx["score_matrix"]  = score_matrix
    _ctx["score_details"] = details

    logger.info(
        "[ScoringAgent] compute_score_matrix result: %dx%d  avg=%.3f  max=%.3f",
        summary["n_employees"], summary["n_jobs"], summary["avg_score"], summary["max_score"],
    )
    return json.dumps({"status": "ok", "summary": summary})
