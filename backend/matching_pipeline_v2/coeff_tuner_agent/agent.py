"""
matching_pipeline_v2/coeff_tuner_agent/agent.py
=================================================
CoeffTuner Agent — LangGraph ReAct agent that adjusts skill coefficients
so the next scoring iteration focuses on under-covered gap skills.

Architecture (matches old pipeline llm_tune_weights + reapply_weights):
  1. get_gap_context()     → LLM reads collective gaps, job descriptions,
                             current weights, urgency signal (like old pipeline)
  2. LLM brain DECIDES the new weights — it reasons about which skills are
     critical for each job and how much to boost them
  3. apply_skill_weights() → physically applies + re-normalises the decisions

The LLM is the brain — it sees the same context as the old pipeline's
llm_tune_weights() LLM prompt and makes the weight decisions directly.
Tool calls are sequential (one at a time) via parallel_tool_calls=False.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from matching_pipeline_v2.llm_factory import build_llm
from langgraph.prebuilt import create_react_agent

import matching_pipeline_v2.config as cfg
from matching_pipeline_v2.coeff_tuner_agent import tools as _tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — LLM brain reads gaps and decides weights
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the Coefficient Tuner Agent — a technical recruiter AI that adjusts \
skill coefficients (weights) for each job so the NEXT scoring iteration penalises \
uncovered critical skills less and rewards employees closer to covering them.

═══ AVAILABLE TOOLS (call them SEQUENTIALLY — one per turn) ════════════════════
  1. get_gap_context      — shows collective gaps, current weights, job descriptions,
                            and an urgency signal (HIGH/MEDIUM/LOW). ALWAYS first.
  2. apply_skill_weights  — applies your weight map, re-normalises, returns final coeffs.

═══ STRICT WORKFLOW ════════════════════════════════════════════════════════════
Step 1: Call get_gap_context (no arguments).
        Study the returned JSON. For each job, focus on:
          - collective_gaps   : skills missing from EVERY assigned employee
                                → MUST be boosted (the job model under-weights them)
          - semantic_gaps     : gaps reachable via KG from existing skills
                                → boost moderately
          - current_weights   : existing coefficients (start at 1.0)
          - urgency           : HIGH → boost 0.4-0.8 above baseline
                                MEDIUM → boost 0.2-0.4 above baseline
                                LOW → boost 0.1-0.2 above baseline

Step 2: Construct your weight decision JSON. Format:
          {
            "job_id_1": {"skill_a": 1.6, "skill_b": 1.0, "skill_c": 1.4, ...},
            "job_id_2": {"skill_x": 1.2, "skill_y": 0.9, ...}
          }
        REQUIREMENTS:
          - Include EVERY required skill for each job (not just boosted ones).
          - Gap skills should be 1.5×–2.5× the non-gap baseline (≈1.0).
          - NEVER set a weight to 0; every required skill still matters.
          - DO NOT over-boost partial gaps that are not collective.

Step 3: Call apply_skill_weights with your JSON serialised as a string:
          apply_skill_weights(weight_decisions='{...JSON...}')
        The tool re-normalises your weights so the average stays at 1.0.

Step 4: Return the EXACT JSON returned by apply_skill_weights as your final answer.
        Do not add any text. The JSON MUST contain "weights" and "changes" keys.

═══ HARD RULES ═════════════════════════════════════════════════════════════════
- One tool call per turn. Never call two tools in the same response.
- Final answer = exact output of apply_skill_weights, nothing more, nothing less.
- No markdown fences, no commentary, no extra prose.
"""


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_llm():
    return build_llm()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent(context: dict) -> str:
    """
    Inject context, run the CoeffTuner ReAct agent, return its JSON output.

    Parameters
    ----------
    context : dict with keys jobs, weights, xai_report, adjustment_report

    Returns
    -------
    str — JSON with keys: weights, changes
    """
    _tools.set_context(context)

    agent = create_react_agent(
        model  = _build_llm(),
        tools  = [
            _tools.get_gap_context,
            _tools.apply_skill_weights,
        ],
        prompt = SystemMessage(content=SYSTEM_PROMPT),
    )

    n_jobs = len(context.get("jobs", []))
    # Build a summary of what's in the XAI report for the task message
    xai = context.get("xai_report", {})
    c_gaps = xai.get("collective_gaps", context.get("adjustment_report", {}).get("collective_gaps", {}))
    gap_summary = ", ".join(
        f"'{j}': {gaps}"
        for j, gaps in list(c_gaps.items())[:3]
    ) or "none identified"

    task = (
        f"Adjust skill coefficients for {n_jobs} job(s). "
        f"Collective gaps: {gap_summary}. "
        "Call get_gap_context first to read the full context, "
        "then decide new weights and call apply_skill_weights."
    )
    logger.info("[CoeffTunerAgent] %s", task)

    result   = agent.invoke({"messages": [HumanMessage(content=task)]})
    messages = result.get("messages", [])

    for msg in reversed(messages):
        text = getattr(msg, "content", "")
        text = text if isinstance(text, str) else str(text)
        if text.strip():
            try:
                json.loads(text)
                return text
            except json.JSONDecodeError:
                start = text.find("{")
                end   = text.rfind("}") + 1
                if start >= 0 and end > start:
                    candidate = text[start:end]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pass
            return text

    return '{"error": "CoeffTuner agent produced no output"}'
