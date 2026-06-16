"""
po_parser/project_parser.py
-----------------------------
Parse a PO project-report PDF into a structured dict.

Pipeline
--------
  1. Docling extracts text → Markdown (with structure preview printed to stdout)
  2. Text is split at paragraph boundaries if it exceeds _MAX_CHUNK_CHARS
  3. Each chunk is sent to the LLM with a strict extraction prompt
  4. Chunk results are merged deterministically (no second LLM call):
       - project metadata : first non-empty value wins
       - functional_needs : case-insensitive union
       - non_functional_needs : union deduped by category
       - technology_stack : merged by layer
       - jobs             : fuzzy dedup by title (word-overlap ≥ 0.5 treated as same job)
  5. list[str] normalisation for fields that Pydantic expects as plain strings

Duplicate-jobs fix
------------------
Chunked extraction sometimes extracts the same role from multiple document
sections with slightly different titles (e.g. "Tech Lead / Architecte IA" vs
"Tech Lead").  `_fuzzy_title_match` uses Jaccard word-overlap to detect near-
duplicate titles and keep only the most complete entry, eliminating the
16-job-instead-of-7 problem.

Uses
----
  services/pdf.py  → Docling text extraction (OCR disabled)
  services/llm.py  → NVIDIA NIM LLM call
"""
from __future__ import annotations

import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.pdf import extract_text_from_pdf
from services.llm import ask_llm, begin_interaction, finish_interaction


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# NVIDIA NIM (Kimi K2 / llama-3.1-8b-instruct) supports 128K context.
# The full PDF text (~14 K chars ≈ 3.5 K tokens) comfortably fits in a single
# call.  Chunking is kept as a safety fallback for unusually large documents
# (> _MAX_CHUNK_CHARS), but the target is always a single LLM call to avoid
# cross-chunk job duplication.
_MAX_CHUNK_CHARS: int = 40_000   # ~10 K tokens — rarely triggered

# Jaccard word-overlap threshold for treating two job titles as the same role.
# 0.5 means "at least half the words in the shorter title appear in the longer
# one" — catches "Tech Lead" vs "Tech Lead / Architecte IA".
_JOB_TITLE_SIMILARITY_THRESHOLD: float = 0.5


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are a structured data extraction assistant reading one SECTION of a PO project report.

Your job is to extract ONLY the information that is EXPLICITLY STATED in this section.
Do NOT invent, infer, or duplicate information.

CRITICAL JOB EXTRACTION RULES:
- List ONLY the job roles EXPLICITLY mentioned in this section.
- If a role is not clearly defined here, output [] for the jobs array.
- Each job title must be unique — do NOT repeat the same role twice.
- "Tech Lead" and "Tech Lead / Architecte IA" are the SAME role — list it once.

Return ONLY a valid JSON object with this exact structure. No markdown, no explanation:

{{
  "project": {{
    "name": "string or null",
    "client": "string or null",
    "description": "string or null"
  }},
  "functional_needs": ["string"],
  "non_functional_needs": [
    {{"category": "string", "description": "string"}}
  ],
  "technology_stack": [
    {{"layer": "string (Frontend/Backend/Database/DevOps/AI-ML)", "technologies": ["string"]}}
  ],
  "jobs": [
    {{
      "title": "string",
      "description": "string or null",
      "headcount": 1,
      "seniority": "junior | mid | senior | lead",
      "type": "full-time | part-time | contract",
      "estimated_duration_months": 0,
      "required_stack": [{{"skill": "string", "level": "beginner | intermediate | expert"}}],
      "responsibilities": ["string"]
    }}
  ]
}}

Rules:
- Use null for absent strings, 0 for absent integers, [] for absent arrays.
- headcount must be an integer >= 1.
- Do NOT invent data not present in this section.
- RETURN ONLY THE JSON OBJECT — nothing else.

