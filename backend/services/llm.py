"""
services/llm.py
================
NVIDIA NIM client (PDF parser, CV parser, KG updater).

Used for raw text/JSON generation tasks (no tool calling) — chunked PDF
extraction in po_parser/, CV extraction in profile_update/, and KG updates
in scripts/update_kg.py.

Raindrop Workshop integration
------------------------------
This module initialises Raindrop Workshop once at import time.  Any pipeline
entry point can call begin_interaction() / finish_interaction() to open a
top-level span; every subsequent ask_llm() call inside that span will
automatically appear as a child tool span in the Workshop UI.

Set RAINDROP_LOCAL_DEBUGGER=http://localhost:5899 in .env to activate tracing.
Leave it unset (or set to empty) to run with zero overhead.

Environment variables
---------------------
NVIDIA_API_KEY        : NVIDIA NIM API key
NVIDIA_PARSER_MODEL   : model name (default qwen/qwen2.5-7b-instruct)
RAINDROP_LOCAL_DEBUGGER : Workshop URL (activates tracing when set)
RAINDROP_WRITE_KEY    : optional cloud key (local-only when empty)
"""
from __future__ import annotations

import json
import os
import time
import uuid

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL   = os.getenv("NVIDIA_PARSER_MODEL", "qwen/qwen2.5-7b-instruct")

_client = OpenAI(
    base_url = "https://integrate.api.nvidia.com/v1",
    api_key  = NVIDIA_API_KEY,
)


# ── Raindrop Workshop ─────────────────────────────────────────────────────────
# Graceful degradation: if raindrop-ai is not installed the whole module still
# works — every raindrop call becomes a no-op.

try:
    import raindrop.analytics as _rd

    _RD_ENABLED: bool = bool(os.getenv("RAINDROP_LOCAL_DEBUGGER", "").strip())
    # tracing_enabled=True is required for manual begin()/track_tool() to emit.
    # RAINDROP_LOCAL_DEBUGGER env var is picked up automatically by the SDK
    # to route spans to the local Workshop daemon at localhost:5899.
    # The "requires api_key for OTEL export" warning only affects auto-
    # instrumentation, not our manual tracing.
    _rd.init(
        api_key               = os.getenv("RAINDROP_WRITE_KEY") or None,
        tracing_enabled       = True,
        bypass_otel_for_tools = True,
        auto_instrument       = False,
    )
    if _RD_ENABLED:
        print(
            "[Raindrop] Workshop tracing ENABLED -> "
            + os.getenv("RAINDROP_LOCAL_DEBUGGER", "")
            + "  (project: smartstaff)"
        )
except ImportError:
    _rd         = None  # type: ignore[assignment]
    _RD_ENABLED = False


# Module-level active interaction — set by pipeline entry points.
# One interaction covers one full pipeline run (parsing job, CV, KG update…).
_active_interaction = None


def set_active_interaction(interaction) -> None:
    """Register the current pipeline interaction so ask_llm() can track spans."""
    global _active_interaction
    _active_interaction = interaction


def clear_active_interaction() -> None:
    global _active_interaction
    _active_interaction = None


def begin_interaction(event: str, input_text: str, **props):
    """
    Open a new top-level Raindrop interaction and register it as active.

    Parameters
    ----------
    event      : logical pipeline name shown in Workshop UI
                 e.g. "project_pdf_extraction", "cv_extraction", "kg_update",
                      "matching_pipeline"
    input_text : short human-readable description of the input
    **props    : extra key/value metadata attached to the span

    Returns
    -------
    The interaction object, or None when tracing is disabled.
    """
    if not _RD_ENABLED or _rd is None:
        return None

    run_id = str(uuid.uuid4())
    ix = _rd.begin(
        user_id  = "smartstaff",
        event    = event,
        event_id = run_id,
        convo_id = run_id,
        input    = input_text[:500],
    )
    if props:
        try:
            ix.set_properties(props)
        except Exception:
            pass
    set_active_interaction(ix)
    return ix


def finish_interaction(output: str, **props) -> None:
    """
    Finish and flush the currently active interaction.

    Safe to call even when tracing is disabled (no-op).
    """
    ix = _active_interaction
    if ix is None:
        return
    try:
        if props:
            ix.set_properties(props)
        ix.finish(output=output[:500])
        if _rd is not None:
            _rd.flush()
    except Exception:
        pass
    finally:
        clear_active_interaction()


# ── Core LLM call ─────────────────────────────────────────────────────────────

def ask_llm(
    prompt: str,
    json_mode: bool = True,
    _span_name: str = "ask_llm",
) -> str:
    """
    Send a prompt to the NVIDIA-hosted model and return the response text.

    json_mode=True  — extracts and returns the first valid JSON object/array
                      found in the response.  Raises ValueError if none found.
    json_mode=False — returns the raw answer text as-is.

    _span_name      — tool span label shown in Raindrop Workshop UI.
                      Callers set this to something descriptive, e.g.
                      "project_parser_chunk", "cv_parser", "kg_extractor".
    """
    t0 = time.perf_counter()

    completion = _client.chat.completions.create(
        model       = NVIDIA_MODEL,
        messages    = [{"role": "user", "content": prompt}],
        temperature = 0.2,
        top_p       = 0.7,
        max_tokens  = 8_192,
        stream      = True,
    )

    parts: list[str] = []
    for chunk in completion:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta.content
        if delta is not None:
            parts.append(delta)

    duration_ms = (time.perf_counter() - t0) * 1000
    print(f"[LLM] NVIDIA response time: {duration_ms / 1000:.2f}s  model={NVIDIA_MODEL}")
    answer = "".join(parts)

    # ── Raindrop tool span ────────────────────────────────────────────────────
    if _active_interaction is not None and _RD_ENABLED:
        try:
            _active_interaction.track_tool(
                name        = _span_name,
                input       = {
                    "prompt_chars": len(prompt),
                    "json_mode":    json_mode,
                    "model":        NVIDIA_MODEL,
                },
                output      = {
                    "response_chars": len(answer),
                    "ok":             True,
                },
                duration_ms = duration_ms,
            )
        except Exception:
            pass  # never let observability break the main path

    if not json_mode:
        return answer

    # ── JSON extraction ───────────────────────────────────────────────────────
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = answer.find(start_char)
        if start == -1:
            continue
        end = answer.rfind(end_char) + 1
        if end <= start:
            continue
        candidate = answer[start:end]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pos = end - 1
            while pos > start:
                pos = candidate.rfind(end_char, 0, pos)
                if pos == -1:
                    break
                try:
                    json.loads(candidate[: pos + 1])
                    return candidate[: pos + 1]
                except json.JSONDecodeError:
                    continue

    raise ValueError(
        f"[LLM] json_mode=True but no valid JSON found in response.\n"
        f"Raw answer:\n{answer[:500]}"
    )
