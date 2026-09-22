from typing import List

from fastapi import APIRouter, HTTPException

from app.agents.methodology import format_methodology_context
from app.agents.recommendation import UnaddressedElement, run_recommendation
from app.db import db_session
from app.models import RecommendationOut

router = APIRouter(tags=["recommendations"])


def _latest_completeness_by_element(rows):
    latest = {}
    for row in rows:  # ascending id order: last write per element_id wins
        latest[row["element_id"]] = row
    return latest


@router.post("/drafts/{draft_id}/recommendations", response_model=List[RecommendationOut])
def create_recommendations(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        tender = conn.execute(
            "SELECT t.id FROM tenders t JOIN questions q ON q.tender_id = t.id WHERE q.id = ?",
            (draft["question_id"],),
        ).fetchone()

        completeness_rows = conn.execute(
            "SELECT * FROM completeness_results WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()
        latest = _latest_completeness_by_element(completeness_rows)
        unaddressed_ids = [eid for eid, r in latest.items() if r["status"] != "addressed"]

        elements: List[UnaddressedElement] = []
        for eid in unaddressed_ids:
            el = conn.execute("SELECT * FROM elements WHERE id = ?", (eid,)).fetchone()
            if el is None:
                continue
            finding = latest[eid]
            elements.append(
                UnaddressedElement(
                    element_id=eid,
                    value_text=el["value_text"],
                    status=finding["status"],
                    rationale=finding["rationale"],
                )
            )

    if not elements:
        return []

    with db_session() as conn:
        methodology_rows = conn.execute(
            "SELECT content_text FROM evaluation_methodology WHERE tender_id = ? ORDER BY id", (tender["id"],)
        ).fetchall()
    methodology_context = format_methodology_context([r["content_text"] for r in methodology_rows])

    rows = run_recommendation(draft["content_text"], tender["id"], elements, methodology_context)

    with db_session() as conn:
        for r in rows:
            conn.execute(
                """
                INSERT INTO recommendations (draft_id, rank, element_id, fix_summary, evidence_pointer, word_budget)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (draft_id, r.rank, r.element_id, r.fix_summary, r.evidence_pointer, r.word_budget),
            )

    return [
        RecommendationOut(
            rank=r.rank, element_id=r.element_id, fix_summary=r.fix_summary,
            evidence_pointer=r.evidence_pointer, word_budget=r.word_budget,
        )
        for r in rows
    ]


@router.get("/drafts/{draft_id}/recommendations", response_model=List[RecommendationOut])
def get_recommendations(draft_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE draft_id = ? ORDER BY rank", (draft_id,)
        ).fetchall()
    return [
        RecommendationOut(
            rank=r["rank"], element_id=r["element_id"], fix_summary=r["fix_summary"],
            evidence_pointer=r["evidence_pointer"], word_budget=r["word_budget"],
        )
        for r in rows
    ]
