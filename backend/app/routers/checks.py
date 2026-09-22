from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.agents.deterministic_checks import run_deterministic_checks
from app.db import db_session
from app.models import DeterministicCheckOut

router = APIRouter(tags=["deterministic-checks"])


def _locked_limit(conn, question_id: int, kind: str) -> Optional[int]:
    row = conn.execute(
        "SELECT value_text FROM elements WHERE question_id = ? AND kind = ? AND locked = 1 LIMIT 1",
        (question_id, kind),
    ).fetchone()
    if row is None:
        return None
    try:
        return int(row["value_text"])
    except (TypeError, ValueError):
        return None


@router.post("/drafts/{draft_id}/deterministic-checks", response_model=List[DeterministicCheckOut])
def run_checks(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        question = conn.execute("SELECT * FROM questions WHERE id = ?", (draft["question_id"],)).fetchone()
        word_limit = _locked_limit(conn, question["id"], "word_limit")
        diagram_limit = _locked_limit(conn, question["id"], "diagram_limit")

    results = run_deterministic_checks(draft["content_text"], word_limit, diagram_limit, question["category"])

    with db_session() as conn:
        for r in results:
            conn.execute(
                "INSERT INTO deterministic_check_results (draft_id, check_type, passed, detail) VALUES (?, ?, ?, ?)",
                (draft_id, r.check_type, int(r.passed), r.detail),
            )

    return [DeterministicCheckOut(check_type=r.check_type, passed=r.passed, detail=r.detail) for r in results]


@router.get("/drafts/{draft_id}/deterministic-checks", response_model=List[DeterministicCheckOut])
def get_checks(draft_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM deterministic_check_results WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()
    return [DeterministicCheckOut(check_type=r["check_type"], passed=bool(r["passed"]), detail=r["detail"]) for r in rows]
