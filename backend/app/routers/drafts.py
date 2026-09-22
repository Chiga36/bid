from typing import List

from fastapi import APIRouter, HTTPException

from app.db import db_session
from app.models import DraftCreate, DraftOut

router = APIRouter(tags=["drafts"])


@router.post("/questions/{question_id}/drafts", response_model=DraftOut)
def create_draft(question_id: int, draft: DraftCreate):
    with db_session() as conn:
        question = conn.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")
        last = conn.execute(
            "SELECT MAX(version_number) AS v FROM drafts WHERE question_id = ?", (question_id,)
        ).fetchone()
        next_version = (last["v"] or 0) + 1
        cur = conn.execute(
            "INSERT INTO drafts (question_id, version_number, content_text) VALUES (?, ?, ?)",
            (question_id, next_version, draft.content_text),
        )
        row = conn.execute("SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.get("/questions/{question_id}/drafts", response_model=List[DraftOut])
def list_drafts(question_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE question_id = ? ORDER BY version_number", (question_id,)
        ).fetchall()
    return [dict(r) for r in rows]
