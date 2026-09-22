"""Tender Requirements agent — a traceable requirements register extracted from the competition
tender instructions document (uploaded under Strategy and Context). Feeds Decomposition (better
question understanding) and Completeness (per-element context) via Chroma retrieval — never
dumped wholesale into a prompt, since a real tender instructions document can be long.

Same chunking approach as app/agents/ingestion.py (reused directly, not duplicated) — no single
call is ever handed an unbounded document — and the same verbatim-verification discipline:
requirement_text is checked as a genuine substring of its source chunk before being accepted.
"""
from dataclasses import dataclass
from typing import List

from app import llm_client
from app.models import TenderRequirementExtractionResult
from app.text_chunking import split_into_chunks

AGENT_NAME = "tender_requirements"

_CHUNK_CHAR_LIMIT = 30_000


@dataclass
class ExtractedRequirement:
    category: str
    requirement_text: str
    strength: str


def _extract_from_chunk(chunk_text: str) -> List[ExtractedRequirement]:
    result: TenderRequirementExtractionResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="tender_requirements_extract_v1.txt",
        variables={"document_text": chunk_text},
        response_model=TenderRequirementExtractionResult,
    )
    extracted: List[ExtractedRequirement] = []
    for r in result.requirements:
        if r.requirement_text and r.requirement_text in chunk_text:
            extracted.append(
                ExtractedRequirement(category=r.category, requirement_text=r.requirement_text, strength=r.strength)
            )
        # Silently dropped if not a verbatim match — no fabricated requirement reaches the DB.
    return extracted


def extract_requirements(document_text: str) -> List[ExtractedRequirement]:
    chunks = split_into_chunks(document_text, _CHUNK_CHAR_LIMIT)
    requirements: List[ExtractedRequirement] = []
    for chunk in chunks:
        requirements.extend(_extract_from_chunk(chunk))
    return requirements
