"""
orchestrator.py - Parses a CV PDF with an LLM and inserts the engineer profile into MongoDB.

Usage:
    python orchestrator.py <path_to_cv.pdf> <engineer_email>
"""

import sys
import json
import os
from dotenv import load_dotenv

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.pdf import extract_text_from_pdf
from services.llm import ask_llm, begin_interaction, finish_interaction
from db.operations import add_employee

load_dotenv()


EXTRACTION_PROMPT = """
You are a CV parser. Extract structured information from the CV text below and return ONLY a valid JSON object — no markdown, no explanation.

CV TEXT:
{cv_text}

Return this exact JSON structure (fill in all fields, use null if unknown, use [] for empty lists):
{{
  "name": "string",
  "current_role": "string",
  "education": [
    {{
      "degree": "string",
      "field": "string",
      "school": "string",
      "year": 2024
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string",
      "date": "YYYY"
    }}
  ],
  "skills": ["skill1", "skill2"],
  "projects": [
    {{
      "project_id": "PROJ-001",
      "client": "string",
      "role": "string",
      "start_date": "YYYY-MM",
      "end_date": null,
      "technologies": ["tech1", "tech2"],
      "tasks": []
    }}
  ]
}}
"""


def parse_cv(pdf_path: str) -> dict:
    """Extract text from PDF, send to LLM, return parsed profile dict."""

    pdf_name = os.path.basename(pdf_path)
    print(f"[*] Extracting text from: {pdf_path}")
    cv_text = extract_text_from_pdf(pdf_path)

    # ── Open Raindrop interaction ─────────────────────────────────────────────
    begin_interaction(
        event      = "cv_extraction",
        input_text = pdf_name,
        cv_chars   = len(cv_text),
    )

    print("[*] Sending to LLM for extraction...")
    prompt = EXTRACTION_PROMPT.format(cv_text=cv_text)
    raw_response = ask_llm(prompt, _span_name="cv_parser")

    # Strip markdown fences if LLM wraps in ```json ... ```
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        profile = json.loads(cleaned)
    except json.JSONDecodeError as e:
        finish_interaction(output=f"JSON parse error: {e}")
        print(f"[!] Failed to parse LLM response as JSON: {e}")
        print("Raw response:\n", raw_response)
        sys.exit(1)

    n_skills   = len(profile.get("skills", []))
    n_projects = len(profile.get("projects", []))
    finish_interaction(
        output     = f"{pdf_name} → {n_skills} skills, {n_projects} projects",
        n_skills   = n_skills,
        n_projects = n_projects,
    )

    return profile


def run(pdf_path: str, email: str):
    if not os.path.exists(pdf_path):
        print(f"[!] File not found: {pdf_path}")
        sys.exit(1)


    profile = parse_cv(pdf_path)

    print(f"[*] Inserting employee '{email}' into MongoDB...")
    add_employee(
        email=email,
        name=profile.get("name", "Unknown"),
        current_role=profile.get("current_role", "Unknown"),
        education=profile.get("education", []),
        certifications=profile.get("certifications", []),
        skills=profile.get("skills", []),
        projects=profile.get("projects", []),
        cv_filename=os.path.basename(pdf_path),
    )

    print(f"\n✅ Done! Employee '{email}' successfully added.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python orchestrator.py <path_to_cv.pdf> <engineer_email>")
        sys.exit(1)
    print(f"[*] Starting CV parsing for '{sys.argv[1]}' with email '{sys.argv[2]}'")
    run(pdf_path=sys.argv[1], email=sys.argv[2])