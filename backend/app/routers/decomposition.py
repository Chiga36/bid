"""Decomposition agent endpoints, and the human verification gate that locks its output before
anything downstream (Deterministic checks, Completeness, Scoring) is allowed to trust it.
"""
import json
from typing import List

from fastapi import APIRouter, HTTPException

from app import vector_store
from app.agents.decomposition import run_decomposition
from app.agents.evidence_score import score_sub_answer_evidence
from app.agents.methodology import format_methodology_context
from app.db import db_session
from app.document_extraction import RawTable, read_document
from app.models import ElementOut, EvidenceScoreIn, EvidenceScoreResult

router = APIRouter(tags=["decomposition"])


def _tables_for_question(question_row) -> List[RawTable]:
    """Best-effort: if this question came from an uploaded document, re-read it to get the
    scoring-matrix tables. Manually-added questions have no document to re-read."""
    source_ref = question_row["source_ref"] or ""
    if not source_ref.startswith("document:"):
        return []
    document_id = source_ref.split(":", 1)[1]
    with db_session() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None:
        return []
    parsed = read_document(doc["file_path"])
    return parsed.tables


def _methodology_context_for_tender(tender_id: int) -> str:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT content_text FROM evaluation_methodology WHERE tender_id = ? ORDER BY id", (tender_id,)
        ).fetchall()
    return format_methodology_context([r["content_text"] for r in rows])


@router.post("/questions/{question_id}/decompose", response_model=List[ElementOut])
def decompose_question(question_id: int):
    """Idempotent by design: safe to call again after a failure (nothing was saved) or after a
    prior success (unlocked candidates are replaced, not duplicated). Locked elements are never
    touched here — once a human has locked the register, only /lock's own table update can
    change it."""
    with db_session() as conn:
        question = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")

    tender_id = question["tender_id"]
    with db_session() as conn:
        has_requirements = conn.execute(
            "SELECT 1 FROM tender_requirements WHERE tender_id = ? LIMIT 1", (tender_id,)
        ).fetchone()
    if has_requirements is None:
        raise HTTPException(
            status_code=400,
            detail="Upload the competition tender instructions document under Strategy first.",
        )

    tables = _tables_for_question(question)
    methodology_context = _methodology_context_for_tender(tender_id)
    tender_instructions_chunks = vector_store.query_tender_requirements(tender_id, question["question_text"])
    tender_instructions_context = "\n\n".join(tender_instructions_chunks)
    evidence_chunks = vector_store.query_evidence(tender_id, question["question_text"])
    evidence_context = "\n\n".join(evidence_chunks)
    candidates = run_decomposition(
        question["title"],
        question["question_text"],
        tables,
        methodology_context,
        tender_instructions_context,
        evidence_context,
        tender_id,
    )

    created: List[dict] = []
    with db_session() as conn:
        conn.execute("DELETE FROM elements WHERE question_id = ? AND locked = 0", (question_id,))
        for c in candidates:
            cur = conn.execute(
                """
                INSERT INTO elements (
                    question_id, kind, value_text, source_quote, elaboration, answer_guidance,
                    extraction_method, locked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    question_id, c.kind, c.value_text, c.source_quote, c.elaboration,
                    json.dumps(c.answer_guidance) if c.answer_guidance is not None else None,
                    c.extraction_method,
                ),
            )
            row = conn.execute("SELECT * FROM elements WHERE id = ?", (cur.lastrowid,)).fetchone()
            created.append(dict(row))

    return [_element_out(r) for r in created]


@router.get("/questions/{question_id}/elements", response_model=List[ElementOut])
def list_elements(question_id: int):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM elements WHERE question_id = ? ORDER BY id", (question_id,)).fetchall()
    return [_element_out(dict(r)) for r in rows]


@router.post("/questions/{question_id}/lock", response_model=List[ElementOut])
def lock_register(question_id: int):
    """The human verification gate. In this backend-first pass it's a direct endpoint call —
    the bid-manager review UI comes later — but it is the one place any element becomes trusted
    enough for Deterministic checks, Completeness, or Scoring to use."""
    with db_session() as conn:
        elements = conn.execute("SELECT * FROM elements WHERE question_id = ?", (question_id,)).fetchall()
        if not elements:
            raise HTTPException(status_code=404, detail="No elements to lock for this question. Run /decompose first.")
        conn.execute("UPDATE elements SET locked = 1 WHERE question_id = ?", (question_id,))
        rows = conn.execute("SELECT * FROM elements WHERE question_id = ? ORDER BY id", (question_id,)).fetchall()
    return [_element_out(dict(r)) for r in rows]


def _element_out(row: dict) -> dict:
    row = dict(row)
    row["locked"] = bool(row["locked"])
    if row.get("answer_guidance"):
        try:
            row["answer_guidance"] = json.loads(row["answer_guidance"])
        except (json.JSONDecodeError, TypeError):
            # A plain-string row from before this field became a JSON-encoded list (or any other
            # malformed value) — degrade gracefully to a single-item list rather than 500ing.
            row["answer_guidance"] = [row["answer_guidance"]]
    return row


@router.post("/elements/{element_id}/evidence-score", response_model=EvidenceScoreResult)
def score_element_evidence(element_id: int, body: EvidenceScoreIn):
    """Stateless — scores how much the given answer_text itself reads as concrete, past-tense
    proof of delivery (judged on its own writing, never cross-referenced against the evidence
    library — see agents/evidence_score.py). Neither the answer text nor the score is persisted;
    the answer only becomes durable once composed into the real draft and saved as a version,
    same as the rest of Response Builder."""
    with db_session() as conn:
        element = conn.execute("SELECT * FROM elements WHERE id = ?", (element_id,)).fetchone()
        if element is None:
            raise HTTPException(status_code=404, detail="Element not found")
        question = conn.execute("SELECT tender_id FROM questions WHERE id = ?", (element["question_id"],)).fetchone()

    return score_sub_answer_evidence(
        sub_question_text=element["value_text"],
        elaboration=element["elaboration"] or "",
        answer_text=body.answer_text,
        tender_id=question["tender_id"],
    )
