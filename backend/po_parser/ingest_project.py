"""
po_parser/ingest_project.py
-----------------------------
Full pipeline: PO project report PDF → MongoDB (projects + jobs collections).

Usage (CLI):
    python ingest_project.py <path_to_pdf> [po_id]

Usage (import — from async context):
    from po_parser.ingest_project import ingest_project_pdf
    summary = await ingest_project_pdf(pdf_path, po_id="po@company.com")

Steps:
    1. Extract raw text from PDF       (services/pdf.py via project_parser.py)
    2. LLM extracts structured data    (project_parser.py → services/llm.py)
    3. Upsert project document         (db.operations → projects collection)
    4. Upsert each job document        (db.operations → jobs collection)
    5. Link job_ids back to project    (db.operations → add_job_to_project)
"""

import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from project_parser import parse_project_pdf, _generate_project_id
from db.operations  import upsert_project, upsert_job, add_job_to_project


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_job_id(project_id: str, job_title: str, index: int) -> str:
    """
    Build a slug-style job ID.
    e.g. proj_ecommerce + 'Senior Backend Engineer' + 0
         → 'proj_ecommerce_senior_backend_engineer_0'
    """
    slug = re.sub(r"[^a-z0-9]+", "_", job_title.lower()).strip("_")
    return f"{project_id}_{slug}_{index}"


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline  (async — all DB calls use Beanie ORM)
# ─────────────────────────────────────────────────────────────────────────────

async def ingest_project_pdf(
    pdf_path: str,
    po_id: str = None,
    parsed_data: dict = None,
) -> dict:
    """
    Parse a PO project-report PDF and persist the project + jobs to MongoDB.

    Parameters
    ----------
    pdf_path    : path to the PO project report PDF (only read if parsed_data is None)
    po_id       : email (_id) of the PO user submitting this project.
    parsed_data : pre-parsed dict from parse_project_pdf().  When supplied the
                  Docling + LLM step is skipped entirely — the data is reused
                  directly, avoiding duplicate heavy processing.

    Returns
    -------
    dict with keys: project_id, po_id, job_ids, jobs_count, name, client
    """

    if po_id:
        print(f"[Ingest] Submitted by PO: {po_id}")
    else:
        print("[Ingest] WARNING — no po_id provided. Project saved without a PO owner.")

    # ── Step 1 & 2: Parse PDF → structured data (skipped if already parsed) ──
    if parsed_data is not None:
        print("\n[Ingest] Step 1/3 — Using pre-parsed PDF data (cache hit, skipping Docling + LLM).")
        data = parsed_data
    else:
        print("\n[Ingest] Step 1/3 — Parsing PDF...")
        data = parse_project_pdf(pdf_path)

    project_info     = data.get("project", {})
    functional_needs = data.get("functional_needs", [])
    non_functional   = data.get("non_functional_needs", [])
    technology_stack = data.get("technology_stack", [])
    jobs_data        = data.get("jobs", [])

    project_name = project_info.get("name") or "Unknown Project"
    project_id   = _generate_project_id(project_name)

    # ── Step 3: Upsert project ────────────────────────────────────────────────
    print(f"\n[Ingest] Step 2/3 — Upserting project '{project_id}'...")
    await upsert_project(
        project_id           = project_id,
        name                 = project_name,
        client_name          = project_info.get("client") or "",
        description          = project_info.get("description") or "",
        functional_needs     = functional_needs,
        non_functional_needs = non_functional,
        technology_stack     = technology_stack,
        job_ids              = [],        # populated in step 4
        po_id                = po_id,
        source_pdf           = pdf_path,
        embedding            = [],
    )

    # ── Step 4: Upsert each job + link back to project ────────────────────────
    print(f"\n[Ingest] Step 3/3 — Upserting {len(jobs_data)} job(s)...")
    job_ids: list[str] = []

    for index, job in enumerate(jobs_data):
        title  = job.get("title") or f"Job {index}"
        job_id = _generate_job_id(project_id, title, index)

        headcount = job.get("headcount")
        if not isinstance(headcount, int) or headcount < 1:
            headcount = 1

        duration = job.get("estimated_duration_months")
        if not isinstance(duration, int):
            duration = 0

        await upsert_job(
            job_id                    = job_id,
            project_id                = project_id,
            title                     = title,
            description               = job.get("description") or "",
            headcount                 = headcount,
            required_stack            = [s for s in (job.get("required_stack") or []) if s is not None],
            responsibilities          = [r for r in (job.get("responsibilities") or []) if isinstance(r, str)],
            seniority                 = job.get("seniority") or "mid",
            job_type                  = job.get("type") or "full-time",
            estimated_duration_months = duration,
            embedding                 = [],
        )

        await add_job_to_project(project_id, job_id)
        job_ids.append(job_id)
        print(f"       [{index + 1}/{len(jobs_data)}] '{title}' → {job_id}")

    summary = {
        "project_id": project_id,
        "po_id":      po_id,
        "job_ids":    job_ids,
        "jobs_count": len(job_ids),
        "name":       project_name,
        "client":     project_info.get("client") or "",
    }

    print(f"\n[Ingest] Done. Project '{project_id}' with {len(job_ids)} job(s) saved to MongoDB.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python ingest_project.py <path_to_pdf> [po_id]")
        sys.exit(1)

    async def _cli() -> None:
        # Initialise Beanie so the async DB calls work from the CLI
        from motor.motor_asyncio import AsyncIOMotorClient
        import beanie
        from db.models import Employee, Job, Project, Assignment, User, CVUploadLog
        from dotenv import load_dotenv
        load_dotenv()

        client = AsyncIOMotorClient(os.environ["MONGODB_URL"])
        await beanie.init_beanie(
            database        = client[os.getenv("DB_NAME", "Profile")],
            document_models = [Employee, Job, Project, Assignment, User, CVUploadLog],
        )

        summary = await ingest_project_pdf(
            pdf_path = sys.argv[1],
            po_id    = sys.argv[2] if len(sys.argv) == 3 else None,
        )
        client.close()

    asyncio.run(_cli())
