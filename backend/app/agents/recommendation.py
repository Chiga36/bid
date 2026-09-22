"""Recommendation agent. Retrieval is deterministic (ChromaDB similarity search, no LLM) —
the model's only job is to turn already-retrieved evidence into a capped, ranked set of fix
pointers. Mirrors the 'top three fixes, evidence pointers not wording' design agreed earlier:
the schema itself caps the list at 3 (see models.RecommendationResult), and the prompt forbids
writing replacement prose. Elements are tagged [E<id>] so the model's reference back to a
requirement is parsed deterministically in code, not fuzzy-matched against free text.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from app import llm_client, vector_store
from app.models import RecommendationResult

AGENT_NAME = "recommendation"

_ELEMENT_TAG_PATTERN = re.compile(r"\[E(\d+)\]")


@dataclass
class UnaddressedElement:
    element_id: int
    value_text: str
    status: str
    rationale: Optional[str]


@dataclass
class RecommendationRow:
    rank: int
    element_id: Optional[int]
    fix_summary: str
    evidence_pointer: str
    word_budget: int


def _build_unaddressed_summary(elements: List[UnaddressedElement]) -> str:
    lines = [
        f"[E{e.element_id}] {e.value_text} — status: {e.status}. {e.rationale or ''}".strip()
        for e in elements
    ]
    return "\n".join(lines) if lines else "(none — nothing unaddressed)"


def _build_evidence_context(tender_id: int, elements: List[UnaddressedElement]) -> str:
    seen = set()
    chunks: List[str] = []
    for e in elements:
        for chunk in vector_store.query_evidence(tender_id, e.value_text, top_k=2):
            if chunk not in seen:
                seen.add(chunk)
                chunks.append(chunk)
    if not chunks:
        return "(no matching evidence found in this tender's evidence library)"
    return "\n---\n".join(chunks)


def run_recommendation(
    draft_text: str,
    tender_id: int,
    elements: List[UnaddressedElement],
    evaluation_methodology_context: str = "",
) -> List[RecommendationRow]:
    if not elements:
        return []

    unaddressed_summary = _build_unaddressed_summary(elements)
    evidence_context = _build_evidence_context(tender_id, elements)
    methodology_section = evaluation_methodology_context or "(none available)"

    result: RecommendationResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="recommendation_v1.txt",
        variables={
            "draft_text": draft_text,
            "unaddressed_summary": unaddressed_summary,
            "evidence_context": evidence_context,
            "evaluation_methodology_section": methodology_section,
        },
        response_model=RecommendationResult,
    )

    rows: List[RecommendationRow] = []
    for rank, fix in enumerate(result.fixes, start=1):
        match = _ELEMENT_TAG_PATTERN.search(fix.element_reference)
        element_id = int(match.group(1)) if match else None
        rows.append(
            RecommendationRow(
                rank=rank,
                element_id=element_id,
                fix_summary=fix.fix_summary,
                evidence_pointer=fix.evidence_pointer,
                word_budget=fix.word_budget,
            )
        )
    return rows
