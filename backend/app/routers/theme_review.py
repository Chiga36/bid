"""Theme Review endpoints. Assembles the toolkit's required inputs from data already collected
by the rest of the workflow — the question text, this tender's scoring bands as the evaluation
criteria, the locked word limit if any, the draft, and retrieved evidence (same call
Recommendation already makes) — then runs the agent and persists the result."""
import json

from fastapi import APIRouter, HTTPException

from app import vector_store
from app.agents.theme_review import run_theme_review
from app.db import db_session
from app.models import GapEntry, PrioritisedImprovement, Theme, ThemeReviewOut

router = APIRouter(tags=["theme-review"])


def _format_evaluation_criteria(band_rows) -> str:
    if not band_rows:
        return ""
    return "\n".join(f"- Band {r['band_value']}: {r['descriptor_text']}" for r in band_rows)


def _row_to_out(row: dict) -> ThemeReviewOut:
    return ThemeReviewOut(
        theme=row["theme"],
        theme_fit=row["theme_fit"],
        evaluator_summary=row["evaluator_summary"],
        strengths=json.loads(row["strengths"]),
        gaps=[GapEntry(**g) for g in json.loads(row["gaps"])],
        prioritised_improvements=[PrioritisedImprovement(**p) for p in json.loads(row["prioritised_improvements"])],
        suggested_wording=json.loads(row["suggested_wording"]),
        evidence_required=json.loads(row["evidence_required"]),
        improved_answer_plan=row["improved_answer_plan"],
        score_compliance=row["score_compliance"],
        score_practicality=row["score_practicality"],
        score_evidence=row["score_evidence"],
        score_client_specificity=row["score_client_specificity"],
        score_evaluator_confidence=row["score_evaluator_confidence"],
    )


@router.post("/drafts/{draft_id}/theme-review", response_model=ThemeReviewOut)
def create_theme_review(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        question = conn.execute("SELECT * FROM questions WHERE id = ?", (draft["question_id"],)).fetchone()

        theme_row = conn.execute(
            "SELECT value_text FROM elements WHERE question_id = ? AND kind = 'theme' AND locked = 1",
            (draft["question_id"],),
        ).fetchone()
        if theme_row is None:
            raise HTTPException(
                status_code=400,
                detail="No locked theme for this question. Run /decompose then /lock first.",
            )
        try:
            theme = Theme(theme_row["value_text"])
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Unrecognised theme '{theme_row['value_text']}'.")

        word_limit_row = conn.execute(
            "SELECT value_text FROM elements WHERE question_id = ? AND kind = 'word_limit' AND locked = 1",
            (draft["question_id"],),
        ).fetchone()

        sub_question_rows = conn.execute(
            "SELECT value_text FROM elements WHERE question_id = ? AND kind = 'sub_question' AND locked = 1 ORDER BY id",
            (draft["question_id"],),
        ).fetchall()

        band_rows = conn.execute(
            "SELECT band_value, descriptor_text FROM scoring_bands WHERE tender_id = ? ORDER BY band_value",
            (question["tender_id"],),
        ).fetchall()

    evaluation_criteria = _format_evaluation_criteria(band_rows)
    word_limit = word_limit_row["value_text"] if word_limit_row else ""
    sub_questions = [r["value_text"] for r in sub_question_rows]
    evidence_chunks = vector_store.query_evidence(question["tender_id"], question["question_text"], top_k=3)
    evidence_context = "\n---\n".join(evidence_chunks)

    result = run_theme_review(
        theme=theme,
        question_text=question["question_text"],
        evaluation_criteria=evaluation_criteria,
        word_limit=word_limit,
        draft_text=draft["content_text"],
        evidence_context=evidence_context,
        sub_questions=sub_questions,
    )

    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO theme_reviews (
                draft_id, theme, theme_fit, evaluator_summary, strengths, gaps,
                prioritised_improvements, suggested_wording, evidence_required, improved_answer_plan,
                score_compliance, score_practicality, score_evidence, score_client_specificity,
                score_evaluator_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                theme.value,
                result.theme_fit,
                result.evaluator_summary,
                json.dumps(result.strengths),
                json.dumps([g.model_dump() for g in result.gaps]),
                json.dumps([p.model_dump() for p in result.prioritised_improvements]),
                json.dumps(result.suggested_wording),
                json.dumps(result.evidence_required),
                result.improved_answer_plan,
                result.score_compliance,
                result.score_practicality,
                result.score_evidence,
                result.score_client_specificity,
                result.score_evaluator_confidence,
            ),
        )

    return ThemeReviewOut(theme=theme.value, **result.model_dump())


@router.get("/drafts/{draft_id}/theme-review", response_model=ThemeReviewOut)
def get_theme_review(draft_id: int):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM theme_reviews WHERE draft_id = ? ORDER BY id DESC LIMIT 1", (draft_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No theme review for this draft yet")
    return _row_to_out(dict(row))
