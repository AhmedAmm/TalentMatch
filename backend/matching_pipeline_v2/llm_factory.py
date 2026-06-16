"""
matching_pipeline_v2/llm_factory.py
=====================================
Shared LLM factory for all ReAct agents — NVIDIA NIM endpoint.

ALL agents (sub-agents + orchestrator) use moonshotai/kimi-k2-instruct:
  - 128K context window (handles large skill matrices and multi-assignment prompts)
  - Supports multiple registered tools without "single tool-calls" error
  - Sequential tool calling via parallel_tool_calls=False (enforced below)
  - Superior instruction-following for complex multi-step pipelines

Why _SingleCallOpenAI subclass
-------------------------------
LangGraph's create_react_agent internally calls model.bind_tools(tools),
which builds a new bound model.  Setting parallel_tool_calls=False at the
ChatOpenAI constructor level is discarded at that point.

Overriding bind_tools() guarantees parallel_tool_calls=False is always
injected at bind time — making every tool call sequential regardless of
how many tools are registered.
"""
from __future__ import annotations

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import ChatOpenAI

import matching_pipeline_v2.config as cfg

_SHARED_RATE_LIMITER = InMemoryRateLimiter(
    requests_per_second   = 0.5,
    check_every_n_seconds = 0.1,
    max_bucket_size       = 3,
)


class _SingleCallOpenAI(ChatOpenAI):
    """ChatOpenAI that always forces parallel_tool_calls=False at bind_tools time."""

    def bind_tools(self, tools, **kwargs):
        kwargs["parallel_tool_calls"] = False
        return super().bind_tools(tools, **kwargs)


_NO_THINKING = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


def _make_llm(model: str) -> _SingleCallOpenAI:
    return _SingleCallOpenAI(
        model        = model,
        base_url     = cfg.NVIDIA_BASE_URL,
        api_key      = cfg.NVIDIA_API_KEY,
        temperature  = cfg.NVIDIA_TEMPERATURE,
        max_tokens   = cfg.NVIDIA_MAX_TOKENS,
        rate_limiter = _SHARED_RATE_LIMITER,
        max_retries  = 3,
        model_kwargs = _NO_THINKING,
    )


def build_llm() -> _SingleCallOpenAI:
    """All agents: Kimi K2 with sequential (non-parallel) tool calling."""
    return _make_llm(cfg.NVIDIA_AGENT_MODEL)


def build_validation_llm() -> _SingleCallOpenAI:
    """Validation agent: same model but with a higher token budget.

    The validation agent must output the full xai_report dict (9 assignments ×
    7 jobs ≈ 5–6 KB of JSON) in addition to its reasoning.  The default 4096
    token cap truncates that output mid-JSON, causing a parse error.
    """
    return _SingleCallOpenAI(
        model        = cfg.NVIDIA_AGENT_MODEL,
        base_url     = cfg.NVIDIA_BASE_URL,
        api_key      = cfg.NVIDIA_API_KEY,
        temperature  = cfg.NVIDIA_TEMPERATURE,
        max_tokens   = cfg.NVIDIA_VALIDATOR_MAX_TOKENS,
        rate_limiter = _SHARED_RATE_LIMITER,
        max_retries  = 3,
        model_kwargs = _NO_THINKING,
    )


def build_orchestrator_llm() -> _SingleCallOpenAI:
    """Orchestrator: same Kimi K2 model (unified for consistency)."""
    return _make_llm(cfg.NVIDIA_ORCHESTRATOR_MODEL)
