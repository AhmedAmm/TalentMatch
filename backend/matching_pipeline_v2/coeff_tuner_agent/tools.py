"""
matching_pipeline_v2/coeff_tuner_agent/tools.py
=================================================
LangChain tools used by the CoeffTuner Agent's ReAct brain.

Architecture (matches old pipeline validator_agent.py coeff_tuner):
  - The LLM brain sees: collective gaps, job descriptions, current weights
  - It decides WHICH skills to boost and by HOW MUCH
  - apply_skill_weights() physically applies the LLM's decisions

Tool 1 — get_gap_context
    Presents the LLM with everything it needs to make weight decisions:
      • Collective gaps per job (skills missing from ALL assigned employees)
      • Per-job descriptions and current seed weights
      • Semantic gap skills (close to what employees know — easier to boost)
      • Average score context (how urgent the adjustment is)

    This mirrors the old pipeline's llm_tune_weights() prompt context.

Tool 2 — apply_skill_weights
    Takes the LLM's weight decisions (a dict of {job_id: {skill: new_weight}})
    and applies them with re-normalisation so coefficients average 1.0.

    Re-normalisation: target_sum = len(required_skills) → average = 1.0.
    This keeps the dot-product scoring scale stable across iterations.
"""
from __future__ import annotations

import json
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
    Inject the A2A request payload.

    Expected keys:
      jobs              : list of job dicts (job_id, title, required_skills)
      weights           : current { job_id: { skill: coeff } }
      xai_report        : full XAI quality report from the Validation Agent
      adjustment_report : structured gap priorities from structure_adjustment_report
    """
    _ctx.clear()
    _ctx.update(data)


# ---------------------------------------------------------------------------
# Tool 1: Gap context — what the LLM brain reads to make weight decisions
# ---------------------------------------------------------------------------

@tool
def get_gap_context() -> str:
    """
    Return everything the LLM needs to decide which skill weights to boost.

    Provides (per job):
      • collective_gaps     : skills missing from EVERY assigned employee
                              → structural under-weighting that MUST be fixed
      • current_weights     : existing coefficient per required skill
      • job_description     : title + required skills (to judge importance)
      • semantic_gap_skills : gaps that are close to skills employees already know
                              → easier to bridge with modest weight boosts
      • avg_score / urgency : how strongly to boost (more urgent = bigger boost)

    This is the equivalent of the old pipeline's context passed to llm_tune_weights().
    Use this information to decide the new weight map in apply_skill_weights().
    """
    logger.info("[CoeffTunerAgent] Tool called: get_gap_context()")
    jobs:    list[dict]         = _ctx.get("jobs", [])
    weights: dict[str, dict]    = _ctx.get("weights", {})
    xai:     dict               = _ctx.get("xai_report", {})
    adj:     dict               = _ctx.get("adjustment_report", {})

    avg_score = xai.get("avg_score", adj.get("avg_score", 0.0))

    # Map job_id → XAI job report for quick lookup
    xai_by_job = {jr["job_id"]: jr for jr in xai.get("job_reports", [])}

    # Collective gaps from either xai_report or adjustment_report
    collective_gaps: dict[str, list[str]] = (
        xai.get("collective_gaps")
        or adj.get("collective_gaps")
        or {}
    )

    context_per_job: list[dict] = []
    for job in jobs:
        jid      = job["job_id"]
        required = [s.strip().lower() for s in job.get("required_skills", [])]
        curr_w   = weights.get(jid, {})
        c_gaps   = collective_gaps.get(jid, [])
        jr       = xai_by_job.get(jid, {})

        # Semantic gap skills (reachable from what employees know)
        semantic_gaps: set[str] = set()
        for a_rep in jr.get("assignments", []):
            semantic_gaps.update(a_rep.get("semantic_gaps", []))

        context_per_job.append({
            "job_id":          jid,
            "job_title":       job.get("title", ""),
            "required_skills": required,
            "current_weights": {s: round(curr_w.get(s, 1.0), 4) for s in required},
            "collective_gaps": c_gaps,
            "semantic_gaps":   sorted(semantic_gaps & set(required)),
            "avg_job_quality": jr.get("avg_quality", 0.0),
        })

    # Urgency guidance for the LLM
    if avg_score < 0.3:
        urgency = "HIGH — scores are very low, use strong boosts (0.4–0.8 above baseline)"
    elif avg_score < 0.5:
        urgency = "MEDIUM — scores are below target, use moderate boosts (0.2–0.4 above baseline)"
    else:
        urgency = "LOW — scores are close to acceptable, use light boosts (0.1–0.2 above baseline)"

    logger.info(
        "[CoeffTunerAgent] get_gap_context result: avg_score=%.3f  urgency=%s  collective_gap_jobs=%s",
        avg_score, urgency.split(" ")[0],
        {jid: gaps for jid, gaps in collective_gaps.items()} or "none",
    )
    return json.dumps({
        "avg_score":       avg_score,
        "urgency":         urgency,
        "collective_gaps": collective_gaps,
        "jobs":            context_per_job,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: Apply weight decisions
# ---------------------------------------------------------------------------

@tool
def apply_skill_weights(weight_decisions: str) -> str:
    """
    Apply the LLM's weight decisions and re-normalise coefficients.

    Args:
        weight_decisions: JSON string with the new weight map decided by the LLM:
            {
              "job_id": {
                "skill_name": new_weight_float,
                ...
              },
              ...
            }
            Only skills explicitly boosted need to be included — other required
            skills retain their current weight (defaulting to 1.0 if never set).

    Re-normalisation:
        target_sum = len(required_skills)  →  average coefficient = 1.0
        This keeps the dot-product scoring scale stable across iterations.

    Returns JSON:
        weights : { job_id: { skill: normalised_coeff } }
        changes : { job_id: { boosted_skills, alpha_effective, old_weights, new_weights } }
    """
    logger.info("[CoeffTunerAgent] Tool called: apply_skill_weights()")
    logger.debug("[CoeffTunerAgent] apply_skill_weights input: %s", weight_decisions[:400])
    jobs:    list[dict]      = _ctx.get("jobs", [])
    current: dict[str, dict] = _ctx.get("weights", {})

    try:
        decisions: dict[str, dict[str, float]] = json.loads(weight_decisions)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("[CoeffTunerAgent] apply_skill_weights: invalid JSON: %s", exc)
        return json.dumps({"error": f"Invalid weight_decisions JSON: {exc}"})

    new_weights: dict[str, dict[str, float]] = {}
    changes:     dict[str, dict]             = {}

    for job in jobs:
        jid      = job["job_id"]
        required = [s.strip().lower() for s in job.get("required_skills", [])]
        if not required:
            new_weights[jid] = {}
            continue

        old_w    = current.get(jid, {})
        llm_w    = decisions.get(jid, {})
        boosted: dict[str, float] = {}

        for skill in required:
            old_c = old_w.get(skill, 1.0)
            # LLM-suggested weight overrides current; if not mentioned, keep current
            new_c = float(llm_w.get(skill, old_c))
            # Never let a coefficient drop below 0.1 or exceed 5.0
            boosted[skill] = max(0.1, min(new_c, 5.0))

        # Re-normalise: average coefficient = 1.0
        total  = sum(boosted.values())
        target = float(len(required))
        if total > 0:
            scale  = target / total
            boosted = {s: round(v * scale, 4) for s, v in boosted.items()}

        new_weights[jid] = boosted
        boosted_skills   = [s for s in required if boosted.get(s, 1.0) > old_w.get(s, 1.0) * 1.05]

        changes[jid] = {
            "boosted_skills": boosted_skills,
            "old_weights":    {s: round(old_w.get(s, 1.0), 4) for s in required},
            "new_weights":    boosted,
        }

    total_boosted = sum(len(v["boosted_skills"]) for v in changes.values())
    logger.info(
        "[CoeffTunerAgent] apply_skill_weights result: %d job(s) updated  total_boosted_skills=%d",
        len(new_weights), total_boosted,
    )
    for jid, ch in changes.items():
        boosted = ch.get("boosted_skills", [])
        if boosted:
            old_w = ch["old_weights"]
            new_w = ch["new_weights"]
            for skill in boosted:
                logger.info(
                    "[CoeffTunerAgent]   job=%s  skill=%s  %.4f → %.4f",
                    jid, skill, old_w.get(skill, 1.0), new_w.get(skill, 1.0),
                )
    return json.dumps({"weights": new_weights, "changes": changes})
