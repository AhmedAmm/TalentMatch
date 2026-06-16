"""Explanation Agent package — evidence-backed hire recommendations."""
from matching_pipeline_v2.explanation_agent.a2a import ExplanationAgentServer
from matching_pipeline_v2.config import EXPLANATION_PORT

__all__ = ["ExplanationAgentServer", "EXPLANATION_PORT"]
