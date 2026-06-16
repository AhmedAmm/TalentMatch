"""
matching_pipeline_v2/explanation_agent/agent.py
=================================================
Explanation Agent — pure batched LLM call, NO ReAct.

Why no ReAct
------------
The previous multi-tool ReAct approach was broken on NVIDIA models:
  - Triggered "single tool-calls at once" 500 errors
  - Retried 9+ times before giving up (~150s per pipeline run)
  - Even when working, the LLM only called compile_explanation once
    per assignment — poor coherence, no shared context

This implementation mirrors the old pipeline's explain_agent.py exactly:

    1. Build a rich context block per (employee, job) — projects, KG paths,
       direct skill evidence, recommended verdict.
    2. Concatenate every candidate into ONE big prompt.
    3. Make ONE LLM call.
    4. Map the JSON response back to assignment records.

Caching
-------
Each (job_id, employee_id) explanation is cached in MongoDB
(collection: explanation_cache, TTL configurable via EXPLAIN_CACHE_TTL).
Repeat calls for the same pair return instantly without an LLM round-trip.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MongoDB-backed explanation cache
# ---------------------------------------------------------------------------

_EXPLAIN_CACHE_TTL: int = int(os.getenv("EXPLAIN_CACHE_TTL", "86400"))   # 24h default


def _cache_key(job_id: str, employee_id: str) -> str:
    return f"{job_id}__{employee_id}"


def _get_cached_explanation(cache_key: str) -> str | None:
    """Return cached explanation if it exists and isn't expired; else None."""
    try:
        from db.operations import db
        col = db["explanation_cache"]
        doc = col.find_one({"_id": cache_key})
        if not doc:
            return None
        created_at = doc.get("created_at")
        if created_at:
            age = (datetime.datetime.utcnow() - created_at).total_seconds()
            if age > _EXPLAIN_CACHE_TTL:
                col.delete_one({"_id": cache_key})
                return None
        return doc.get("explanation")
    except Exception as exc:
        logger.debug("[ExplainCache] Cache read failed: %s", exc)
        return None


