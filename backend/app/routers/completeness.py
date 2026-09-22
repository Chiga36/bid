from typing import List

from fastapi import APIRouter, HTTPException

from app.agents.completeness import COMPLETENESS_ELEMENT_KINDS, run_completeness
from app.db import db_session
from app.models import CompletenessResultOut

router = APIRouter(tags=["completeness"])


@router.post("/drafts/{draft_id}/completeness", response_model=List[CompletenessResultOut])
def check_completeness(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        placeholders = ",".join("?" for _ in COMPLETENESS_ELEMENT_KINDS)
        locked_elements = conn.execute(
            f"SELECT id, value_text FROM elements WHERE question_id = ? AND locked = 1 AND kind IN ({placeholders})",
            (draft["question_id"], *COMPLETENESS_ELEMENT_KINDS),
        ).fetchall()
        if not locked_elements:
            raise HTTPException(
                status_code=400,
                detail="No locked preamble/constraint elements for this question. Run /decompose then /lock first.",
            )

    elements = [{"id": r["id"], "value_text": r["value_text"]} for r in locked_elements]
    results = run_completeness(draft["content_text"], elements)

    with db_session() as conn:
        for r in results:
            conn.execute(
                """
                INSERT INTO completeness_results (draft_id, element_id, status, quote, rationale, verified)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (draft_id, r.element_id, r.status, r.quote, r.rationale, int(r.verified)),
            )

    return [
        CompletenessResultOut(
            element_id=r.element_id, status=r.status, quote=r.quote, rationale=r.rationale, verified=r.verified
        )
        for r in results
    ]


@router.get("/drafts/{draft_id}/completeness", response_model=List[CompletenessResultOut])
def get_completeness_results(draft_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM completeness_results WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()
    return [
        CompletenessResultOut(
            element_id=r["element_id"],
            status=r["status"],
            quote=r["quote"],
            rationale=r["rationale"],
            verified=bool(r["verified"]),
        )
        for r in rows
    ]
