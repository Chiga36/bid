"""Lightweight, deterministic file reading — replaces Docling entirely.

This is deliberately NOT an AI/ML pipeline: python-docx, openpyxl, python-pptx, and pypdf just
unzip and read a structured file's own text, the same category of operation as json.load(). No model weights,
no OCR, no layout detection, no network calls, no downloaded artifacts. All of the *understanding*
(what's a question, what's noise, what category something belongs to) happens later, in
app/agents/ingestion.py, via a real LLM call — this module's only job is getting clean text and
table rows out of a file.

Scanned/image-only PDFs have no extractable text layer and will come back with little or no
content — that's a visible symptom (an empty or near-empty RawDocument), not a silent wrong
answer. Reading one properly would need either OCR or a vision-capable model call, neither of
which this module does.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import openpyxl
from docx import Document as DocxDocument
from pptx import Presentation
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


_NUMBER_CELL_PATTERN = re.compile(r"^\d+(\.\d+)*$")


def _row_number_segments(cells: List[str]):
    """Returns the dot-separated segments of the row's first cell if it looks like a hierarchical
    item number (e.g. "3.1.2" -> ["3", "1", "2"]), else None — the header row ("Number | Name |
    ..."), a blank-number instructional row, or anything else that isn't a numbered item."""
    first = cells[0].strip() if cells else ""
    if not _NUMBER_CELL_PATTERN.match(first):
        return None
    return first.split(".")


def _is_section_header(current_segments, next_segments) -> bool:
    """A row is a section header — a label, not a real question — if the very next numbered row
    nests directly under it: its number starts with this row's number as a dot-prefix (e.g. "3.1"
    before "3.1.1", or "3.4.2" before "3.4.2.1"). Holds regardless of nesting depth, with no need
    to guess from content length or wording."""
    if current_segments is None or next_segments is None:
        return False
    return len(next_segments) > len(current_segments) and next_segments[: len(current_segments)] == current_segments


def _rows_to_text_lines(rows: List[List[str]]) -> List[str]:
    """Marks detected section-header rows as "## Section: <name>" (same marker convention as
    "## Sheet: " and docx's "## <heading>") instead of dumping them as a raw row, so downstream
    extraction (app/agents/ingestion.py) can tell a section label apart from a real question
    without inferring it purely from prose."""
    segments_per_row = [_row_number_segments(row) for row in rows]
    lines: List[str] = []
    for i, row in enumerate(rows):
        next_segments = next((s for s in segments_per_row[i + 1 :] if s is not None), None)
        if _is_section_header(segments_per_row[i], next_segments):
            name = row[1].strip() if len(row) > 1 and row[1].strip() else row[0].strip()
            lines.append(f"## Section: {name}")
        else:
            lines.append(" | ".join(row))
    return lines


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
        full_text_lines.extend(_rows_to_text_lines(sheet_rows))
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


def _read_pptx(path: Path) -> RawDocument:
    prs = Presentation(str(path))

    full_text_lines: List[str] = []
    paragraphs: List[str] = []
    tables: List[RawTable] = []

    for i, slide in enumerate(prs.slides, start=1):
        full_text_lines.append(f"## Slide {i}")
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    paragraphs.append(text)
                    full_text_lines.append(text)
            if shape.has_table:
                rows = [[cell.text.strip() for cell in row.cells] for row in shape.table.rows]
                if rows:
                    tables.append(RawTable(rows=rows))
                    serialized = "\n".join(" | ".join(r) for r in rows)
                    paragraphs.append(serialized)
                    full_text_lines.append(serialized)

    return RawDocument(full_text="\n\n".join(full_text_lines), paragraphs=paragraphs, tables=tables)


_READERS = {
    ".docx": _read_docx,
    ".xlsx": _read_xlsx,
    ".pdf": _read_pdf,
    ".pptx": _read_pptx,
}

# Public, stable export of the supported-extension set — e.g. routers/zip_ingestion.py uses this
# to silently skip unsupported files (images, .DS_Store, nested archives) found inside a ZIP,
# without reaching into the "private" _READERS dict directly.
SUPPORTED_EXTENSIONS = frozenset(_READERS)


def read_document(path) -> RawDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(_READERS))}.")
    return reader(path)


_SHEET_MARKER_PATTERN = re.compile(r"^## Sheet: (.+)$", re.MULTILINE)


def _filter_sheets(full_text: str, name_patterns: List[str], keep_matching: bool) -> str:
    matches = list(_SHEET_MARKER_PATTERN.finditer(full_text))
    if not matches:
        return full_text

    lowered_patterns = [p.lower() for p in name_patterns]
    kept_blocks: List[str] = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        is_match = any(pattern in title.lower() for pattern in lowered_patterns)
        if is_match != keep_matching:
            continue
        kept_blocks.append(full_text[start:end].strip())
    return "\n\n".join(kept_blocks)


def exclude_sheets(full_text: str, name_patterns: List[str]) -> str:
    """Drops any '## Sheet: <title>' block (as written by _read_xlsx above) whose title matches
    one of `name_patterns` (case-insensitive substring match) — e.g. excluding a "Selection
    Questionnaire" sheet before question extraction ever sees it, so the LLM can't extract from
    content it was never shown. A no-op on text with no sheet markers at all, i.e. anything that
    didn't come from an .xlsx — this only ever applies to xlsx's own sheet structure."""
    return _filter_sheets(full_text, name_patterns, keep_matching=False)


def keep_only_sheets(full_text: str, name_patterns: List[str]) -> str:
    """The inverse of exclude_sheets — an allowlist rather than a blocklist: drops every sheet
    whose title does NOT match one of `name_patterns`, keeping only the ones that do. Safer than
    exclude_sheets for a question-extraction source like the Award Questionnaire: a real tender
    workbook can carry extra sheets beyond the two well-known ones (a cover page, an "Other
    Content" tab, instructions) with unpredictable names — naming every sheet to exclude is a
    losing game, whereas naming the one sheet that genuinely IS the question set is robust
    regardless of what else the workbook contains. A no-op on text with no sheet markers at all."""
    return _filter_sheets(full_text, name_patterns, keep_matching=True)
