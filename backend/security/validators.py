"""
security/validators.py
========================
Domain-level input validators.

Functions
---------
validate_email_field — strict RFC-style email format enforcement
validate_pdf_upload  — magic-bytes check, size cap, page-count guard

Environment variables
---------------------
MAX_PDF_SIZE_MB   : max upload size in MB (default 10)
"""
from __future__ import annotations

import logging
import os
import re

from fastapi import HTTPException, UploadFile

logger = logging.getLogger("security.validators")

# PDF config
MAX_PDF_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "10"))
MAX_PDF_BYTES   = MAX_PDF_SIZE_MB * 1024 * 1024
MAX_PDF_PAGES   = 50
_PDF_MAGIC      = b"%PDF-"

# Email regex (RFC 5321 / 5322 simplified)
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,253}\.[a-zA-Z]{2,}$"
)


def validate_email_field(email: str) -> str:
    """Return the lower-cased, stripped email or raise HTTPException 400."""
    if not email or not isinstance(email, str):
        raise HTTPException(status_code=400, detail="Email is required.")
    clean = email.strip().lower()
    if not _EMAIL_RE.match(clean):
        raise HTTPException(status_code=400, detail=f"Invalid email format: '{email}'.")
    return clean


async def validate_pdf_upload(file: UploadFile) -> bytes:
    """
    Read the upload into memory and verify:
      1. MIME type is application/pdf or filename ends with .pdf
      2. First 5 bytes match the PDF magic bytes (%PDF-)
      3. File size ≤ MAX_PDF_BYTES
      4. Page count ≤ MAX_PDF_PAGES  (pdfplumber)

    Returns raw bytes on success; raises HTTPException on any failure.
    """
    filename     = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    if not filename.endswith(".pdf") and "pdf" not in content_type:
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    raw = await file.read()

    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the maximum allowed size of {MAX_PDF_SIZE_MB} MB.",
        )
    if len(raw) < 5:
        raise HTTPException(status_code=400, detail="File is too small to be a valid PDF.")

    if not raw.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid PDF (bad magic bytes).",
        )

    try:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            num_pages = len(pdf.pages)
        if num_pages > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=400,
                detail=f"PDF has {num_pages} pages; maximum allowed is {MAX_PDF_PAGES}.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse PDF: {exc}")

    logger.info("PDF validated: %s (%d bytes, %d pages)", filename, len(raw), num_pages)
    return raw
