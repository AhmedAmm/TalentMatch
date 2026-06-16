"""
matching_pipeline_v2/validation_agent/agent.py
================================================
Validation Agent — LangGraph ReAct agent that reads the XAI report and
decides FINALIZE or ADJUST.

Architecture (mirrors old pipeline llm_validator + xai_analyzer):
  1. XAI tool (analyze_assignment_quality) prepares the detailed report:
       - Per-job assignment breakdowns (coverage, matched/missing/semantic gaps)
       - Collective gaps (skills missing for ALL employees in a job)
       - Bottleneck employees, avg/min scores, n_poor_fits
  2. LLM brain (Kimi K2) reads the XAI report and reasons about:
       - Are the core required skills covered across jobs?
       - Are collective gaps fixable by reweighting (ADJUST) or normal hiring gaps?
       - Is the overall quality acceptable or does another iteration help?
  3. If ADJUST: LLM calls structure_adjustment_report to get the gap priorities
     and recommended alpha for the CoeffTuner.

The LLM is the brain — it makes the judgment call, not the XAI tool.
Tool calls are sequential (one at a time) via parallel_tool_calls=False.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from matching_pipeline_v2.llm_factory import build_validation_llm
from langgraph.prebuilt import create_react_agent

import matching_pipeline_v2.config as cfg
from matching_pipeline_v2.validation_agent import tools as _tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — LLM brain reads XAI report and decides
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the Validation Agent — a senior technical recruiter AI deciding whether \
the current employee-to-job assignments are good enough to FINALIZE or whether \
the skill weightings should be ADJUSTED for another iteration.

═══ AVAILABLE TOOLS (call them SEQUENTIALLY — one per turn) ════════════════════
  1. analyze_assignment_quality   — generates the full XAI report (ALWAYS first)
  2. trace_skill_inference_path   — (debug) trace how a specific skill was inferred
  3. structure_adjustment_report  — builds the gap-priority plan for CoeffTuner
                                    (CALL ONLY IF you decide ADJUST)

═══ STRICT WORKFLOW ════════════════════════════════════════════════════════════
Step 1: Call analyze_assignment_quality (no arguments).
        Study the returned XAI report. Key fields to read:
          - avg_score, min_score, n_poor_fits
          - job_reports[]: per-job quality, collective_gaps, per-employee assignments
          - bottlenecks: employees scoring far below average

Step 2: Decide FINALIZE or ADJUST using these principles (USE JUDGMENT):
        → FINALIZE when:
            • Core required skills are well covered for most assignments
            • Collective gaps are secondary skills, not showstoppers
            • Reweighting would not meaningfully improve matching
            • When in doubt, prefer FINALIZE.
        → ADJUST when:
            • Core skills are poorly covered across MOST assignments
            • Collective gaps include critical skills under-weighted
            • You believe reweighting would genuinely fix the problem

Step 3a (FINALIZE): Return the JSON below as your FINAL answer (no extra text):
        {
          "decision": "finalize",
          "avg_score": <float, copy from XAI report>,
          "reasoning": "<4-6 specific sentences naming concrete jobs/skills>",
          "xai_report": <the FULL dict you got back from analyze_assignment_quality>
        }

Step 3b (ADJUST): First call structure_adjustment_report with the XAI report
        JSON string as its single argument. Then return:
        {
          "decision": "adjust",
          "avg_score": <float>,
          "reasoning": "<4-6 specific sentences: which jobs/skills need boosting and why>",
          "xai_report": <the FULL dict from analyze_assignment_quality>,
          "adjustment_report": <the FULL dict from structure_adjustment_report>
        }

═══ HARD RULES ═════════════════════════════════════════════════════════════════
- One tool call per turn. Never call two tools in the same response.
- The "reasoning" MUST name specific jobs and skills. No generic filler.
- NEVER call structure_adjustment_report when decision = finalize.
- ALWAYS include the full xai_report dict in the final answer.
- Output ONLY the JSON object — no markdown, no commentary, no code fences.
"""


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_llm():
    return build_validation_llm()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent(context: dict) -> str:
    """
    Inject context, run the Validation ReAct agent, return its JSON output.

    Parameters
    ----------
    context : dict with keys assignments, jobs, global_knowledge_graph

    Returns
    -------
    str — JSON: { decision, avg_score, reasoning, xai_report, [adjustment_report] }
    """
    _tools.set_context(context)

    agent = create_react_agent(
        model  = _build_llm(),
        tools  = [
            _tools.analyze_assignment_quality,
            _tools.trace_skill_inference_path,
            _tools.structure_adjustment_report,
        ],
        prompt = SystemMessage(content=SYSTEM_PROMPT),
    )

    n_assignments = len(context.get("assignments", []))
    n_jobs        = len(context.get("jobs", []))
    task = (
        f"You have {n_assignments} assignment(s) across {n_jobs} job(s). "
        "Call analyze_assignment_quality first to get the XAI report. "
        "Read it carefully, then make your FINALIZE or ADJUST decision. "
        "Call tools one at a time."
    )
    logger.info("[ValidationAgent] %s", task)

    result   = agent.invoke({"messages": [HumanMessage(content=task)]})
    messages = result.get("messages", [])

    parsed: dict | None = None
    for msg in reversed(messages):
        text = getattr(msg, "content", "")
        text = text if isinstance(text, str) else str(text)
        if not text.strip():
            continue
        # Try direct parse
        try:
            parsed = json.loads(text)
            break
        except json.JSONDecodeError:
            pass
        # Try to extract {...} substring
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end])
                break
            except json.JSONDecodeError:
                pass
        # Non-JSON last message — keep looking
        continue

    if parsed is None:
        parsed = {"decision": "finalize", "avg_score": 0.0, "reasoning": "No output from validation agent"}

    # Safety net: if the LLM omitted xai_report, inject it from the stored tool result
    if "xai_report" not in parsed:
        parsed["xai_report"] = _tools._ctx.get("_last_xai_report", {})

    return json.dumps(parsed)
