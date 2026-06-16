"""
matching_pipeline_v2/orchestrator.py
======================================
Deterministic orchestrator — Python loop, NO ReAct, NO LLM brain.

Pipeline steps
--------------
    for iteration in 1..MAX_ITER:
        call_scorer()        → (N×M) score matrix via Scoring Agent
        run_hungarian()      → one-employee-per-slot assignment (scipy)
        decision = call_validator()
        if decision == "finalize": break
        if iteration == MAX_ITER:  break
        call_coeff_tuner()   → boost gap-skill coefficients

    call_explanation()       → hire recommendations

Raindrop Workshop integration
------------------------------
Every run_pipeline() call opens a top-level Raindrop interaction.
Each step (scorer, hungarian, validator, tuner, explanation) is tracked
as a child tool span so you can watch the pipeline execute live in the
Workshop UI at http://localhost:5899.

State
-----
Module-level `_state` dict holds all data between steps.
"""
from __future__ import annotations

import json
import logging
import time

import numpy as np
import requests
from scipy.optimize import linear_sum_assignment

import matching_pipeline_v2.config as cfg

logger = logging.getLogger(__name__)

MAX_ITER: int = 3

# ---------------------------------------------------------------------------
# Module-level pipeline state (one run at a time)
# ---------------------------------------------------------------------------
_state: dict = {}


# ---------------------------------------------------------------------------
# Raindrop Workshop — per-run interaction handle
# Imported lazily so the orchestrator still works when raindrop-ai is absent.
# ---------------------------------------------------------------------------
_rd_ix = None   # active interaction for the current run_pipeline() call


