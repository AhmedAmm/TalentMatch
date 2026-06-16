"""
matching_pipeline_v2/validation_agent/a2a.py
=============================================
A2A server wrapper for the Validation Agent.

Exposes the ReAct validation agent over HTTP on VALIDATOR_PORT (default 8102).

Message contract
----------------
Input  JSON keys: assignments, jobs, global_knowledge_graph
Output JSON keys: decision, avg_score, reasoning, [adjustment_report]  |  {error}

Run standalone:
    python -m matching_pipeline_v2.validation_agent.a2a
"""
from __future__ import annotations

import json
import logging
import re
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
from matching_pipeline_v2.validation_agent.agent import run_agent

logger = logging.getLogger(__name__)


class ValidationAgentServer(A2AServer):
    """
    A2A server wrapping the Validation ReAct agent.

    Receives the current assignment context, delegates to the LangGraph
    ReAct agent, and returns the validation decision JSON.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        card = AgentCard(
            name        = "Validation Agent",
            description = (
                "Validates assignment quality using XAI analysis and knowledge-graph "
                "path tracing.  Returns FINALIZE or ADJUST with a structured gap report."
            ),
            url     = cfg.VALIDATOR_URL,
            version = "2.0.0",
            skills  = [
                AgentSkill(
                    name        = "validate_assignments",
                    description = (
                        "XAI-based quality assessment of the current employee-job "
                        "assignment; produces FINALIZE or ADJUST decision."
                    ),
                )
            ],
        )
        super().__init__(agent_card=card)

    def handle_message(self, message: Message) -> Message:
        """
        Deserialise input JSON → run ReAct agent → serialise output JSON.

        Input  JSON: { assignments, jobs, global_knowledge_graph }
        Output JSON: { decision, avg_score, reasoning, [adjustment_report] }
        """
        with self._lock:
            result_text = ""
            try:
                context     = json.loads(message.content.text)
                result_text = run_agent(context)
                if not result_text or not result_text.strip():
                    logger.warning("[ValidationAgent] Agent returned empty response — defaulting to finalize")
                    result = {"decision": "finalize", "avg_score": 0.0, "reasoning": "Agent returned no output"}
                else:
                    result = json.loads(result_text)
                logger.info(
                    "[ValidationAgent] decision=%s  avg_score=%.3f",
                    result.get("decision", "?"),
                    result.get("avg_score", 0.0),
                )
            except Exception as exc:
                logger.error("[ValidationAgent] Error: %s", exc, exc_info=True)
                # Try to salvage decision + avg_score from malformed LLM output
                from matching_pipeline_v2.validation_agent import tools as _val_tools
                xai = _val_tools._ctx.get("_last_xai_report", {})
                decision_m = re.search(r'"decision"\s*:\s*"(finalize|adjust)"', result_text or "", re.I)
                avg_m      = re.search(r'"avg_score"\s*:\s*([\d.]+)', result_text or "")
                if decision_m:
                    logger.warning("[ValidationAgent] Salvaged decision=%s from partial LLM output", decision_m.group(1))
                    result = {
                        "decision":  decision_m.group(1).lower(),
                        "avg_score": float(avg_m.group(1)) if avg_m else xai.get("avg_score", 0.0),
                        "reasoning": "Recovered from partial LLM output",
                        "xai_report": xai,
                    }
                else:
                    result = {"decision": "finalize", "avg_score": xai.get("avg_score", 0.0), "reasoning": str(exc), "xai_report": xai}

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
    print(f"Starting Validation Agent on {cfg.VALIDATOR_URL}/a2a")
    run_server(ValidationAgentServer(), host="0.0.0.0", port=cfg.VALIDATOR_PORT)
