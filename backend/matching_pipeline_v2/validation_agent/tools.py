"""
matching_pipeline_v2/validation_agent/tools.py
================================================
LangChain tools used by the Validation Agent's ReAct brain.

The Validation Agent assesses the quality of the current Hungarian assignment
and decides whether to FINALIZE or ADJUST weights for another iteration.

Tool 1 — analyze_assignment_quality (XAI)
    Explainable analysis of every assigned (employee, job) pair.
    Reports: coverage ratio, semantic gaps, quality score per job, and
    an overall assessment with bottleneck detection.

Tool 2 — trace_skill_inference_path
    Given an employee and a skill that was inferred through the knowledge
    graph, reconstructs the BFS path:
        seed_skill → hop1 → … → inferred_skill
    Useful for explaining WHY a candidate is considered for a skill they
    don't directly hold.

Tool 3 — structure_adjustment_report
    Called by the LLM when it decides to ADJUST.  Consolidates the XAI
    findings into a structured JSON report that the orchestrator passes
    verbatim to the CoeffTuner agent, including per-job gap priorities and
    recommended boost magnitudes.
"""
from __future__ import annotations

import json
import math
from collections import deque
from typing import Any

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request context — injected before agent invocation
# ---------------------------------------------------------------------------
_ctx: dict[str, Any] = {}


