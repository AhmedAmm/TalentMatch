"""
matching_pipeline_v2/search_service.py
========================================
Candidate search and scoring for the manual-swap / candidate-ranking flow.

Architecture
------------
Single source of truth: this module delegates ALL scoring math to
``scoring_agent.tools`` so the manual-swap UI gets the exact same numbers
as the full pipeline.  The only differences vs the full pipeline are:
  - Filtering happens in Python (available=True, not in project)
  - Score matrix is built for ONE job × N employees (not full grid)
  - No A2A round-trip — runs in-process for low latency

Scoring formulas (verbatim from old pipeline; see scoring_agent.tools)
---------------------------------------------------------------------
  Employee BFS : bidirectional, MAX_HOPS=4, HOP_DECAY=0.55, EDGE_W per rel type
  Job BFS      : outgoing REQUIRES/EXTENDS/IMPLEMENTS only, same hop math
  Adequacy     : dot(profile, job / ‖job‖) clipped to [0, 1]
"""
from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from matching_pipeline_v2.scoring_agent.tools import (
    _build_employee_vector as _agent_build_employee_vector,
    _build_job_vector      as _agent_build_job_vector,
)

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scoring")


# ---------------------------------------------------------------------------
# KG helpers (singleton accessors)
# ---------------------------------------------------------------------------

def _get_kg() -> dict[str, dict[str, float]]:
    from matching_pipeline_v2.knowledge_graph import get_kg
    return get_kg()


def refresh_kg() -> None:
    from matching_pipeline_v2.knowledge_graph import invalidate_kg_cache
    invalidate_kg_cache()


# ---------------------------------------------------------------------------
# Job format normalisation (DB → pipeline)
# ---------------------------------------------------------------------------

def _required_skills(job: dict) -> list[str]:
    """
    Flat, lowercase, deduplicated list of required skill names.

    Handles DB format (`required_stack: [{skill, level}]`) and pipeline format
    (`required_skills: [str]`).
    """
    raw = job.get("required_stack") or job.get("required_skills") or []
    seen: set[str] = set()
    out: list[str] = []
    for s in raw:
        if s is None:
            continue
        name = s["skill"] if isinstance(s, dict) else s
        if isinstance(name, str):
            key = name.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


# ---------------------------------------------------------------------------
# Single (employee, job) score (uses agent math)
# ---------------------------------------------------------------------------

def _ensure_agent_ctx_kg(kg: dict[str, dict[str, float]] | None) -> None:
    """
    Make sure the scoring agent's ``_ctx`` has the global KG before BFS runs.

    The agent's _DictKGShim fallback reads ``_ctx['global_knowledge_graph']``
    when no real GraphStore is loaded (e.g. unit tests).  This helper sets
    that key so the search service produces the same scores as the full
    pipeline path.
    """
    if kg is None:
        kg = _get_kg()
    from matching_pipeline_v2.scoring_agent import tools as _agent_tools
    if not _agent_tools._ctx.get("global_knowledge_graph"):
        _agent_tools._ctx["global_knowledge_graph"] = kg


def _build_job_vector(
    required: list[str],
    kg: dict[str, dict[str, float]] | None = None,
    max_depth: int = 4,
) -> dict[str, float]:
    """
    BFS-expanded job vector. Delegates to scoring_agent.tools._build_job_vector
    which uses outgoing REQUIRES/EXTENDS/IMPLEMENTS only when the real KG is
    loaded; otherwise falls back to the in-context dict shim.
    """
    _ensure_agent_ctx_kg(kg)
    return _agent_build_job_vector(required, seed_weights=None)


def _build_employee_vector(
    employee: dict,
    kg: dict[str, dict[str, float]] | None = None,
    max_depth: int = 4,
) -> dict[str, float]:
    """Bidirectional BFS employee vector. Delegates to scoring_agent.tools."""
    _ensure_agent_ctx_kg(kg)
    return _agent_build_employee_vector(employee)


