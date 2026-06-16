"""Validation Agent package — XAI-based assignment quality assessment."""
from matching_pipeline_v2.validation_agent.a2a import ValidationAgentServer
from matching_pipeline_v2.config import VALIDATOR_PORT

__all__ = ["ValidationAgentServer", "VALIDATOR_PORT"]
