"""
services/
==========
External service adapters.

Sub-modules
-----------
llm  — Groq LLM client  (ask_llm)
pdf  — PDF text extraction           (extract_text_from_pdf)
"""
from services.llm import ask_llm
from services.pdf import extract_text_from_pdf

__all__ = ["ask_llm", "extract_text_from_pdf"]
