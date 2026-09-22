"""Versioned clarification responses. Storing and surfacing these is the scope here — resolving
one into the locked register is a human decision, made by re-running the already-idempotent
POST /questions/{id}/decompose after reading the clarification, not automated conflict
resolution."""
from typing import List

from fastapi import APIRouter, HTTPException

from app.db import db_session
from app.models import ClarificationCreate, ClarificationOut

router = APIRouter(tags=["clarifications"])


@router.post("/tenders/{tender_id}/clarifications", response_model=ClarificationOut)
def add_clarification(tender_id: int, clarification: ClarificationCreate):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        last = conn.execute(
            "SELECT MAX(version_number) AS v FROM clarifications WHERE tender_id = ?", (tender_id,)
        ).fetchone()
        next_version = (last["v"] or 0) + 1
        cur = conn.execute(
            "INSERT INTO clarifications (tender_id, question_id, content_text, version_number) VALUES (?, ?, ?, ?)",
            (tender_id, clarification.question_id, clarification.content_text, next_version),
        )
        row = conn.execute("SELECT * FROM clarifications WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.get("/tenders/{tender_id}/clarifications", response_model=List[ClarificationOut])
def list_clarifications(tender_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM clarifications WHERE tender_id = ? ORDER BY version_number", (tender_id,)
        ).fetchall()
    return [dict(r) for r in rows]
