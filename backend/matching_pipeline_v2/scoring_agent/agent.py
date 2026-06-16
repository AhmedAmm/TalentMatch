"""
matching_pipeline_v2/scoring_agent/agent.py
=============================================
ReAct agent declaration for the Scoring Agent.

The agent receives a request context (employees, jobs, weights, KG) and
uses its four tools to build the skill-match score matrix.

Brain LLM: openai/gpt-oss-20b via Groq (ChatGroq).
Framework: LangGraph create_react_agent (direct usage, no fallbacks).
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from matching_pipeline_v2.llm_factory import build_llm
from langgraph.prebuilt import create_react_agent

import matching_pipeline_v2.config as cfg
from matching_pipeline_v2.scoring_agent import tools as _tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the Scoring Agent in a multi-agent job-matching pipeline.
Your one job: build the full skill-match score matrix for all (employee, job) pairs.

═══ AVAILABLE TOOLS (call them SEQUENTIALLY — never two at once) ═══════════════
  1. compute_score_matrix         — builds the full (n_employees × n_jobs) matrix
                                    using BFS over the knowledge graph and the
                                    dot-product adequacy formula. ALWAYS call this.
  2. score_employee_skills        — (debug) inspect a single employee's raw
                                    recency/duration/complexity component scores
  3. expand_employee_knowledge_graph — (debug) show a single employee's BFS skill
                                    vector
  4. expand_job_requirements      — (debug) show one job's expanded requirement vector

═══ WORKFLOW (strict, deterministic) ═══════════════════════════════════════════
Step 1: Call compute_score_matrix (no arguments).
        It returns: { "status": "ok", "summary": { n_employees, n_jobs, avg_score, max_score } }
        The full matrix and per-pair details are stored server-side automatically.

Step 2: Return the EXACT JSON string from compute_score_matrix as your final answer.
        Do NOT add prose, do NOT call any other tool, do NOT modify the JSON.

═══ RULES ══════════════════════════════════════════════════════════════════════
- Sequential tool calls only. One call per turn.
- Tools 2-4 are for debugging — DO NOT call them during normal scoring.
- The final answer MUST be the raw JSON output of compute_score_matrix.
- If compute_score_matrix returns an error, return that error JSON as-is.
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
    Inject request context, invoke the ReAct agent, return its text output.

    Parameters
    ----------
    context : dict with keys employees, jobs, weights, global_knowledge_graph

    Returns
    -------
    str — JSON produced by compute_score_matrix (or an error string).
    """
    _tools.set_context(context)

    agent = create_react_agent(
        model  = _build_llm(),
        tools  = [
            _tools.score_employee_skills,
            _tools.expand_employee_knowledge_graph,
            _tools.expand_job_requirements,
            _tools.compute_score_matrix,
        ],
        prompt = SystemMessage(content=SYSTEM_PROMPT),
    )

    n_emp  = len(context.get("employees", []))
    n_jobs = len(context.get("jobs", []))
    task   = f"Build the score matrix for {n_emp} employees and {n_jobs} jobs."
    logger.info("[ScoringAgent] %s", task)

    result   = agent.invoke({"messages": [HumanMessage(content=task)]})
    messages = result.get("messages", [])

    for msg in reversed(messages):
        text = getattr(msg, "content", "")
        text = text if isinstance(text, str) else str(text)
        if text.strip():
            return text

    return '{"error": "Scoring agent produced no output"}'
