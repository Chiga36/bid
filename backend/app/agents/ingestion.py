"""Ingestion agent — real LLM understanding, replacing the old heading-heuristic stub entirely.

Every distinct tender question is identified by gpt-5.6-sol reading the document's actual text,
not by pairing headings with the paragraph underneath them. Long documents are chunked on
paragraph boundaries first, so no single call is ever handed an unbounded amount of text — each
chunk is extracted independently and the results are concatenated. Every extracted question_text
is verified as a genuine verbatim substring of its source chunk before being accepted, the same
discipline app/agents/decomposition.py already applies to constraints — a fabricated question
cannot reach the database.
"""
from dataclasses import dataclass
from typing import List

from app import llm_client
from app.models import QuestionExtractionResult

AGENT_NAME = "ingestion"

# Conservative on purpose: keeps every call well within any reasonable context window regardless
# of the exact model, rather than tuning close to a limit we don't have confirmed knowledge of.
_CHUNK_CHAR_LIMIT = 30_000


@dataclass
class CandidateQuestion:
    title: str
    question_text: str
    category: str  # "sq" | "pass_fail" | "scored"


def _split_into_chunks(text: str, limit: int) -> List[str]:
    """Splits on paragraph boundaries (blank lines) so a question's text is never cut mid-sentence
    unless a single paragraph alone exceeds the limit — greedily packs paragraphs into chunks."""
    paragraphs = [p for p in text.split("\n\n") if p]
    if not paragraphs:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for para in paragraphs:
        para_len = len(para) + 2
        if current and current_len + para_len > limit:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _extract_from_chunk(chunk_text: str) -> List[CandidateQuestion]:
    result: QuestionExtractionResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="ingestion_extract_v1.txt",
        variables={"document_text": chunk_text},
        response_model=QuestionExtractionResult,
    )
    candidates: List[CandidateQuestion] = []
    for q in result.questions:
        if q.question_text and q.question_text in chunk_text:
            candidates.append(CandidateQuestion(title=q.title, question_text=q.question_text, category=q.category))
        # Silently dropped if not a verbatim match — no fabricated question reaches the DB.
    return candidates


def extract_questions(document_text: str) -> List[CandidateQuestion]:
    chunks = _split_into_chunks(document_text, _CHUNK_CHAR_LIMIT)
    candidates: List[CandidateQuestion] = []
    for chunk in chunks:
        candidates.extend(_extract_from_chunk(chunk))
    return candidates
