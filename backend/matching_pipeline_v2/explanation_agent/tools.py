"""
matching_pipeline_v2/explanation_agent/tools.py
=================================================
LangChain tools used by the Explanation Agent's ReAct brain.

The Explanation Agent runs after the pipeline FINALIZES.  For each
assignment it provides a concrete, evidence-backed hire recommendation
so that decision-makers have clear justification for every match.

Tool 1 — find_relevant_work_examples
    Extracts concrete evidence from the employee's skill profile:
      - For each matched required skill:  duration, complexity, recency
      - For each inferred skill:          the KG path that bridged the gap
      - Overall experience depth:         years of combined relevant experience

Tool 2 — assess_hire_recommendation
    Determines the recommendation level from the assignment score and
    skill-coverage profile:
      strong_hire  — score ≥ 0.80  AND ≤ 1 missing skill
      hire         — score ≥ 0.60
      consider     — score ≥ 0.40
      pass         — score < 0.40

Tool 3 — compile_explanation
    Combines the evidence and recommendation into a final natural-language
    summary entry for the given (employee, job) assignment.
"""
from __future__ import annotations

import json
from collections import deque
from typing import Any

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Request context — injected before agent invocation
# ---------------------------------------------------------------------------
_ctx: dict[str, Any] = {}


def set_context(data: dict) -> None:
    """
    Inject the A2A request payload.

    Expected keys:
      assignments            : list of assignment dicts
      employees              : list of employee dicts
      global_knowledge_graph : WeightedKG from Neo4j
      xai_report             : (optional) full XAI quality report from the
                               Validation Agent — provides coverage ratios,
                               semantic gaps, and quality scores per pair
    """
    _ctx.clear()
    _ctx.update(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_employee(email: str) -> dict | None:
    return next((e for e in _ctx.get("employees", []) if e["email"] == email), None)


def _get_assignment(employee_email: str, job_id: str) -> dict | None:
    return next(
        (a for a in _ctx.get("assignments", [])
         if a["employee_email"] == employee_email and a["job_id"] == job_id),
        None,
    )


def _build_kg() -> dict[str, dict[str, float]]:
    """Return the global weighted KG (loaded from Neo4j)."""
    return _ctx.get("global_knowledge_graph", {})


def _bfs_path(
    start: str, target: str, kg: dict[str, dict[str, float]], max_depth: int = 2
) -> list[str] | None:
    """BFS shortest path. Works on weighted adjacency dict (weights ignored for path finding)."""
    if start == target:
        return [start]
    visited = {start}
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


def _skill_description(skill_record: dict | str) -> str:
    """Convert a skill record into a human-readable experience statement."""
    if isinstance(skill_record, str):
        return f"'{skill_record}' (listed in profile, no detailed metadata)"

    name       = skill_record.get("name", "unknown")
    duration   = skill_record.get("duration_months", 0)
    complexity = skill_record.get("complexity", 1)
    last_used  = skill_record.get("last_used")

    level_map = {1: "basic", 2: "intermediate", 3: "expert"}
    level     = level_map.get(complexity, "basic")
    years     = round(duration / 12, 1)

    parts = [f"'{name}': {years} year(s) at {level} level"]
    if last_used:
        # ISO string → year only for brevity
        year_str = str(last_used)[:4]
        parts.append(f"last used in {year_str}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Tool 1: Work example extractor
# ---------------------------------------------------------------------------

@tool
def find_relevant_work_examples(employee_email: str, job_id: str) -> str:
    """
    Extract concrete evidence from the employee's profile for a specific job.

    For every required skill in the job:
      - If the employee directly holds it: returns duration, complexity level,
        and last-used year as a concrete experience statement.
      - If it was inferred through the knowledge graph: returns the BFS path
        that connects a direct skill to the required skill.
      - If it is missing entirely: flags it as a gap.

    Also computes total_relevant_months (sum of duration_months across
    matched skills) as a proxy for overall experience depth.

    Args:
        employee_email: The employee's email identifier.
        job_id:         The target job identifier.
    """
    emp        = _get_employee(employee_email)
    assignment = _get_assignment(employee_email, job_id)

    if emp is None:
        return json.dumps({"error": f"Employee {employee_email!r} not found"})
    if assignment is None:
        return json.dumps({"error": f"No assignment found for ({employee_email}, {job_id})"})

    # Build lookup: skill_name_lower → full skill record
    skill_lookup: dict[str, dict | str] = {}
    for s in emp.get("skills", []):
        name = s if isinstance(s, str) else s.get("name", "")
        if name:
            skill_lookup[name.strip().lower()] = s

    kg = _build_kg()
    matched   = [s.strip().lower() for s in assignment.get("matched_skills", [])]
    inferred  = [s.strip().lower() for s in assignment.get("inferred_skills", [])]
    missing   = [s.strip().lower() for s in assignment.get("missing_skills", [])]

    direct_examples: list[str] = []
    total_relevant_months = 0
    for skill_key in matched:
        record = skill_lookup.get(skill_key)
        if record:
            direct_examples.append(_skill_description(record))
            if isinstance(record, dict):
                total_relevant_months += record.get("duration_months", 0)

    inferred_examples: list[str] = []
    for skill_key in inferred:
        best_path = None
        for seed in matched:
            path = _bfs_path(seed, skill_key, kg)
            if path and (best_path is None or len(path) < len(best_path)):
                best_path = path
        if best_path:
            # Annotate with cumulative edge weight from Neo4j
            cumulative = 1.0
            for i in range(len(best_path) - 1):
                cumulative *= kg.get(best_path[i], {}).get(best_path[i + 1], 0.6)
            inferred_examples.append(
                f"'{skill_key}' inferred via KG path: {' → '.join(best_path)} "
                f"(transfer weight: {round(cumulative, 2)})"
            )
        else:
            inferred_examples.append(f"'{skill_key}' inferred (path not traceable)")

    gap_notes: list[str] = [f"'{s}' — not in profile or KG reach" for s in missing]

    return json.dumps({
        "employee_email":        employee_email,
        "job_id":                job_id,
        "score":                 assignment.get("score", 0.0),
        "direct_examples":       direct_examples,
        "inferred_examples":     inferred_examples,
        "gap_notes":             gap_notes,
        "total_relevant_months": total_relevant_months,
        "total_relevant_years":  round(total_relevant_months / 12, 1),
    })


# ---------------------------------------------------------------------------
# Tool 2: Hire recommendation assessor
# ---------------------------------------------------------------------------

@tool
def assess_hire_recommendation(employee_email: str, job_id: str) -> str:
    """
    Determine the hire recommendation level for an (employee, job) pair.

    Recommendation levels:
      strong_hire  — score ≥ 0.80 AND ≤ 1 missing required skill
      hire         — score ≥ 0.60
      consider     — score ≥ 0.40
      pass         — score < 0.40

    Also returns:
      key_strengths  : top matched/inferred skills (ordered by score contribution)
      gaps_to_address: missing skills the candidate should develop

    Args:
        employee_email: The employee's email identifier.
        job_id:         The target job identifier.
    """
    assignment = _get_assignment(employee_email, job_id)
    if assignment is None:
        return json.dumps({"error": f"No assignment found for ({employee_email}, {job_id})"})

    score   = assignment.get("score", 0.0)
    matched = assignment.get("matched_skills", [])
    inferred = assignment.get("inferred_skills", [])
    missing = assignment.get("missing_skills", [])

    n_missing = len(missing)
    key_strengths = sorted(set(matched + inferred))  # combined coverage

    if score >= 0.80 and n_missing <= 1:
        recommendation = "strong_hire"
        rationale      = (
            f"Exceptional skill coverage (score={score:.2f}) with only {n_missing} gap(s). "
            "Strongly recommend for this role."
        )
    elif score >= 0.60:
        recommendation = "hire"
        rationale      = (
            f"Good skill match (score={score:.2f}).  {n_missing} gap(s) are manageable "
            "with on-the-job training."
        )
    elif score >= 0.40:
        recommendation = "consider"
        rationale      = (
            f"Partial match (score={score:.2f}).  Candidate covers core skills but has "
            f"{n_missing} gap(s) that require assessment."
        )
    else:
        recommendation = "pass"
        rationale      = (
            f"Weak match (score={score:.2f}).  Too many critical skill gaps ({n_missing}) "
            "for this role at this time."
        )

    return json.dumps({
        "employee_email":   employee_email,
        "job_id":           job_id,
        "score":            score,
        "recommendation":   recommendation,
        "key_strengths":    key_strengths,
        "gaps_to_address":  missing,
        "rationale":        rationale,
    })


# ---------------------------------------------------------------------------
# Tool 3: Final explanation compiler
# ---------------------------------------------------------------------------

@tool
def compile_explanation(employee_email: str, job_id: str) -> str:
    """
    Compile a complete, human-readable hire recommendation for one assignment.

    Combines the work examples (Tool 1) and recommendation assessment (Tool 2)
    into a single, structured explanation entry that can be delivered to
    hiring managers.

    The explanation includes:
      - Recommendation level (strong_hire / hire / consider / pass)
      - Key strengths with concrete evidence from the employee's history
      - Knowledge-graph inferences with their BFS paths
      - Gaps to address and why they matter
      - A final one-paragraph summary suitable for an HR report

    Args:
        employee_email: The employee's email identifier.
        job_id:         The target job identifier.
    """
    emp        = _get_employee(employee_email)
    assignment = _get_assignment(employee_email, job_id)

    if emp is None:
        return json.dumps({"error": f"Employee {employee_email!r} not found"})
    if assignment is None:
        return json.dumps({"error": f"No assignment found for ({employee_email}, {job_id})"})

    score      = assignment.get("score", 0.0)
    matched    = assignment.get("matched_skills", [])
    inferred   = assignment.get("inferred_skills", [])
    missing    = assignment.get("missing_skills", [])
    job_title  = assignment.get("job_title", job_id)
    emp_name   = emp.get("name", employee_email)

    # Determine recommendation level (same logic as assess_hire_recommendation)
    n_missing = len(missing)
    if score >= 0.80 and n_missing <= 1:
        recommendation = "strong_hire"
    elif score >= 0.60:
        recommendation = "hire"
    elif score >= 0.40:
        recommendation = "consider"
    else:
        recommendation = "pass"

    # Build concrete experience statements
    skill_lookup: dict[str, dict | str] = {}
    for s in emp.get("skills", []):
        name = s if isinstance(s, str) else s.get("name", "")
        if name:
            skill_lookup[name.strip().lower()] = s

    kg = _build_kg()

    concrete_examples: list[str] = []
    for skill_key in matched:
        record = skill_lookup.get(skill_key)
        if record:
            concrete_examples.append(_skill_description(record))

    for skill_key in inferred:
        for seed in matched:
            path = _bfs_path(seed, skill_key, kg)
            if path:
                concrete_examples.append(
                    f"'{skill_key}' demonstrated via related experience: {' → '.join(path)}"
                )
                break

    # Compose summary paragraph
    coverage_pct = round(
        (len(matched) + len(inferred)) /
        max(len(matched) + len(inferred) + len(missing), 1) * 100
    )
    summary_parts: list[str] = [
        f"{emp_name} achieves a match score of {score:.2f} for the role of '{job_title}' "
        f"(recommendation: {recommendation.replace('_', ' ').upper()}).",
        f"They directly cover {len(matched)} required skill(s)"
        + (f" and have {len(inferred)} additional skill(s) inferred via knowledge-graph proximity" if inferred else "")
        + f", giving {coverage_pct}% total skill coverage.",
    ]
    if missing:
        summary_parts.append(
            f"Skill gap(s) to address before or during onboarding: {', '.join(missing)}."
        )
    if recommendation in ("strong_hire", "hire"):
        summary_parts.append(
            "Overall profile is well-aligned with the role requirements."
        )

    return json.dumps({
        "employee_email":   employee_email,
        "employee_name":    emp_name,
        "job_id":           job_id,
        "job_title":        job_title,
        "score":            score,
        "recommendation":   recommendation,
        "key_strengths":    sorted(set(matched + inferred)),
        "concrete_examples": concrete_examples,
        "gaps_to_address":  missing,
        "summary":          " ".join(summary_parts),
    })


# ---------------------------------------------------------------------------
# Tool 4 — Batched explanation compiler (old pipeline style)
# ---------------------------------------------------------------------------

_BATCH_PROMPT = """\
You are a senior technical recruiter writing hiring recommendations for an engineering team.

For EACH candidate below, write a compelling, human recommendation based ONLY on their \
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
- Write 5-7 sentences per candidate.
- End every recommendation with exactly: "VERDICT: [recommendation]" using the \
RECOMMENDED VERDICT provided.

CANDIDATES:
{candidates_block}

Return ONLY a valid JSON object with one key per candidate (use the KEY value shown):
{{
  "email::job_id": "full recommendation text here",
  ...
}}

Keys to include: {keys_list}
"""


def _build_candidate_block(
    assignment: dict,
    emp: dict,
    kg: dict[str, dict[str, float]],
    xai_assignment: dict | None = None,
) -> tuple[str, str] | None:
    """
    Build one candidate's context block. Returns (key, block_text) or None.

    xai_assignment : per-pair data from the Validation Agent's XAI report
                     (semantic_gaps, coverage_ratio, quality_score) — used to
                     add richer context about fixable vs structural gaps.
    """
    email     = assignment["employee_email"]
    job_id    = assignment["job_id"]
    job_title = assignment.get("job_title", job_id)

    matched  = [s.lower() for s in assignment.get("matched_skills", [])]
    inferred = [s.lower() for s in assignment.get("inferred_skills", [])]
    missing  = [s.lower() for s in assignment.get("missing_skills", [])]

    # Enrich from XAI report if available
    if xai_assignment:
        semantic_gaps    = xai_assignment.get("semantic_gaps", [])
        coverage_ratio   = xai_assignment.get("coverage_ratio", 0.0)
        quality_score    = xai_assignment.get("quality_score", 0.0)
    else:
        semantic_gaps  = []
        coverage_ratio = 0.0
        quality_score  = 0.0

    skill_lookup: dict[str, Any] = {}
    for s in emp.get("skills", []):
        name = s if isinstance(s, str) else s.get("name", "")
        if name:
            skill_lookup[name.strip().lower()] = s

    _level = {1: "basic", 2: "intermediate", 3: "expert"}

    direct_parts: list[str] = []
    for key in matched:
        rec = skill_lookup.get(key)
        if isinstance(rec, dict):
            yrs  = round(rec.get("duration_months", 0) / 12, 1)
            lvl  = _level.get(rec.get("complexity", 1), "basic")
            year = str(rec.get("last_used", ""))[:4]
            desc = f"'{key}': {yrs}y at {lvl} level"
            if year:
                desc += f", last used in {year}"
            direct_parts.append(desc)
        else:
            direct_parts.append(f"'{key}'")

    inferred_parts: list[str] = []
    for inf_skill in inferred:
        for seed in matched:
            # BFS to find path
            visited: set[str] = {seed}
            queue: deque[list[str]] = deque([[seed]])
            path_found: list[str] | None = None
            while queue and path_found is None:
                path = queue.popleft()
                if len(path) - 1 >= 2:
                    continue
                for nb in kg.get(path[-1], {}):
                    if nb == inf_skill:
                        path_found = path + [nb]
                        break
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(path + [nb])
            if path_found:
                inferred_parts.append(
                    f"'{inf_skill}' inferred via: {' → '.join(path_found)}"
                )
                break
        else:
            inferred_parts.append(f"'{inf_skill}' (KG-adjacent)")

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

    score     = assignment.get("score", 0.0)
    n_missing = len(missing)
    if score >= 0.80 and n_missing <= 1:
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
            f"  (Semantic proximity — reachable gaps: {', '.join(semantic_gaps)})\n"
            if semantic_gaps else ""
        )
        + f"\nPROJECT HISTORY:\n"
        f"{chr(10).join(project_lines) if project_lines else '(no project history)'}\n\n"
        f"XAI QUALITY CONTEXT: coverage={round(coverage_ratio * 100)}%  "
        f"quality_score={round(quality_score, 2)}\n\n"
        f"RECOMMENDED VERDICT: {verdict}\n"
        f"{sep}"
    )
    return key, block


