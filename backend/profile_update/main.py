"""
main.py
-------
FastAPI server exposing two endpoints:
  POST /sync  → runs jira_sync.sync()
  POST /run   → runs orchestrator.run()
"""

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse

from jira_sync import sync
from orchestrator import run

app = FastAPI(title="Jira Sync & CV Orchestrator", version="1.0.0")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok"}


# ── Endpoint 1: Jira Sync ─────────────────────────────────────────────────────

@app.post("/sync")
def sync_jira(
    date: str | None = Query(
        default=None,
        description="Optional start date filter (YYYY-MM-DD). Fetches all Done tickets if omitted.",
        example="2024-01-01",
    )
):
    """
    Fetches all DONE Jira tickets across every project and saves them to MongoDB.
    Optionally filter by tickets updated on or after `date`.
    """
    try:
        sync(date=date)
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Jira sync completed.", "date_filter": date},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# ── Endpoint 2: CV Orchestrator ───────────────────────────────────────────────

@app.post("/run")
async def run_orchestrator(
    email: str = Form(..., description="Engineer's email address", example="john@company.com"),
    cv:    UploadFile = File(..., description="CV file in PDF format"),
):
    """
    Parses a CV PDF with an LLM and inserts the engineer profile into MongoDB.
    Accepts a multipart/form-data request with `email` and `cv` (PDF file).
    """
    if not cv.filename.endswith(".pdf"):
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Only PDF files are accepted."})

    # Save the uploaded PDF to a temp file so orchestrator.run() can read it
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await cv.read())
            tmp_path = tmp.name

        run(pdf_path=tmp_path, email=email)

        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": f"Employee '{email}' successfully added.", "file": cv.filename},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)  # clean up temp file