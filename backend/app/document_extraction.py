"""Lightweight, deterministic file reading — replaces Docling entirely.

This is deliberately NOT an AI/ML pipeline: python-docx, openpyxl, and pypdf just unzip and read
a structured file's own text, the same category of operation as json.load(). No model weights,
no OCR, no layout detection, no network calls, no downloaded artifacts. All of the *understanding*
(what's a question, what's noise, what category something belongs to) happens later, in
app/agents/ingestion.py, via a real LLM call — this module's only job is getting clean text and
table rows out of a file.

Scanned/image-only PDFs have no extractable text layer and will come back with little or no
content — that's a visible symptom (an empty or near-empty RawDocument), not a silent wrong
answer. Reading one properly would need either OCR or a vision-capable model call, neither of
which this module does.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import openpyxl
from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass
class RawTable:
    rows: List[List[str]]


@dataclass
class RawDocument:
    full_text: str  # whole-document text, headings prefixed with "## " where the file's own
    # styling says so (real metadata from the file, not a guess) — gives the ingestion agent
    # helpful structure cues without this module doing any heuristic splitting itself
    paragraphs: List[str]  # paragraph/page-level chunks, for evidence chunking
    tables: List[RawTable] = field(default_factory=list)


def _read_docx(path: Path) -> RawDocument:
    doc = DocxDocument(str(path))

    paragraphs: List[str] = []
    full_text_lines: List[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        paragraphs.append(text)
        style_name = (p.style.name if p.style else "") or ""
        if style_name.lower().startswith(("heading", "title")):
            full_text_lines.append(f"## {text}")
        else:
            full_text_lines.append(text)

    tables = [
        RawTable(rows=[[cell.text.strip() for cell in row.cells] for row in table.rows])
        for table in doc.tables
    ]

    return RawDocument(full_text="\n\n".join(full_text_lines), paragraphs=paragraphs, tables=tables)


def _read_xlsx(path: Path) -> RawDocument:
    workbook = openpyxl.load_workbook(str(path), data_only=True)

    full_text_lines: List[str] = []
    paragraphs: List[str] = []
    tables: List[RawTable] = []

    for sheet in workbook.worksheets:
        full_text_lines.append(f"## Sheet: {sheet.title}")
        sheet_rows: List[List[str]] = []
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if not any(cell.strip() for cell in cells):
                continue
            sheet_rows.append(cells)
            full_text_lines.append(" | ".join(cells))
        if sheet_rows:
            tables.append(RawTable(rows=sheet_rows))
            paragraphs.append(f"Sheet: {sheet.title}\n" + "\n".join(" | ".join(r) for r in sheet_rows))

    return RawDocument(full_text="\n\n".join(full_text_lines), paragraphs=paragraphs, tables=tables)


def _read_pdf(path: Path) -> RawDocument:
    reader = PdfReader(str(path))
    paragraphs: List[str] = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            paragraphs.append(text)
    return RawDocument(full_text="\n\n".join(paragraphs), paragraphs=paragraphs, tables=[])


_READERS = {
    ".docx": _read_docx,
    ".xlsx": _read_xlsx,
    ".pdf": _read_pdf,
}


def read_document(path) -> RawDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(_READERS))}.")
    return reader(path)
