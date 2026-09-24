"""Procurement Timeline agent — extracts the tender's procurement timetable (stage name + date
pairs, e.g. "ITT issued" / "14 March 2026") from a Strategy and Context upload.

Real timetables show up two ways: as a genuine table (same shape as a scoring matrix — see
app/agents/scoring_matrix.py, whose table-classification pattern this reuses directly), or as a
bulleted list / paragraph of prose (same shape tender_requirements.py already handles via chunked
extraction). This agent tries tables first, since a table is the stronger/cleaner signal when one
exists, and falls back to prose chunking only if no table was classified as the timetable.

Both paths keep the same verbatim-verification discipline as every other extractor in this app:
stage_name/stage_date are checked as genuine substrings of their source (table or chunk) before
being trusted — a value that doesn't verify is dropped, not guessed at. stage_date is always kept
as free text, never parsed into a real date, since source documents state dates with wildly
varying precision ("14 March 2026", "Q2 2026", "TBC").
"""
from dataclasses import dataclass
from typing import List

from app import llm_client
from app.document_extraction import RawTable
from app.models import ProcurementTimelineProseResult, ProcurementTimelineTableResult
from app.text_chunking import split_into_chunks

AGENT_NAME = "procurement_timeline"

_CHUNK_CHAR_LIMIT = 30_000
_MAX_TABLE_ROWS = 60
_SIGNAL_WORDS = ("timetable", "timeline", "procurement stage", "key date", "milestone", "schedule")


@dataclass
class ExtractedStage:
    stage_name: str
    stage_date: str


def _serialize_table(table: RawTable) -> str:
    return "\n".join(" | ".join(row) for row in table.rows)


def _looks_like_timetable(serialized: str) -> bool:
    """Cheap deterministic pre-filter, no LLM call — same permissive philosophy as
    scoring_matrix._looks_like_scoring_matrix: any one signal is enough to warrant asking the
    model, since a false positive only costs one extra call."""
    return any(word in serialized.lower() for word in _SIGNAL_WORDS)


def _extract_from_table(table: RawTable) -> List[ExtractedStage]:
    serialized = _serialize_table(table)
    result: ProcurementTimelineTableResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="procurement_timeline_extract_table_v1.txt",
        variables={"table_text": serialized},
        response_model=ProcurementTimelineTableResult,
    )
    if not result.is_procurement_timeline:
        return []
    return [
        ExtractedStage(stage_name=s.stage_name, stage_date=s.stage_date)
        for s in result.stages
        if s.stage_name and s.stage_name in serialized and s.stage_date and s.stage_date in serialized
    ]


def _extract_from_tables(tables: List[RawTable]) -> List[ExtractedStage]:
    for table in tables:
        if not table.rows or len(table.rows) > _MAX_TABLE_ROWS:
            continue
        serialized = _serialize_table(table)
        if not _looks_like_timetable(serialized):
            continue
        stages = _extract_from_table(table)
        if stages:
            return stages
    return []


def _extract_from_chunk(chunk_text: str) -> List[ExtractedStage]:
    result: ProcurementTimelineProseResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="procurement_timeline_extract_prose_v1.txt",
        variables={"document_text": chunk_text},
        response_model=ProcurementTimelineProseResult,
    )
    return [
        ExtractedStage(stage_name=s.stage_name, stage_date=s.stage_date)
        for s in result.stages
        if s.stage_name and s.stage_name in chunk_text and s.stage_date and s.stage_date in chunk_text
    ]


def _extract_from_prose(document_text: str) -> List[ExtractedStage]:
    chunks = split_into_chunks(document_text, _CHUNK_CHAR_LIMIT)
    stages: List[ExtractedStage] = []
    for chunk in chunks:
        stages.extend(_extract_from_chunk(chunk))
    return stages


def extract_procurement_stages(tables: List[RawTable], document_text: str) -> List[ExtractedStage]:
    table_stages = _extract_from_tables(tables)
    if table_stages:
        return table_stages
    return _extract_from_prose(document_text)
