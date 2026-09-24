"""Scoring Matrix agent — extracts a tender's own scoring-band descriptors (the "Scoring Matrix" /
"Quality Criteria" table) from a Strategy and Context upload, so `scoring_bands` no longer has to
be typed in by hand. Works on `RawTable`s (docx tables / xlsx sheets, see
app/document_extraction.py) rather than chunked prose — a scoring matrix is a real table, not
free text.

Judging whether a given table genuinely IS the scoring matrix is real understanding (tables come
in many shapes, and most tables in a tender document are NOT the scoring matrix), so that part is
an LLM call. Extracting the descriptor wording is not — every returned descriptor_text is checked
as a genuine substring of that table's own serialized text before being trusted, the same
discipline app/agents/tender_requirements.py already applies to requirement_text.
"""
from dataclasses import dataclass
from typing import List

from app import llm_client
from app.document_extraction import RawTable
from app.models import ScoringMatrixExtractionResult

AGENT_NAME = "scoring_matrix"

# Real scoring matrices are small (one row per band, a handful of columns). Anything bigger is
# almost certainly a different table (e.g. the Award Questionnaire itself) — skip it outright
# rather than spending an LLM call ruling it out.
_MAX_TABLE_ROWS = 60

_SIGNAL_WORDS = ("score", "scoring", "quality criteria", "band", "descriptor", "weighting")
_BAND_NUMBER_SIGNALS = ("0%", "25%", "50%", "75%", "100%")


@dataclass
class ExtractedBand:
    band_value: int
    descriptor_text: str


def _serialize_table(table: RawTable) -> str:
    return "\n".join(" | ".join(row) for row in table.rows)


def _looks_like_scoring_matrix(serialized: str) -> bool:
    """Cheap deterministic pre-filter, no LLM call: does this table even plausibly discuss
    scoring bands? Kept permissive (any one signal is enough) — a false positive here only costs
    one extra LLM call, a false negative would silently miss the real matrix entirely."""
    lowered = serialized.lower()
    if any(word in lowered for word in _SIGNAL_WORDS):
        return True
    if any(signal in serialized for signal in _BAND_NUMBER_SIGNALS):
        return True
    # Bare band numbers as their own cell/column, e.g. "0 | 25 | 50 | 75 | 100"
    return all(str(n) in serialized for n in (0, 25, 50, 75, 100))


def _extract_from_table(table: RawTable) -> List[ExtractedBand]:
    serialized = _serialize_table(table)
    result: ScoringMatrixExtractionResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="scoring_matrix_extract_v1.txt",
        variables={"table_text": serialized},
        response_model=ScoringMatrixExtractionResult,
    )
    if not result.is_scoring_matrix:
        return []
    return [
        ExtractedBand(band_value=b.band_value, descriptor_text=b.descriptor_text)
        for b in result.bands
        if b.descriptor_text and b.descriptor_text in serialized
    ]


def extract_scoring_bands(tables: List[RawTable]) -> List[ExtractedBand]:
    """Tries each table in order; the first one that both looks plausible AND the model confirms
    (with at least one verbatim-verified band) wins. Returns [] if nothing in this document is
    the tender's scoring matrix — callers must treat that as "nothing found", never fabricate
    bands to fill the gap."""
    for table in tables:
        if not table.rows or len(table.rows) > _MAX_TABLE_ROWS:
            continue
        serialized = _serialize_table(table)
        if not _looks_like_scoring_matrix(serialized):
            continue
        bands = _extract_from_table(table)
        if bands:
            return bands
    return []
