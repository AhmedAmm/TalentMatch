"""
matching_pipeline_v2/coeff_tuner_agent/a2a.py
===============================================
A2A server wrapper for the CoeffTuner Agent.

Exposes the ReAct coefficient-tuning agent over HTTP on TUNER_PORT (default 8103).

Message contract
----------------
Input  JSON keys: jobs, weights, adjustment_report
Output JSON keys: weights, changes   |  { error }

Run standalone:
    python -m matching_pipeline_v2.coeff_tuner_agent.a2a
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
from matching_pipeline_v2.coeff_tuner_agent.agent import run_agent

logger = logging.getLogger(__name__)


class CoeffTunerAgentServer(A2AServer):
    """
    A2A server wrapping the CoeffTuner ReAct agent.

    Receives the adjustment report from the Validation Agent alongside
    the current jobs and weights, then returns updated weights for the
    next scoring iteration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        card = AgentCard(
            name        = "CoeffTuner Agent",
            description = (
                "Boosts skill coefficients for gap skills using gap-priority ranking "
                "and coverage-elasticity re-normalisation to guide the next iteration."
            ),
            url     = cfg.TUNER_URL,
            version = "2.0.0",
            skills  = [
                AgentSkill(
                    name        = "boost_gap_weights",
                    description = (
                        "Rank gap priorities and apply coverage-elasticity boosting "
                        "to job skill coefficients."
                    ),
                )
            ],
        )
        super().__init__(agent_card=card)

    def handle_message(self, message: Message) -> Message:
        """
        Deserialise input JSON → run ReAct agent → serialise output JSON.

        Input  JSON: { jobs, weights, adjustment_report }
        Output JSON: { weights, changes }
        """
        with self._lock:
            try:
                context     = json.loads(message.content.text)
                result_text = run_agent(context)
                result      = json.loads(result_text)
                logger.info(
                    "[CoeffTunerAgent] Updated weights for %d job(s)",
                    len(result.get("changes", {})),
                )
            except Exception as exc:
                logger.error("[CoeffTunerAgent] Error: %s", exc, exc_info=True)
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
    print(f"Starting CoeffTuner Agent on {cfg.TUNER_URL}/a2a")
    run_server(CoeffTunerAgentServer(), host="0.0.0.0", port=cfg.TUNER_PORT)
