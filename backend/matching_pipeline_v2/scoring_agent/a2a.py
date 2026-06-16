"""
matching_pipeline_v2/scoring_agent/a2a.py
==========================================
A2A server wrapper for the Scoring Agent.

Exposes the ReAct scoring agent over HTTP on SCORER_PORT (default 8101) so
the orchestrator can reach it via A2AClient.

Message contract
----------------
Input  JSON keys: employees, jobs, weights, global_knowledge_graph
Output JSON keys: score_matrix, details, summary   (or {"error": "..."})

Run standalone:
    python -m matching_pipeline_v2.scoring_agent.a2a
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import threading

from python_a2a import (
    A2AServer,
    AgentCard,
    AgentSkill,
    Message,
    MessageRole,
    TextContent,
    run_server,
)

import matching_pipeline_v2.config as cfg
from matching_pipeline_v2.scoring_agent.agent import run_agent
from matching_pipeline_v2.scoring_agent import tools as _tools

logger = logging.getLogger(__name__)


class ScoringAgentServer(A2AServer):
    """
    A2A server that wraps the Scoring ReAct agent.

    Receives an A2A message with the pipeline context, delegates to the
    LangGraph ReAct agent, and returns the score-matrix JSON.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        card = AgentCard(
            name        = "Scoring Agent",
            description = (
                "Builds the weighted skill-coverage score matrix (employees × jobs) "
                "using recency/duration/complexity scoring and BFS knowledge-graph expansion."
            ),
            url     = cfg.SCORER_URL,
            version = "2.0.0",
            skills  = [
                AgentSkill(
                    name        = "build_score_matrix",
                    description = (
                        "Compute dot-product skill-match scores for all employee-job pairs, "
                        "including KG-inferred skill coverage."
                    ),
                )
            ],
        )
        super().__init__(agent_card=card)

    def handle_message(self, message: Message) -> Message:
        """
        Deserialise input JSON → run ReAct agent → serialise output JSON.

        Input  JSON: { employees, jobs, weights, global_knowledge_graph }
        Output JSON: { score_matrix, details, summary }  |  { error }
        """
        # Serialise access: _ctx is module-level state shared between threads.
        # Without this lock a concurrent request's set_context() clears _ctx
        # between run_agent() writing score_matrix and handle_message reading it,
        # causing avg=0.000 on an empty matrix.
        with self._lock:
            try:
                context = json.loads(message.content.text)
                run_agent(context)
                # Full matrix + details are stored in _ctx by compute_score_matrix;
                # only the compact summary was returned to the LLM to avoid 413 errors.
                score_matrix = _tools._ctx.get("score_matrix", [])
                details      = _tools._ctx.get("score_details", [])
                summary      = {
                    "n_employees": len(context.get("employees", [])),
                    "n_jobs":      len(context.get("jobs", [])),
                    "avg_score":   round(
                        sum(s for row in score_matrix for s in row) / max(len(score_matrix) * len(score_matrix[0]), 1), 3
                    ) if score_matrix else 0.0,
                    "max_score": round(
                        max((s for row in score_matrix for s in row), default=0.0), 3
                    ),
                }
                result = {"score_matrix": score_matrix, "details": details, "summary": summary}
                logger.info(
                    "[ScoringAgent] Matrix %dx%d  avg=%.3f  max=%.3f",
                    summary["n_employees"], summary["n_jobs"],
                    summary["avg_score"],   summary["max_score"],
                )
            except Exception as exc:
                logger.error("[ScoringAgent] Error: %s", exc, exc_info=True)
                result = {"error": str(exc)}

        return Message(
            content = TextContent(text=json.dumps(result)),
            role    = MessageRole.AGENT,
        )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    print(f"Starting Scoring Agent on {cfg.SCORER_URL}/a2a")
    run_server(ScoringAgentServer(), host="0.0.0.0", port=cfg.SCORER_PORT)