@tool
def compile_all_explanations() -> str:
    """
    Generate rich hire recommendations for ALL assignments in one batched LLM call.

    Builds a structured context block for each assignment (direct skill evidence,
    KG inference paths, project history, recommended verdict), then fires a
    single LLM call with the old pipeline's narrative prompt format.

    Each recommendation is 5-7 sentences, mentions specific project experience,
    explains KG-inferred skills concretely, and ends with a VERDICT line.

    Returns JSON:
      {
        "explanations": [
          {
            "employee_email": str,
            "employee_name": str,
            "job_id": str,
            "job_title": str,
            "recommendation": str,   -- strong_hire | hire | consider | high_potential
            "summary": str,          -- the 5-7 sentence narrative
            "matched_skills": [...],
            "inferred_skills": [...],
            "missing_skills": [...]
          }
        ]
      }
    """
    import re
    from services.llm import ask_llm

    assignments = _ctx.get("assignments", [])
    employees   = _ctx.get("employees", [])
    kg          = _ctx.get("global_knowledge_graph", {})
    xai_report  = _ctx.get("xai_report", {})

    if not assignments:
        return json.dumps({"explanations": []})

    emp_map = {e["email"]: e for e in employees}

    # Build per-assignment XAI lookup: (email, job_id) → quality data
    xai_lookup: dict[tuple[str, str], dict] = {}
    for job_rep in xai_report.get("job_reports", []):
        jid = job_rep.get("job_id", "")
        for a_rep in job_rep.get("assignments", []):
            email_key = a_rep.get("employee_email", "")
            if email_key and jid:
                xai_lookup[(email_key, jid)] = a_rep

    blocks: list[str] = []
    keys:   list[str] = []
    valid_assignments: list[dict] = []

    for a in assignments:
        email = a["employee_email"]
        emp   = emp_map.get(email)
        if not emp:
            continue
        xai_a = xai_lookup.get((email, a["job_id"]))
        result = _build_candidate_block(a, emp, kg, xai_assignment=xai_a)
        if result:
            key, block = result
            keys.append(key)
            blocks.append(block)
            valid_assignments.append(a)

    if not blocks:
        return json.dumps({"explanations": []})

    candidates_block = "\n\n".join(blocks)
    keys_list        = json.dumps(keys)

    prompt = _BATCH_PROMPT.format(
        candidates_block=candidates_block,
        keys_list=keys_list,
    )

    try:
        raw = ask_llm(prompt)
    except Exception as exc:
        return json.dumps({"error": str(exc), "explanations": []})

    # Extract JSON from LLM response
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    explanations_map: dict[str, str] = {}
    s = cleaned.find("{")
    e = cleaned.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            explanations_map = json.loads(cleaned[s:e])
        except json.JSONDecodeError:
            pass

    _level_map = {
        "Strong Hire": "strong_hire",
        "Hire": "hire",
        "Consider": "consider",
        "High Potential": "high_potential",
    }

    results: list[dict] = []
    for a, key in zip(valid_assignments, keys):
        text = explanations_map.get(key, "")
        if not text:
            emp = emp_map.get(a["employee_email"], {})
            matched_str = ", ".join(a.get("matched_skills", [])[:3]) or "relevant skills"
            text = (
                f"{emp.get('name', a['employee_email'])} brings hands-on experience "
                f"with {matched_str} that aligns with the "
                f"{a.get('job_title', a['job_id'])} role. "
                f"VERDICT: Consider — Assess Core Skills"
            )

        verdict_line = ""
        if "VERDICT:" in text:
            verdict_line = text.split("VERDICT:")[-1].strip().split("\n")[0].strip()

        recommendation = next(
            (v for k, v in _level_map.items() if k in verdict_line), "consider"
        )

        results.append({
            "employee_email":  a["employee_email"],
            "employee_name":   a.get("employee_name", ""),
            "job_id":          a["job_id"],
            "job_title":       a.get("job_title", a["job_id"]),
            "recommendation":  recommendation,
            "summary":         text,
            "matched_skills":  a.get("matched_skills", []),
            "inferred_skills": a.get("inferred_skills", []),
            "missing_skills":  a.get("missing_skills", []),
        })

    return json.dumps({"explanations": results})