def _score_employee(
    employee: dict,
    required: list[str],
    kg: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """
    Compute the matching score + skill breakdown for one (employee, job) pair.

    Uses the SAME formula as the full pipeline:
        score = dot(profile_vec, job_vec / ‖job_vec‖) clipped to [0, 1]

    Returns
    -------
    {
      matching_score   : float in [0, 1]
      matched_skills   : required skills the employee directly holds
      inferred_skills  : required skills reached only via BFS
      missing_skills   : required skills with zero coverage
    }
    """
    if not required:
        return {
            "matching_score":  0.0,
            "matched_skills":  [],
            "inferred_skills": [],
            "missing_skills":  [],
        }

    _ensure_agent_ctx_kg(kg)
    job_vec = _agent_build_job_vector(required, seed_weights=None)
    emp_vec = _agent_build_employee_vector(employee)

    direct_set = {
        (s if isinstance(s, str) else s.get("name", "")).strip().lower()
        for s in employee.get("skills", [])
    }

    norm = math.sqrt(sum(c * c for c in job_vec.values())) or 1.0
    dot = 0.0
    for skill, coeff in job_vec.items():
        p = emp_vec.get(skill, 0.0)
        if p:
            dot += p * (coeff / norm)
    score = round(min(max(dot, 0.0), 1.0), 4)

    matched  = [s for s in required if s in direct_set]
    inferred = [s for s in required if s not in direct_set and emp_vec.get(s, 0.0) > 0]
    missing  = [s for s in required if emp_vec.get(s, 0.0) == 0.0]

    return {
        "matching_score":  score,
        "matched_skills":  matched,
        "inferred_skills": inferred,
        "missing_skills":  missing,
    }


# ---------------------------------------------------------------------------
# Explanation builder (rich, mirrors Explanation Agent without LLM)
# ---------------------------------------------------------------------------

def _bfs_path(
    start: str,
    target: str,
    kg: dict[str, dict[str, float]],
    max_depth: int = 2,
) -> list[str] | None:
    if start == target:
        return [start]
    visited: set[str] = {start}
    queue: deque[list[str]] = deque([[start]])
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for nb in kg.get(path[-1], {}):
            if nb == target:
                return path + [nb]
            if nb not in visited:
                visited.add(nb)
                queue.append(path + [nb])
    return None


def _build_explanation(
    employee: dict,
    job_title: str,
    score: float,
    matched: list[str],
    inferred: list[str],
    missing: list[str],
    kg: dict[str, dict[str, float]],
) -> str:
    """Concise, evidence-backed explanation (no LLM call)."""
    emp_name  = employee.get("name", employee["email"])
    n_missing = len(missing)

    if score >= 0.80 and n_missing <= 1:
        verdict = "STRONG HIRE"
    elif score >= 0.60:
        verdict = "HIRE"
    elif score >= 0.40:
        verdict = "CONSIDER"
    else:
        verdict = "PASS"

    skill_lookup: dict[str, Any] = {}
    for s in employee.get("skills", []):
        name = s if isinstance(s, str) else s.get("name", "")
        if name:
            skill_lookup[name.strip().lower()] = s

    _level = {1: "basic", 2: "intermediate", 3: "expert"}

    direct_parts: list[str] = []
    for key in matched:
        rec = skill_lookup.get(key)
        if isinstance(rec, dict):
            yrs = round(rec.get("duration_months", 0) / 12, 1)
            lvl = _level.get(rec.get("complexity", 1), "basic")
            year = str(rec.get("last_used", ""))[:4]
            desc = f"{key} ({yrs}y {lvl}"
            if year:
                desc += f", last {year}"
            desc += ")"
            direct_parts.append(desc)
        else:
            direct_parts.append(key)

    inferred_parts: list[str] = []
    for inf_skill in inferred:
        for seed in matched:
            path = _bfs_path(seed, inf_skill, kg)
            if path:
                inferred_parts.append(f"{inf_skill} via {' → '.join(path)}")
                break
        else:
            inferred_parts.append(inf_skill)

    total   = len(matched) + len(inferred) + n_missing
    cov_pct = round((len(matched) + len(inferred)) / max(total, 1) * 100)

    parts: list[str] = [
        f"{emp_name} — {round(score * 100)}/100 [{verdict}] for '{job_title}'.",
        f"Coverage: {cov_pct}% ({len(matched)} direct, {len(inferred)} inferred).",
    ]
    if direct_parts:
        shown = direct_parts[:4]
        tail  = f" (+{len(direct_parts) - 4} more)" if len(direct_parts) > 4 else ""
        parts.append("Strengths: " + ", ".join(shown) + tail + ".")
    if inferred_parts:
        parts.append("KG: " + "; ".join(inferred_parts[:3]) + ".")
    if missing:
        shown = missing[:3]
        tail  = f" (+{n_missing - 3} more)" if n_missing > 3 else ""
        parts.append(f"Gaps: {', '.join(shown)}{tail}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Batch scoring (CPU-bound, runs in thread executor)
# ---------------------------------------------------------------------------

def _score_all(
    employees: list[dict],
    job: dict,
    required: list[str],
) -> list[dict]:
    """Score every employee against one job; return sorted desc."""
    kg        = _get_kg()
    job_id    = str(job.get("job_id", job.get("_id", "")))
    job_title = job.get("title", job_id)
    results: list[dict] = []

    for emp in employees:
        s = _score_employee(emp, required)
        name  = emp.get("name", "") or ""
        email = emp["email"]
        results.append({
            # frontend aliases
            "id":    email,
            "name":  name,
            "email": email,
            # pipeline aliases
            "employee_id":     email,
            "employee_name":   name,
            "matching_score":  s["matching_score"],
            "matched_skills":  s["matched_skills"],
            "inferred_skills": s["inferred_skills"],
            "missing_skills":  s["missing_skills"],
            "explanation": _build_explanation(
                emp, job_title,
                s["matching_score"],
                s["matched_skills"],
                s["inferred_skills"],
                s["missing_skills"],
                kg,
            ),
        })

    results.sort(key=lambda r: r["matching_score"], reverse=True)
    return results


def _enrich_with_llm_explanations(
    results: list[dict],
    job_id: str,
    job_title: str,
    employees: list[dict],
    kg: dict[str, dict[str, float]],
) -> None:
    """Call the explanation agent to replace template explanations with LLM text (in-place)."""
    from matching_pipeline_v2.explanation_agent.agent import run_agent
    import json

    emp_map = {e["email"]: e for e in employees}

    assignments = [
        {
            "employee_email":  r["employee_id"],
            "employee_name":   r["employee_name"],
            "job_id":          job_id,
            "job_title":       job_title,
            "score":           r["matching_score"],
            "matched_skills":  r["matched_skills"],
            "inferred_skills": r["inferred_skills"],
            "missing_skills":  r["missing_skills"],
        }
        for r in results
    ]

    context = {
        "assignments":            assignments,
        "employees":              list(emp_map.values()),
        "global_knowledge_graph": kg,
        "xai_report":             {},
    }

    raw = json.loads(run_agent(context))
    explanations = raw.get("explanations", [])

    explain_map = {
        (e["employee_email"], e["job_id"]): e
        for e in explanations
    }

    for r in results:
        entry = explain_map.get((r["employee_id"], job_id))
        if entry and entry.get("summary"):
            r["explanation"]     = entry["summary"]
            r["recommendation"]  = entry.get("recommendation", "consider")


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def search_employees_for_job(
    job_id: str,
    project_id: str,
    limit: int = 50,
    min_score: float = 0.0,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """
    Rank all eligible employees for a job.

    Filters before scoring:
      1. available == True
      2. Not already assigned to project_id
      3. Not in exclude_ids
    """
    from db.operations import get_job, list_employees, get_project_assigned_employee_ids

    job = await get_job(job_id)
    if not job:
        logger.warning("[SearchService] Job '%s' not found.", job_id)
        return []

    required = _required_skills(job)
    if not required:
        logger.warning("[SearchService] Job '%s' has no required skills.", job_id)

    already_assigned = await get_project_assigned_employee_ids(project_id)
    blocked          = already_assigned | (exclude_ids or set())

    employees = await list_employees(available=True)
    eligible  = [e for e in employees if e["email"] not in blocked]

    if not eligible:
        return []

    logger.info(
        "[SearchService] Scoring %d eligible employees for job '%s'.",
        len(eligible), job_id,
    )

    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        _EXECUTOR, _score_all, eligible, job, required
    )

    filtered = [r for r in results if r["matching_score"] >= min_score][:limit]
    for r in filtered:
        r["score_percentage"] = round(r["matching_score"] * 100)

    # Enrich filtered results with LLM explanations (runs in thread to avoid blocking event loop).
    if filtered:
        job_id_str = str(job.get("job_id", job.get("_id", job_id)))
        job_title  = job.get("title", job_id_str)
        emp_map    = {e["email"]: e for e in eligible}
        await loop.run_in_executor(
            _EXECUTOR,
            _enrich_with_llm_explanations,
            filtered, job_id_str, job_title,
            list(emp_map.values()),
            _get_kg(),
        )

    return filtered


async def find_best_replacement(job_id: str, project_id: str) -> dict | None:
    """Find and assign the best unassigned candidate after a rejection."""
    from db.operations import create_assignment

    candidates = await search_employees_for_job(job_id, project_id, limit=1, min_score=0.0)
    if not candidates:
        return None

    best   = candidates[0]
    emp_id = best["employee_id"]
    score  = best["matching_score"]

    try:
        from db.operations import update_assignment_fields
        new_asgn = await create_assignment(
            employee_id = emp_id,
            project_id  = project_id,
            job_id      = job_id,
            assigned_by = "pipeline_replacement",
            notes       = "",
        )
        await update_assignment_fields(
            str(new_asgn["_id"]),
            explanation    = best.get("explanation", ""),
            adequacy_score = score,
        )
    except (ValueError, Exception) as exc:
        logger.warning("[SearchService] Auto-assign failed %s → %s: %s", emp_id, job_id, exc)
        return None

    return {
        "assignment_id":   str(new_asgn["_id"]),
        "employee_id":     emp_id,
        "name":            best.get("employee_name", emp_id),
        "employeeName":    best.get("employee_name", emp_id),
        "matchScore":      score,
        "matching_score":  score,
        "scorePercentage": round(score * 100),
        "matched_skills":  best.get("matched_skills", []),
        "missing_skills":  best.get("missing_skills", []),
        "explanation":     best.get("explanation", ""),
    }


def build_explanation_text(
    job_id: str,
    employee_id: str,
    score: float = 0.0,
    matched_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
) -> str:
    """Lightweight template fallback for callers without full context."""
    matched = matched_skills or []
    missing = missing_skills or []
    pct     = round(score * 100)

    if not matched and not missing:
        return f"Match score: {pct}/100."

    parts = [f"Match score: {pct}/100."]
    if matched:
        shown = matched[:5]
        tail  = f" and {len(matched) - 5} more" if len(matched) > 5 else ""
        parts.append(f"Covers: {', '.join(shown)}{tail}.")
    if missing:
        shown = missing[:3]
        tail  = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
        parts.append(f"Gaps: {', '.join(shown)}{tail}.")

    return " ".join(parts)