--- SECTION START ---
{text}
--- SECTION END ---
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_project_pdf(pdf_path: str) -> dict:
    """
    Full pipeline: PDF → Markdown → (chunked) LLM extraction → structured dict.

    The Docling extraction is printed to stdout for operator verification before
    the LLM step runs.  Single-chunk documents make one LLM call; larger PDFs
    are chunked at paragraph boundaries and merged deterministically.

    Parameters
    ----------
    pdf_path : path to the PO project-report PDF.

    Returns
    -------
    dict with keys: project, functional_needs, non_functional_needs,
                    technology_stack, jobs.
    """
    import os as _os
    pdf_name = _os.path.basename(pdf_path)

    print(f"\n[Parser] Extracting text from: {pdf_path}")
    raw_text = extract_text_from_pdf(pdf_path, show_output=True)

    if not raw_text.strip():
        raise ValueError("PDF appears to be empty or unreadable.")

    print(f"[Parser] Extracted {len(raw_text):,} characters.")

    # ── Open Raindrop interaction ─────────────────────────────────────────────
    begin_interaction(
        event      = "project_pdf_extraction",
        input_text = pdf_name,
        pdf_chars  = len(raw_text),
    )

    chunks = _chunk_text(raw_text)

    if len(chunks) == 1:
        print("[Parser] Single chunk — one LLM call.")
        structured = _parse_llm_response(
            ask_llm(
                EXTRACTION_PROMPT.format(text=raw_text),
                _span_name="project_parser_chunk_1",
            )
        )
    else:
        print(f"[Parser] Split into {len(chunks)} chunk(s) — batched LLM extraction.")
        partials: list[dict] = []
        for i, chunk in enumerate(chunks, 1):
            print(f"[Parser]   Chunk {i}/{len(chunks)} ({len(chunk):,} chars) …")
            response = ask_llm(
                EXTRACTION_PROMPT.format(text=chunk),
                _span_name=f"project_parser_chunk_{i}",
            )
            partials.append(_parse_llm_response(response))
        print(f"[Parser] Merging {len(chunks)} partial results (deterministic, no LLM).")
        structured = _merge_partials(partials)

    # Normalise to list[str] so the Pydantic Job/Project models accept them
    structured["non_functional_needs"] = _flatten_non_functional(
        structured.get("non_functional_needs") or []
    )
    structured["technology_stack"] = _flatten_technology_stack(
        structured.get("technology_stack") or []
    )

    n_jobs = len(structured.get("jobs", []))
    print(f"[Parser] Extraction complete — {n_jobs} unique job(s) identified.")

    # ── Close Raindrop interaction ────────────────────────────────────────────
    finish_interaction(
        output    = f"{n_jobs} jobs extracted from {pdf_name}",
        n_jobs    = n_jobs,
        n_chunks  = len(chunks),
        pdf_chars = len(raw_text),
    )

    return structured


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """
    Split ``text`` at paragraph boundaries so each chunk stays ≤ max_chars.

    Paragraphs that exceed max_chars by themselves are kept as single chunks
    (the LLM tolerates slightly oversized inputs better than split sentences).
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len: int = 0

    for para in paragraphs:
        para_len = len(para) + 2          # +2 for the restored \n\n
        if current and current_len + para_len > max_chars:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _merge_partials(partials: list[dict]) -> dict:
    """
    Merge N partial extraction dicts into one coherent result.

    Deduplication strategy per field
    ---------------------------------
    project              : first non-empty value wins for each sub-field
    functional_needs     : case-insensitive union
    non_functional_needs : union keyed by category (first description wins)
    technology_stack     : merged by layer name; technologies deduped per layer
    jobs                 : fuzzy dedup by title (Jaccard ≥ 0.5 = same role);
                           keep the entry with the longer description
    """
    merged: dict = {
        "project":              {"name": "", "client": "", "description": ""},
        "functional_needs":     [],
        "non_functional_needs": [],
        "technology_stack":     [],
        "jobs":                 [],
    }

    seen_fn:    set[str]         = set()
    nf_by_cat:  dict[str, dict]  = {}
    layer_map:  dict[str, set[str]] = {}
    layer_order: list[str]       = []
    jobs_list:  list[dict]       = []   # fuzzy-deduped list (order preserved)

    for part in partials:
        # ── project metadata ────────────────────────────────────────────
        proj = part.get("project") or {}
        for field in ("name", "client", "description"):
            if not merged["project"][field] and proj.get(field):
                merged["project"][field] = proj[field]

        # ── functional_needs ────────────────────────────────────────────
        for fn in part.get("functional_needs") or []:
            if not isinstance(fn, str):
                continue
            key = fn.strip().lower()
            if key and key not in seen_fn:
                seen_fn.add(key)
                merged["functional_needs"].append(fn.strip())

        # ── non_functional_needs ─────────────────────────────────────────
        for nfn in part.get("non_functional_needs") or []:
            if not isinstance(nfn, dict):
                continue
            cat = (nfn.get("category") or "").strip()
            if not cat:
                continue
            if cat not in nf_by_cat:
                nf_by_cat[cat] = {"category": cat, "description": nfn.get("description") or ""}
            elif not nf_by_cat[cat]["description"] and nfn.get("description"):
                nf_by_cat[cat]["description"] = nfn["description"]

        # ── technology_stack ─────────────────────────────────────────────
        for ts in part.get("technology_stack") or []:
            if not isinstance(ts, dict):
                continue
            layer = (ts.get("layer") or "").strip()
            if not layer:
                continue
            if layer not in layer_map:
                layer_map[layer] = set()
                layer_order.append(layer)
            for tech in ts.get("technologies") or []:
                if isinstance(tech, str) and tech.strip():
                    layer_map[layer].add(tech.strip())

        # ── jobs (fuzzy dedup by title) ──────────────────────────────────
        for job in part.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            title = (job.get("title") or "").strip()
            if not title:
                continue
            _upsert_job(jobs_list, job, title)

    merged["non_functional_needs"] = list(nf_by_cat.values())
    merged["technology_stack"] = [
        {"layer": layer, "technologies": sorted(layer_map[layer])}
        for layer in layer_order
    ]
    merged["jobs"] = jobs_list
    return merged


def _upsert_job(jobs_list: list[dict], new_job: dict, new_title: str) -> None:
    """
    Insert ``new_job`` into ``jobs_list`` unless a fuzzy-matching entry exists.

    If a match is found, the entry with the longer description is kept.
    This prevents the same role (e.g. "Tech Lead" vs "Tech Lead / Architecte IA")
    from appearing multiple times after chunked extraction.
    """
    for i, existing in enumerate(jobs_list):
        existing_title = (existing.get("title") or "").strip()
        if _fuzzy_title_match(existing_title, new_title):
            # Keep the richer entry
            if len(str(new_job.get("description", ""))) > len(str(existing.get("description", ""))):
                jobs_list[i] = new_job
            return
    jobs_list.append(new_job)


def _fuzzy_title_match(title_a: str, title_b: str) -> bool:
    """
    Return True if two job titles refer to the same role.

    Uses Jaccard similarity on lowercased word sets, ignoring punctuation.
    Threshold: _JOB_TITLE_SIMILARITY_THRESHOLD (default 0.5).

    Examples
    --------
    "Tech Lead"  vs  "Tech Lead / Architecte IA"  →  True  (2/4 = 0.5)
    "Frontend Developer"  vs  "DevOps Engineer"   →  False (0/4 = 0.0)
    """
    def _words(t: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9\s]", " ", t.lower()).split())

    wa, wb = _words(title_a), _words(title_b)
    if not wa or not wb:
        return title_a.lower() == title_b.lower()

    intersection = len(wa & wb)
    union        = len(wa | wb)
    return (intersection / union) >= _JOB_TITLE_SIMILARITY_THRESHOLD


def _parse_llm_response(response: str) -> dict:
    """Strip markdown fences and parse the LLM's JSON response."""
    cleaned = re.sub(r"```(?:json)?", "", response).strip().strip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"[Parser] LLM returned invalid JSON.\n"
            f"Error: {exc}\n"
            f"Raw (first 500 chars):\n{response[:500]}"
        ) from exc


def _flatten_non_functional(items: list) -> list[str]:
    """Convert [{category, description}] → ['Category: description']."""
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            cat  = item.get("category", "")
            desc = item.get("description", "")
            result.append(f"{cat}: {desc}" if cat else desc)
        elif isinstance(item, str):
            result.append(item)
    return result


def _flatten_technology_stack(items: list) -> list[str]:
    """Convert [{layer, technologies[]}] → ['Layer/Tech', ...]."""
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            layer = item.get("layer", "")
            for tech in item.get("technologies", []):
                if isinstance(tech, str):
                    result.append(f"{layer}/{tech}" if layer else tech)
        elif isinstance(item, str):
            result.append(item)
    return result


def _generate_project_id(project_name: str) -> str:
    """
    Generate a slug-style project ID from the project name.

    Examples
    --------
    'E-Commerce Platform' → 'proj_ecommerce_platform'
    'SmartStaff'          → 'proj_smartstaff'
    """
    slug = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")
    return f"proj_{slug}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python project_parser.py <path_to_pdf>")
        sys.exit(1)

    result = parse_project_pdf(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