def _rd_track(name: str, inp: dict, out: dict, duration_s: float) -> None:
    """Track one pipeline step as a Raindrop tool span (no-op if disabled)."""
    if _rd_ix is None:
        return
    try:
        _rd_ix.track_tool(
            name        = name,
            input       = inp,
            output      = out,
            duration_ms = duration_s * 1000,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# A2A helper
# ---------------------------------------------------------------------------

def _a2a_call(url: str, payload: dict) -> dict:
    """
    POST a JSON payload to an A2A agent's /a2a endpoint and return the parsed
    response dict.  Uses a 600-second timeout so long-running agents are never
    cut off mid-LLM-call.
    """
    msg = {
        "role": "user",
        "content": {"type": "text", "text": json.dumps(payload)},
    }
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/a2a",
            json=msg,
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()

        text = (
            (data.get("content") or {}).get("text")
            or next(
                (p.get("text") for p in data.get("parts", []) if p.get("type") == "text"),
                None,
            )
        )
        if not text or not text.strip():
            return {"error": "Agent returned empty response"}
        return json.loads(text)
    except json.JSONDecodeError as exc:
        return {"error": f"Agent returned non-JSON response: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"A2A call failed: {exc}"}
    except Exception as exc:
        return {"error": f"A2A call failed: {exc}"}


# ---------------------------------------------------------------------------
# Step 1 — Scoring Agent
# ---------------------------------------------------------------------------

def _step_scorer() -> bool:
    result = _a2a_call(cfg.SCORER_URL, {
        "employees":              _state["employees"],
        "jobs":                   _state["jobs"],
        "weights":                _state["weights"],
        "global_knowledge_graph": _state["global_knowledge_graph"],
    })

    if "error" in result:
        logger.error("[Orchestrator] Scoring failed: %s", result["error"])
        return False

    _state["score_matrix"]  = result.get("score_matrix", [])
    _state["score_details"] = result.get("details", [])

    summary = result.get("summary", {})
    logger.info(
        "[Orchestrator] Scoring: %dx%d matrix  avg=%.3f  max=%.3f",
        summary.get("n_employees", "?"), summary.get("n_jobs", "?"),
        summary.get("avg_score", 0), summary.get("max_score", 0),
    )
    _state["_scorer_summary"] = summary
    return True


# ---------------------------------------------------------------------------
# Step 2 — Hungarian (local scipy, multi-slot per job)
# ---------------------------------------------------------------------------

def _step_hungarian() -> bool:
    matrix = _state.get("score_matrix")
    if not matrix:
        logger.error("[Orchestrator] No score matrix — cannot run Hungarian.")
        return False

    employees = _state["employees"]
    jobs      = _state["jobs"]

    score_arr = np.array(matrix, dtype=float)
    n_emp, n_jobs = score_arr.shape

    job_slots: list[tuple[dict, int]] = []
    for col_idx, job in enumerate(jobs):
        posts = max(int(job.get("headcount", job.get("posts", 1))), 1)
        for _ in range(posts):
            job_slots.append((job, col_idx))
    n_slots = len(job_slots)

    expanded = np.zeros((n_emp, n_slots), dtype=float)
    for slot_j, (_, orig_col) in enumerate(job_slots):
        expanded[:, slot_j] = score_arr[:, orig_col]

    size = max(n_emp, n_slots)
    cost = np.ones((size, size), dtype=float)
    cost[:n_emp, :n_slots] = 1.0 - np.clip(expanded, 0.0, 1.0)
    row_idx, col_idx_arr = linear_sum_assignment(cost)

    detail_lookup: dict[tuple[str, str], dict] = {
        (d["employee"], d["job"]): d for d in _state.get("score_details", [])
    }

    assignments:      list[dict] = []
    assigned_emp_idx: set[int]   = set()

    for emp_i, slot_j in zip(row_idx, col_idx_arr):
        if emp_i >= n_emp or slot_j >= n_slots or emp_i in assigned_emp_idx:
            continue
        emp           = employees[emp_i]
        job, orig_col = job_slots[slot_j]
        score         = float(np.clip(expanded[emp_i, slot_j], 0.0, 1.0))
        if score == 0.0:
            continue

        detail = detail_lookup.get((emp["email"], job["job_id"]), {})
        assignments.append({
            "employee_email":  emp["email"],
            "employee_name":   emp.get("name", emp["email"]),
            "job_id":          job["job_id"],
            "job_title":       job.get("title", job["job_id"]),
            "score":           round(score, 4),
            "matched_skills":  detail.get("matched_skills", []),
            "inferred_skills": detail.get("inferred_skills", []),
            "missing_skills":  detail.get("missing_skills", []),
        })
        assigned_emp_idx.add(emp_i)

    assignments.sort(key=lambda a: a["score"], reverse=True)
    _state["assignments"] = assignments

    avg = round(sum(a["score"] for a in assignments) / max(len(assignments), 1), 3)
    logger.info(
        "[Orchestrator] Hungarian: %d assignment(s) across %d slot(s) (%d job(s))  avg=%.3f",
        len(assignments), n_slots, n_jobs, avg,
    )
    return True


# ---------------------------------------------------------------------------
# Step 3 — Validation Agent
# ---------------------------------------------------------------------------

def _step_validator() -> str:
    result = _a2a_call(cfg.VALIDATOR_URL, {
        "assignments":            _state.get("assignments", []),
        "jobs":                   _state["jobs"],
        "global_knowledge_graph": _state["global_knowledge_graph"],
    })

    if "error" in result:
        logger.warning(
            "[Orchestrator] Validation error (%s) — defaulting to FINALIZE.",
            result["error"],
        )
        _state["decision"]   = "finalize"
        _state["xai_report"] = {}
        return "finalize"

    decision = str(result.get("decision", "finalize")).lower().strip()
    if decision not in ("finalize", "adjust"):
        decision = "finalize"

    _state["decision"]          = decision
    _state["adjustment_report"] = result.get("adjustment_report")
    _state["xai_report"]        = result.get("xai_report", {})

    logger.info(
        "[Orchestrator] Validation: decision=%s  avg_score=%.3f  reasoning=%s",
        decision,
        result.get("avg_score", 0.0),
        (result.get("reasoning") or "")[:140],
    )
    return decision


# ---------------------------------------------------------------------------
# Step 4 — CoeffTuner Agent
# ---------------------------------------------------------------------------

def _step_coeff_tuner() -> bool:
    if not _state.get("adjustment_report"):
        logger.warning("[Orchestrator] No adjustment_report — skipping CoeffTuner.")
        return False

    result = _a2a_call(cfg.TUNER_URL, {
        "jobs":              _state["jobs"],
        "weights":           _state["weights"],
        "xai_report":        _state.get("xai_report", {}),
        "adjustment_report": _state["adjustment_report"],
    })

    if "error" in result:
        logger.warning(
            "[Orchestrator] CoeffTuner error: %s — keeping previous weights.",
            result["error"],
        )
        return False

    _state["weights"] = result.get("weights", _state["weights"])

    changes   = result.get("changes", {})
    n_updated = len(changes)
    logger.info("[Orchestrator] CoeffTuner: updated weights for %d job(s)", n_updated)
    for jid, ch in changes.items():
        boosted = ch.get("boosted_skills", [])
        old_w   = ch.get("old_weights", {})
        new_w   = ch.get("new_weights", {})
        for skill in boosted:
            logger.info(
                "[Orchestrator]   '%s' / '%s': %.3f → %.3f",
                jid, skill, old_w.get(skill, 1.0), new_w.get(skill, 1.0),
            )
    return True


# ---------------------------------------------------------------------------
# Step 5 — Explanation Agent
# ---------------------------------------------------------------------------

def _step_explanation() -> list[dict]:
    result = _a2a_call(cfg.EXPLANATION_URL, {
        "assignments":            _state.get("assignments", []),
        "employees":              _state["employees"],
        "global_knowledge_graph": _state["global_knowledge_graph"],
        "xai_report":             _state.get("xai_report", {}),
    })

    if "error" in result:
        logger.error(
            "[Orchestrator] Explanation error: %s — recommendations will be empty.",
            result["error"],
        )
        return []

    explanations = result.get("explanations", [])
    _state["explanations"] = explanations
    logger.info("[Orchestrator] Explanation: %d recommendation(s) generated", len(explanations))
    return explanations


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    employees: list[dict],
    jobs: list[dict],
    global_knowledge_graph: dict[str, dict[str, float]] | None = None,
) -> tuple[str, list[dict]]:
    """
    Run the full matching pipeline (deterministic Python loop).

    Parameters
    ----------
    employees : list of employee dicts (email, name, skills, knowledge_graph)
    jobs      : list of job dicts (job_id, title, required_skills, headcount)
    global_knowledge_graph : weighted KG from Neo4j (optional)

    Returns
    -------
    (summary_text, assignments)
    """
    global _rd_ix

    _state.clear()
    _state["employees"]              = employees
    _state["jobs"]                   = jobs
    _state["global_knowledge_graph"] = global_knowledge_graph or {}
    _state["assignments"]            = []
    _state["explanations"]           = []
    _state["weights"] = {
        job["job_id"]: {s.strip().lower(): 1.0 for s in job.get("required_skills", [])}
        for job in jobs
    }

    logger.info(
        "[Orchestrator] Starting — %d employee(s) × %d job(s), MAX_ITER=%d",
        len(employees), len(jobs), MAX_ITER,
    )

    # ── Open Raindrop interaction ─────────────────────────────────────────────
    _rd_ix = None
    try:
        from services.llm import begin_interaction, _RD_ENABLED
        if _RD_ENABLED:
            _rd_ix = begin_interaction(
                event      = "matching_pipeline",
                input_text = f"{len(employees)} employees × {len(jobs)} jobs",
                model      = cfg.NVIDIA_AGENT_MODEL,
                max_iter   = MAX_ITER,
            )
    except Exception:
        pass  # raindrop unavailable — continue without tracing

    iteration_used = 0
    final_decision = "finalize"

    # ── Main loop: scorer → hungarian → validator → (tuner) ──────────────────
    for iteration in range(1, MAX_ITER + 1):
        iteration_used = iteration
        logger.info("[Orchestrator] ─── Iteration %d/%d ──────────", iteration, MAX_ITER)

        # Step 1 — Scorer
        t = time.perf_counter()
        scorer_ok = _step_scorer()
        summary   = _state.get("_scorer_summary", {})
        _rd_track(
            "scoring_agent",
            inp={"iteration": iteration, "n_emp": len(employees), "n_jobs": len(jobs)},
            out={"ok": scorer_ok, "avg_score": summary.get("avg_score", 0),
                 "max_score": summary.get("max_score", 0)},
            duration_s=time.perf_counter() - t,
        )
        if not scorer_ok:
            break

        # Step 2 — Hungarian
        t = time.perf_counter()
        hungarian_ok = _step_hungarian()
        _rd_track(
            "hungarian_algorithm",
            inp={"n_emp": len(employees), "n_jobs": len(jobs), "n_slots": len(_state.get("assignments", []))},
            out={"ok": hungarian_ok, "n_assignments": len(_state.get("assignments", []))},
            duration_s=time.perf_counter() - t,
        )
        if not hungarian_ok:
            break

        # Step 3 — Validator
        t = time.perf_counter()
        decision       = _step_validator()
        final_decision = decision
        xai            = _state.get("xai_report", {})
        _rd_track(
            "validation_agent",
            inp={"n_assignments": len(_state.get("assignments", []))},
            out={"decision": decision,
                 "avg_score": xai.get("avg_score", 0),
                 "n_poor_fits": xai.get("n_poor_fits", 0)},
            duration_s=time.perf_counter() - t,
        )

        if decision == "finalize":
            logger.info("[Orchestrator] Validator → FINALIZE.  Stopping iterations.")
            break

        if iteration == MAX_ITER:
            logger.info("[Orchestrator] Reached MAX_ITER=%d — force-finalising.", MAX_ITER)
            break

        # Step 4 — CoeffTuner (only on ADJUST)
        t = time.perf_counter()
        tuner_ok = _step_coeff_tuner()
        gaps     = _state.get("xai_report", {}).get("collective_gaps", {})
        _rd_track(
            "coeff_tuner_agent",
            inp={"n_jobs_with_gaps": len(gaps)},
            out={"ok": tuner_ok,
                 "n_weight_maps": len(_state.get("weights", {}))},
            duration_s=time.perf_counter() - t,
        )

    # ── Step 5 — Explanations ─────────────────────────────────────────────────
    t            = time.perf_counter()
    explanations = _step_explanation()
    _rd_track(
        "explanation_agent",
        inp={"n_assignments": len(_state.get("assignments", []))},
        out={"n_explanations": len(explanations)},
        duration_s=time.perf_counter() - t,
    )

    # ── Merge explanations into assignments ───────────────────────────────────
    explain_lookup = {
        (e.get("employee_email"), e.get("job_id")): e
        for e in explanations
    }
    assignments = _state.get("assignments", [])
    for a in assignments:
        e = explain_lookup.get((a["employee_email"], a["job_id"]))
        if e:
            a["recommendation"] = e.get("recommendation", "consider")
            a["explanation"]    = e.get("summary", "")

    # ── Build summary ─────────────────────────────────────────────────────────
    avg_score = round(
        sum(a["score"] for a in assignments) / max(len(assignments), 1), 3
    )
    top_3 = [
        {"employee": a["employee_name"], "job": a["job_title"], "score": a["score"]}
        for a in assignments[:3]
    ]
    poor_fits = [
        {"employee": a["employee_name"], "job": a["job_title"], "score": a["score"]}
        for a in assignments if a["score"] < 0.4
    ]

    summary = {
        "iterations":     iteration_used,
        "decision":       final_decision,
        "n_assignments":  len(assignments),
        "avg_score":      avg_score,
        "top_3":          top_3,
        "poor_fits":      poor_fits,
        "n_explanations": len(explanations),
    }
    summary_text = json.dumps(summary, ensure_ascii=False)

    logger.info(
        "[Orchestrator] Done — iter=%d  decision=%s  assignments=%d  avg=%.3f",
        iteration_used, final_decision, len(assignments), avg_score,
    )

    # ── Close Raindrop interaction ────────────────────────────────────────────
    if _rd_ix is not None:
        try:
            from services.llm import finish_interaction
            finish_interaction(
                output     = summary_text,
                iterations = iteration_used,
                decision   = final_decision,
                avg_score  = avg_score,
                n_assignments = len(assignments),
            )
        except Exception:
            pass
        _rd_ix = None

    return summary_text, assignments
