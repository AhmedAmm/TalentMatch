"""
matching_pipeline_v2/explanation_agent/a2a.py
===============================================
A2A server wrapper for the Explanation Agent.

Exposes the ReAct explanation agent over HTTP on EXPLANATION_PORT (default 8104).

Message contract
----------------
Input  JSON keys: assignments, employees, global_knowledge_graph
Output JSON keys: explanations (list)   |  { error }

Run standalone:
    python -m matching_pipeline_v2.explanation_agent.a2a
"""
from __future__ import annotations

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
from matching_pipeline_v2.explanation_agent.agent import run_agent

logger = logging.getLogger(__name__)


class ExplanationAgentServer(A2AServer):
    """
    A2A server wrapping the Explanation ReAct agent.

    Receives the final assignments plus employee profiles, then returns a
    list of structured hire recommendations with concrete evidence.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        card = AgentCard(
            name        = "Explanation Agent",
            description = (
                "Generates concrete, evidence-backed hire recommendations for each "
                "assignment using skill history, KG inference paths, and coverage analysis."
            ),
            url     = cfg.EXPLANATION_URL,
            version = "2.0.0",
            skills  = [
                AgentSkill(
                    name        = "explain_assignments",
                    description = (
                        "For each assignment produce a strong-hire / hire / consider / pass "
                        "recommendation backed by the employee's concrete experience."
                    ),
                )
            ],
        )
        super().__init__(agent_card=card)

    def handle_message(self, message: Message) -> Message:
        """
        Deserialise input JSON → run ReAct agent → serialise output JSON.

        Input  JSON: { assignments, employees, global_knowledge_graph }
        Output JSON: { explanations: [ ... ] }
        """
        with self._lock:
            try:
                context     = json.loads(message.content.text)
                result_text = run_agent(context)
                raw         = json.loads(result_text)

                # Normalise: agent may return a list or a dict with an "explanations" key
                if isinstance(raw, list):
                    result = {"explanations": raw}
                elif isinstance(raw, dict) and "explanations" in raw:
                    result = raw
                else:
                    result = {"explanations": [raw] if raw else []}

                logger.info(
                    "[ExplanationAgent] Generated %d explanation(s)",
                    len(result["explanations"]),
                )
            except Exception as exc:
                logger.error("[ExplanationAgent] Error: %s", exc, exc_info=True)
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
    print(f"Starting Explanation Agent on {cfg.EXPLANATION_URL}/a2a")
    run_server(ExplanationAgentServer(), host="0.0.0.0", port=cfg.EXPLANATION_PORT)
