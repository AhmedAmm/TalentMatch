"""
services/pdf.py
================
PDF text extraction using Docling (IBM Research) — OCR disabled.

Docling applies an ML-based document-understanding pipeline that produces
richer output than plain text extractors:

  - Multi-column layouts handled correctly
  - Tables extracted and rendered as Markdown tables
  - Heading hierarchy (H1/H2/H3) preserved
  - Lists and bullet points retained

OCR is disabled because all documents here (CVs, project PDFs) are
text-based — they carry an embedded text layer.  Skipping OCR:
  - Removes the ~1 GB Tesseract / EasyOCR model download
  - Cuts per-document processing time significantly

Output format: Markdown — gives the downstream LLM cleaner, more
structured input than raw concatenated text.

The extracted Markdown is printed to stdout so operators can verify the
quality of the extraction before the LLM ingestion step.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str, *, show_output: bool = True) -> str:
    """
    Extract all content from a PDF using Docling without OCR.

    Parameters
    ----------
    pdf_path    : absolute or relative path to the PDF file.
    show_output : when True (default), prints the extracted Markdown to stdout
                  so operators can verify extraction quality before the LLM step.

    Returns
    -------
    str — extracted content as Markdown.

    Raises
    ------
    Exception — propagates any Docling conversion error to the caller.
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr              = False   # use embedded text layer only
    pipeline_options.do_table_structure  = True    # keep table detection (no OCR)
    pipeline_options.generate_page_images = False  # no page rendering needed

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    result   = converter.convert(str(pdf_path))
    markdown = result.document.export_to_markdown()

    if show_output:
        _display_extraction(pdf_path, markdown)

    return markdown


def _display_extraction(pdf_path: str, markdown: str) -> None:
    """Print a formatted preview of the Docling-extracted content."""
    separator = "─" * 72
    lines     = markdown.splitlines()
    n_lines   = len(lines)
    n_chars   = len(markdown)

    print(f"\n{separator}")
    print(f"  DOCLING EXTRACTION — {pdf_path}")
    print(f"  {n_lines} lines · {n_chars:,} characters")
    print(separator)

    # Show the first 60 lines as a preview
    preview_limit = 60
    for line in lines[:preview_limit]:
        print(line)

    if n_lines > preview_limit:
        remaining = n_lines - preview_limit
        print(f"\n  … {remaining} more line(s) not shown …")

    print(f"{separator}\n")
    logger.info("[PDF] Extracted %d chars from %s", n_chars, pdf_path)