def _store_cached_explanation(cache_key: str, explanation: str) -> None:
    """Persist an explanation to the MongoDB cache (best-effort)."""
    try:
        from db.operations import db
        db["explanation_cache"].replace_one(
            {"_id": cache_key},
            {
                "_id":         cache_key,
                "explanation": explanation,
                "created_at":  datetime.datetime.utcnow(),
            },
            upsert=True,
        )
    except Exception as exc:
        logger.debug("[ExplainCache] Cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Batched explanation prompt (verbatim style of old pipeline explain_agent.py)
# ---------------------------------------------------------------------------

_EXPLAIN_PROMPT_SINGLE = """\
You are a senior technical recruiter writing a hiring recommendation for an engineering team.

Write a compelling, human recommendation for the candidate below based ONLY on their \
real project experience and the technologies they have worked with.

LANGUAGE RULE: Write ONLY in English. Translate any French, Arabic, or other non-English \
terms naturally into English.

STRICT RULES:
- Do NOT mention any scores, coefficients, numbers, or ratings of any kind.
- Do NOT write generic filler sentences. Every sentence must reference something specific \
from their project history or skill background.
- For transferable knowledge: explain concretely how a technology they know maps to what \
the role needs (e.g. "Their experience with X means they can quickly adopt Y because both \
share Z").
- For skills to develop: frame positively as a short onboarding focus, not a weakness.
- Write 5-7 sentences.
- End with exactly: "VERDICT: [recommendation]" using the RECOMMENDED VERDICT provided.

CANDIDATE:
{candidate_block}

Return ONLY the recommendation text. No JSON, no markdown, no extra formatting.
"""


# ---------------------------------------------------------------------------
# KG path helper
# ---------------------------------------------------------------------------

def _bfs_path(
    start: str,
    target: str,
    kg: dict[str, dict[str, float]],
    max_depth: int = 2,
) -> list[str] | None:
    """Shortest path from start to target in the KG (≤ max_depth hops)."""
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


# ---------------------------------------------------------------------------
# Per-candidate context builder (rich block fed to the LLM)
# ---------------------------------------------------------------------------

_LEVEL_NAME = {1: "basic", 2: "intermediate", 3: "expert"}


def _build_candidate_block(
    assignment: dict,
    emp: dict,
    kg: dict[str, dict[str, float]],
    xai_assignment: dict | None = None,
) -> tuple[str, str, str]:
    """Build the (key, block_text, verdict) tuple for one assignment."""
    email     = assignment["employee_email"]
    job_id    = assignment["job_id"]
    job_title = assignment.get("job_title", job_id)

    matched  = [s.lower() for s in assignment.get("matched_skills", [])]
    inferred = [s.lower() for s in assignment.get("inferred_skills", [])]
    missing  = [s.lower() for s in assignment.get("missing_skills", [])]

    if xai_assignment:
        semantic_gaps  = xai_assignment.get("semantic_gaps", [])
        coverage_ratio = xai_assignment.get("coverage_ratio", 0.0)
        quality_score  = xai_assignment.get("quality_score", 0.0)
    else:
        semantic_gaps  = []
        coverage_ratio = 0.0
        quality_score  = 0.0

    # Skill metadata lookup
    skill_lookup: dict[str, Any] = {}
    for s in emp.get("skills", []):
        name = s if isinstance(s, str) else s.get("name", "")
        if name:
            skill_lookup[name.strip().lower()] = s

    # Direct evidence
    direct_parts: list[str] = []
    for key in matched:
        rec = skill_lookup.get(key)
        if isinstance(rec, dict):
            yrs  = round(rec.get("duration_months", 0) / 12, 1)
            lvl  = _LEVEL_NAME.get(rec.get("complexity", 1), "basic")
            year = str(rec.get("last_used", ""))[:4]
            desc = f"'{key}': {yrs}y at {lvl} level"
            if year:
                desc += f", last used in {year}"
            direct_parts.append(desc)
        else:
            direct_parts.append(f"'{key}'")

    # KG inference paths
    inferred_parts: list[str] = []
    for inf_skill in inferred:
        path = None
        for seed in matched:
            path = _bfs_path(seed, inf_skill, kg)
            if path:
                inferred_parts.append(
                    f"'{inf_skill}' inferred via: {' → '.join(path)}"
                )
                break
        if not path:
            inferred_parts.append(f"'{inf_skill}' (KG-adjacent)")

    # Project history
    project_lines: list[str] = []
    for proj in emp.get("projects", [])[:5]:
        if not isinstance(proj, dict):
            continue
        name  = proj.get("name", proj.get("client", proj.get("project_id", "Project")))
        role  = proj.get("role", "")
        techs = proj.get("technologies", [])
        line  = f"• {name}"
        if role:
            line += f" ({role})"
        if techs:
            line += f": {', '.join(str(t) for t in techs[:6])}"
        project_lines.append(line)

    # Verdict hint
    score = assignment.get("score", 0.0)
    if score >= 0.80 and len(missing) <= 1:
        verdict = "Strong Hire — Immediate Start"
    elif score >= 0.60:
        verdict = "Hire with Short Onboarding"
    elif score >= 0.40:
        verdict = "Consider — Assess Core Skills"
    else:
        verdict = "High Potential — Invest and Develop"

    key = f"{email}::{job_id}"
    sep = "=" * 60
    block = (
        f"KEY: {key}\n"
        f"CANDIDATE: {emp.get('name', email)}\n"
        f"ROLE: {job_title}\n\n"
        f"DIRECT EXPERIENCE (skills they hold that this role requires):\n"
        f"  {chr(10).join(direct_parts) if direct_parts else '(none matched)'}\n\n"
        f"TRANSFERABLE KNOWLEDGE (KG-inferred):\n"
        f"  {chr(10).join(inferred_parts) if inferred_parts else 'none'}\n\n"
        f"SKILLS TO DEVELOP (onboarding focus):\n"
        f"  {', '.join(missing) if missing else 'none identified'}\n"
        + (
            f"  (Reachable from existing skills via KG: {', '.join(semantic_gaps)})\n"
            if semantic_gaps else ""
        )
        + f"\nPROJECT HISTORY:\n"
        f"{chr(10).join(project_lines) if project_lines else '(no project history)'}\n\n"
        + (
            f"XAI QUALITY: coverage={round(coverage_ratio * 100)}%  "
            f"quality={round(quality_score, 2)}\n\n"
            if xai_assignment else ""
        )
        + f"RECOMMENDED VERDICT: {verdict}\n"
        f"{sep}"
    )
    return key, block, verdict


# ---------------------------------------------------------------------------
# Verdict → recommendation label
# ---------------------------------------------------------------------------

_VERDICT_TO_LABEL = {
    "Strong Hire": "strong_hire",
    "Hire": "hire",
    "Consider": "consider",
    "High Potential": "high_potential",
}


def _verdict_to_recommendation(verdict_text: str) -> str:
    for k, v in _VERDICT_TO_LABEL.items():
        if k in verdict_text:
            return v
    return "consider"


# ---------------------------------------------------------------------------
# Public entry point — single LLM call, batched, with cache
# ---------------------------------------------------------------------------

def run_agent(context: dict) -> str:
    """
    Build candidate blocks, fire ONE LLM call, return JSON {explanations: [...]}.

    Cache strategy:
      - Each (job_id, employee_id) pair is checked in the MongoDB cache first.
      - Only un-cached pairs are sent to the LLM (saves ~10-20s per cached pair).
      - Fresh LLM responses are written back to the cache for next time.

    Parameters
    ----------
    context : dict with keys assignments, employees, global_knowledge_graph, xai_report

    Returns
    -------
    str — JSON: { "explanations": [ ... ] }
    """
    from services.llm import ask_llm

    assignments = context.get("assignments", [])
    employees   = context.get("employees", [])
    kg          = context.get("global_knowledge_graph", {})
    xai_report  = context.get("xai_report", {})

    if not assignments:
        return json.dumps({"explanations": []})

    emp_map = {e["email"]: e for e in employees}

    # Build XAI lookup: (email, job_id) → quality data
    xai_lookup: dict[tuple[str, str], dict] = {}
    for jr in xai_report.get("job_reports", []):
        jid = jr.get("job_id", "")
        for ar in jr.get("assignments", []):
            em = ar.get("employee_email", "")
            if em and jid:
                xai_lookup[(em, jid)] = ar

    # ── Pass 1: split into cached vs uncached ────────────────────────────────
    cached_results: dict[str, str] = {}     # key → explanation text
    uncached_blocks: list[str] = []
    uncached_keys:   list[str] = []
    verdicts:        dict[str, str] = {}    # key → verdict
    valid_assignments: list[dict] = []      # in original order

    for a in assignments:
        email = a["employee_email"]
        emp   = emp_map.get(email)
        if not emp:
            continue
        valid_assignments.append(a)

        key, block, verdict = _build_candidate_block(
            a, emp, kg, xai_assignment=xai_lookup.get((email, a["job_id"]))
        )
        verdicts[key] = verdict

        cached = _get_cached_explanation(_cache_key(a["job_id"], email))
        if cached:
            cached_results[key] = cached
        else:
            uncached_blocks.append(block)
            uncached_keys.append(key)

    logger.info(
        "[ExplanationAgent] %d cached, %d new — %d individual LLM call(s)",
        len(cached_results), len(uncached_blocks), len(uncached_blocks),
    )

    # ── Pass 2: one LLM call per uncached assignment ─────────────────────────
    fresh_results: dict[str, str] = {}
    for idx, (block, key) in enumerate(zip(uncached_blocks, uncached_keys)):
        prompt = _EXPLAIN_PROMPT_SINGLE.format(candidate_block=block)
        try:
            text = ask_llm(prompt, json_mode=False).strip()
        except Exception as exc:
            logger.warning(
                "[ExplanationAgent] LLM call %d/%d failed for %s: %s",
                idx + 1, len(uncached_blocks), key, exc,
            )
            text = ""

        if not text:
            continue

        fresh_results[key] = text
        try:
            em, jid = key.split("::", 1)
            _store_cached_explanation(_cache_key(jid, em), text)
        except ValueError:
            pass

    # ── Pass 3: assemble results in the original assignment order ────────────
    results: list[dict] = []
    for a in valid_assignments:
        key  = f"{a['employee_email']}::{a['job_id']}"
        text = cached_results.get(key) or fresh_results.get(key, "")

        if not text:
            # Fallback: short template
            matched_str = ", ".join(a.get("matched_skills", [])[:3]) or "relevant skills"
            text = (
                f"{emp_map.get(a['employee_email'], {}).get('name', a['employee_email'])} "
                f"brings hands-on experience with {matched_str}, supporting the "
                f"{a.get('job_title', a['job_id'])} role. "
                f"VERDICT: {verdicts.get(key, 'Consider — Assess Core Skills')}"
            )

        verdict_text = ""
        if "VERDICT:" in text:
            verdict_text = text.split("VERDICT:")[-1].strip().split("\n")[0].strip()

        results.append({
            "employee_email":  a["employee_email"],
            "employee_name":   a.get("employee_name", ""),
            "job_id":          a["job_id"],
            "job_title":       a.get("job_title", a["job_id"]),
            "score":           a.get("score", 0.0),
            "matched_skills":  a.get("matched_skills", []),
            "inferred_skills": a.get("inferred_skills", []),
            "missing_skills":  a.get("missing_skills", []),
            "recommendation":  _verdict_to_recommendation(verdict_text or verdicts.get(key, "")),
            "summary":         text,
        })

    return json.dumps({"explanations": results})