def set_context(data: dict) -> None:
    """
    Inject the A2A request payload into the module-level context.

    Expected keys: assignments, jobs, global_knowledge_graph, score_details.
    """
    _ctx.clear()
    _ctx.update(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_kg() -> dict[str, dict[str, float]]:
    """
    Return the merged weighted KG (Neo4j global + all employees' personal edges).

    The global_knowledge_graph in context is already a WeightedKG loaded from
    Neo4j by knowledge_graph.load_kg().  Personal edges use weight 1.0.
    """
    from matching_pipeline_v2.knowledge_graph import merge_with_personal
    global_kg: dict[str, dict[str, float]] = _ctx.get("global_knowledge_graph", {})
    # Merge personal KGs from all assignments' employees
    merged = dict(global_kg)
    for assignment in _ctx.get("assignments", []):
        personal = assignment.get("employee_knowledge_graph", {})
        if personal:
            merged = merge_with_personal(merged, personal)
    return merged


def _bfs_path(
    start: str, target: str, kg: dict[str, dict[str, float]], max_depth: int = 2
) -> list[str] | None:
    """BFS shortest path from start → target in the weighted KG."""
    if start == target:
        return [start]
    visited = {start}
    queue: deque[list[str]] = deque([[start]])
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for neighbour in kg.get(path[-1], {}):
            if neighbour == target:
                return path + [neighbour]
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    return None


def _neighbours_in_kg(skill: str, kg: dict[str, dict[str, float]]) -> list[str]:
    """Return all skills reachable within 2 hops from the given skill."""
    reachable: set[str] = set()
    for n1 in kg.get(skill, {}):
        reachable.add(n1)
        reachable.update(kg.get(n1, {}).keys())
    return sorted(reachable)


# ---------------------------------------------------------------------------
# Tool 1: XAI assignment quality analysis
# ---------------------------------------------------------------------------

@tool
def analyze_assignment_quality() -> str:
    """
    Run an explainable quality analysis over all current assignments.

    For each (employee, job) assignment this tool computes:
      - coverage_ratio    : fraction of required skills covered (direct + inferred)
      - matched_skills    : required skills the employee directly holds
      - inferred_skills   : required skills covered via knowledge-graph hops
      - missing_skills    : required skills not covered at all
      - semantic_gaps     : missing skills that are close (≤2 hops) to skills
                            the employee DOES have (fixable gaps)
      - quality_score     : normalised 0–1 quality for this pair

    Also produces collective_gaps: skills that are missing from EVERY employee
    assigned to a given job (structural gaps not fixable by reordering).

    Overall output includes avg_score, min_score, n_poor_fits (score < 0.4),
    and a bottleneck_employees list (employees covering disproportionately few
    required skills).

    Returns a comprehensive JSON report.
    """
    assignments: list[dict] = _ctx.get("assignments", [])
    jobs: list[dict] = _ctx.get("jobs", [])
    kg: dict[str, dict[str, float]] = _build_kg()

    logger.info(
        "[ValidationAgent] Tool called: analyze_assignment_quality()  assignments=%d  jobs=%d",
        len(assignments), len(jobs),
    )

    if not assignments:
        return json.dumps({
            "avg_score":        0.0,
            "min_score":        0.0,
            "collective_gaps":  {},
            "job_reports":      [],
            "bottlenecks":      [],
            "overall_quality":  "no_assignments",
        })

    # Index assignments by job_id for easy lookup
    assignments_by_job: dict[str, list[dict]] = {}
    for a in assignments:
        assignments_by_job.setdefault(a["job_id"], []).append(a)

    job_reports: list[dict] = []
    collective_gaps: dict[str, list[str]] = {}

    for job in jobs:
        jid       = job["job_id"]
        required  = [s.strip().lower() for s in job.get("required_skills", [])]
        job_assignments = assignments_by_job.get(jid, [])

        if not job_assignments or not required:
            continue

        # Start collective gap set as full required set, then intersect
        gap_set = set(required)
        per_assignment_reports: list[dict] = []

        for a in job_assignments:
            matched  = [s.strip().lower() for s in a.get("matched_skills", [])]
            inferred = [s.strip().lower() for s in a.get("inferred_skills", [])]
            covered  = set(matched) | set(inferred)
            missing  = sorted(set(required) - covered)

            # Semantic gaps: missing skills that are neighbours of what we have
            emp_skills_set = set(matched) | set(inferred)
            semantic_gaps = [
                s for s in missing
                if any(s in _neighbours_in_kg(known, kg) for known in emp_skills_set)
            ]

            coverage_ratio = round(len(covered & set(required)) / len(required), 4) if required else 1.0
            quality_score  = round(
                0.6 * coverage_ratio + 0.4 * a.get("score", 0.0), 4
            )

            per_assignment_reports.append({
                "employee_email":  a["employee_email"],
                "employee_name":   a.get("employee_name", a.get("employee_email", "")),
                "score":           a.get("score", 0.0),
                "coverage_ratio":  coverage_ratio,
                "matched_skills":  matched,
                "inferred_skills": inferred,
                "missing_skills":  missing,
                "semantic_gaps":   semantic_gaps,
                "quality_score":   quality_score,
            })

            # Collective gap = missing from ALL assigned employees
            gap_set &= set(missing)

        if gap_set:
            collective_gaps[jid] = sorted(gap_set)

        avg_quality = round(
            sum(r["quality_score"] for r in per_assignment_reports) / len(per_assignment_reports), 4
        )
        job_reports.append({
            "job_id":           jid,
            "job_title":        job.get("title", ""),
            "avg_quality":      avg_quality,
            "collective_gaps":  sorted(gap_set),
            "assignments":      per_assignment_reports,
        })

    all_scores = [a.get("score", 0.0) for a in assignments]
    avg_score  = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0
    min_score  = round(min(all_scores), 4) if all_scores else 0.0

    # Bottleneck employees: assigned score significantly below the average
    bottlenecks = [
        {"employee": a["employee_name"], "score": a["score"], "job": a["job_id"]}
        for a in assignments
        if a.get("score", 0.0) < avg_score * 0.6
    ]

    n_poor_fits = sum(1 for s in all_scores if s < 0.4)

    report = {
        "avg_score":       avg_score,
        "min_score":       min_score,
        "n_poor_fits":     n_poor_fits,
        "collective_gaps": collective_gaps,
        "job_reports":     job_reports,
        "bottlenecks":     bottlenecks,
        "overall_quality": "good" if avg_score >= 0.6 else "acceptable" if avg_score >= 0.4 else "poor",
    }
    _ctx["_last_xai_report"] = report
    logger.info(
        "[ValidationAgent] analyze_assignment_quality result: avg=%.3f  min=%.3f  poor_fits=%d  collective_gaps=%s  quality=%s",
        avg_score, min_score, n_poor_fits,
        {jid: gaps for jid, gaps in collective_gaps.items()} or "none",
        report["overall_quality"],
    )
    return json.dumps(report)


# ---------------------------------------------------------------------------
# Tool 2: KG skill inference path tracer
# ---------------------------------------------------------------------------

@tool
def trace_skill_inference_path(employee_email: str, inferred_skill: str) -> str:
    """
    Reconstruct how an inferred skill was reached through the knowledge graph.

    Starting from all skills the employee directly holds, this tool runs BFS
    to find the shortest path in the knowledge graph that connects any direct
    skill to the target inferred_skill.

    Returns the full path:
        direct_skill → intermediate_skill → … → inferred_skill

    This is used to explain WHY a candidate is considered for a required skill
    they do not explicitly list in their profile.

    Args:
        employee_email: The employee's email identifier.
        inferred_skill: The skill that was inferred (normalised to lowercase).
    """
    logger.info(
        "[ValidationAgent] Tool called: trace_skill_inference_path(employee=%s, skill=%s)",
        employee_email, inferred_skill,
    )
    assignments = _ctx.get("assignments", [])
    emp_assignment = next(
        (a for a in assignments if a["employee_email"] == employee_email), None
    )
    if emp_assignment is None:
        return json.dumps({"error": f"No assignment found for {employee_email!r}"})

    target = inferred_skill.strip().lower()
    kg     = _build_kg()

    direct_skills = [s.strip().lower() for s in emp_assignment.get("matched_skills", [])]
    if not direct_skills:
        return json.dumps({
            "employee_email": employee_email,
            "target_skill":   target,
            "path":           None,
            "explanation":    "Employee has no directly matched skills to trace from.",
        })

    # Try each direct skill; return shortest path
    best_path: list[str] | None = None
    for seed in direct_skills:
        path = _bfs_path(seed, target, kg)
        if path is not None and (best_path is None or len(path) < len(best_path)):
            best_path = path

    if best_path is None:
        return json.dumps({
            "employee_email": employee_email,
            "target_skill":   target,
            "path":           None,
            "explanation":    f"No KG path found to '{target}' within 2 hops.",
        })

    # Annotate each hop with its edge weight from the Neo4j graph
    hop_details: list[dict] = []
    cumulative_weight = 1.0
    for i in range(len(best_path) - 1):
        src, dst   = best_path[i], best_path[i + 1]
        ew         = kg.get(src, {}).get(dst, 0.6)
        cumulative_weight *= ew
        hop_details.append({"from": src, "to": dst, "edge_weight": round(ew, 4)})

    steps       = " → ".join(best_path)
    explanation = (
        f"'{best_path[0]}' (direct skill) leads to '{target}' in "
        f"{len(best_path)-1} hop(s) with cumulative transfer weight "
        f"{round(cumulative_weight, 4)}: {steps}"
    )
    logger.info(
        "[ValidationAgent] trace_skill_inference_path result: %s → %s  path=%s  cumulative_weight=%.4f",
        employee_email, target, " → ".join(best_path), round(cumulative_weight, 4),
    )
    return json.dumps({
        "employee_email":    employee_email,
        "target_skill":      target,
        "path":              best_path,
        "hops":              len(best_path) - 1,
        "hop_details":       hop_details,
        "cumulative_weight": round(cumulative_weight, 4),
        "explanation":       explanation,
    })


# ---------------------------------------------------------------------------
# Tool 3: Adjustment report structurer
# ---------------------------------------------------------------------------

@tool
def structure_adjustment_report(xai_report_json: str) -> str:
    """
    Structure a prioritised adjustment report for the CoeffTuner agent.

    Call this tool when you decide the pipeline should ADJUST.  It consumes
    the XAI report (from analyze_assignment_quality) and produces a structured
    JSON that the orchestrator passes directly to the CoeffTuner agent.

    The report contains:
      - Per-job gap_priorities   : skill → priority score (0–1)
      - Collective gaps index    : jobs that have structural skill gaps
      - Recommended_alpha        : suggested boost magnitude (higher for worse gaps)
      - Rationale                : human-readable explanation of the decision

    Priority score formula:
        priority(skill, job) = 0.5 × (gap_severity) + 0.3 × (semantic_closeness) + 0.2 × (frequency)
    where:
        gap_severity       = 1.0  (skill is in collective gap, missing from ALL employees)
        semantic_closeness = 1.0 if skill has a semantic gap path; else 0.0
        frequency          = fraction of job assignments that miss this skill

    Args:
        xai_report_json: The raw JSON string returned by analyze_assignment_quality.
    """
    logger.info("[ValidationAgent] Tool called: structure_adjustment_report()")
    try:
        xai = json.loads(xai_report_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("[ValidationAgent] structure_adjustment_report: invalid XAI JSON: %s", exc)
        return json.dumps({"error": f"Invalid XAI report JSON: {exc}"})

    avg_score        = xai.get("avg_score", 0.0)
    collective_gaps  = xai.get("collective_gaps", {})
    job_reports      = xai.get("job_reports", [])

    gap_priorities_per_job: dict[str, dict[str, float]] = {}

    for jr in job_reports:
        jid          = jr["job_id"]
        c_gaps       = set(jr.get("collective_gaps", []))
        job_assignments = jr.get("assignments", [])
        n_assignments   = len(job_assignments) or 1

        # Collect all missing skills across assignments
        all_missing: dict[str, int] = {}   # skill → count of assignments missing it
        semantic_gap_skills: set[str] = set()

        for a in job_assignments:
            for s in a.get("missing_skills", []):
                all_missing[s] = all_missing.get(s, 0) + 1
            semantic_gap_skills.update(a.get("semantic_gaps", []))

        priorities: dict[str, float] = {}
        for skill, count in all_missing.items():
            gap_severity       = 1.0 if skill in c_gaps else 0.5
            semantic_closeness = 1.0 if skill in semantic_gap_skills else 0.0
            frequency          = count / n_assignments
            priority = round(
                0.5 * gap_severity + 0.3 * semantic_closeness + 0.2 * frequency, 4
            )
            priorities[skill] = priority

        if priorities:
            gap_priorities_per_job[jid] = dict(
                sorted(priorities.items(), key=lambda kv: kv[1], reverse=True)
            )

    # Recommend alpha: higher when quality is poor, lower when it's marginal
    if avg_score < 0.3:
        recommended_alpha = 0.8
    elif avg_score < 0.5:
        recommended_alpha = 0.5
    else:
        recommended_alpha = 0.3

    rationale = (
        f"Avg score {avg_score:.3f} with {len(collective_gaps)} job(s) having collective gaps. "
        f"Recommending coefficient boost (alpha={recommended_alpha}) for gap skills."
    )

    logger.info(
        "[ValidationAgent] structure_adjustment_report result: avg=%.3f  alpha=%.2f  gap_jobs=%d  rationale=%s",
        avg_score, recommended_alpha, len(gap_priorities_per_job), rationale,
    )
    return json.dumps({
        "decision":               "adjust",
        "avg_score":              avg_score,
        "collective_gaps":        collective_gaps,
        "gap_priorities_per_job": gap_priorities_per_job,
        "recommended_alpha":      recommended_alpha,
        "rationale":              rationale,
    })
