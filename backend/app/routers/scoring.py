from fastapi import APIRouter, HTTPException

from app.agents.scoring import ScoringBandRow, run_scoring
from app.db import db_session
from app.models import ScoringRunOut, ScoringSummaryOut

router = APIRouter(tags=["scoring"])


@router.post("/drafts/{draft_id}/score", response_model=ScoringSummaryOut)
def score_draft(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        tender = conn.execute(
            """
            SELECT t.id FROM tenders t
            JOIN questions q ON q.tender_id = t.id
            WHERE q.id = ?
            """,
            (draft["question_id"],),
        ).fetchone()

        band_rows = conn.execute(
            "SELECT band_value, descriptor_text FROM scoring_bands WHERE tender_id = ?", (tender["id"],)
        ).fetchall()
        if not band_rows:
            raise HTTPException(
                status_code=400,
                detail="This tender has no scoring bands set. Call POST /tenders/{id}/scoring-bands first.",
            )

        rule_row = conn.execute(
            "SELECT rule_value FROM business_rules WHERE tender_id = ? AND rule_key = 'scoring_confidence_spread_steps'",
            (tender["id"],),
        ).fetchone()

    spread_threshold_steps = 1
    if rule_row is not None:
        try:
            spread_threshold_steps = int(rule_row["rule_value"])
        except ValueError:
            pass  # malformed rule value: fall back to the default rather than fail the whole scoring run

    bands = [ScoringBandRow(band_value=r["band_value"], descriptor_text=r["descriptor_text"]) for r in band_rows]
    summary = run_scoring(draft["content_text"], bands, spread_threshold_steps)

    with db_session() as conn:
        for run in summary.runs:
            conn.execute(
                """
                INSERT INTO scoring_runs (draft_id, pass_number, band_value, rationale, temperature)
                VALUES (?, ?, ?, ?, ?)
                """,
                (draft_id, run.pass_number, run.band_value, run.rationale, run.temperature),
            )
        conn.execute(
            """
            INSERT INTO scoring_summary (draft_id, final_band, confidence, used_moderator)
            VALUES (?, ?, ?, ?)
            """,
            (draft_id, summary.final_band, summary.confidence, int(summary.used_moderator)),
        )

    return ScoringSummaryOut(
        final_band=summary.final_band,
        confidence=summary.confidence,
        used_moderator=summary.used_moderator,
        runs=[
            ScoringRunOut(pass_number=r.pass_number, band_value=r.band_value, rationale=r.rationale, temperature=r.temperature)
            for r in summary.runs
        ],
    )


@router.get("/drafts/{draft_id}/score", response_model=ScoringSummaryOut)
def get_latest_score(draft_id: int):
    with db_session() as conn:
        summary_row = conn.execute(
            "SELECT * FROM scoring_summary WHERE draft_id = ? ORDER BY id DESC LIMIT 1", (draft_id,)
        ).fetchone()
        if summary_row is None:
            raise HTTPException(status_code=404, detail="No scoring run for this draft yet")
        run_rows = conn.execute(
            "SELECT * FROM scoring_runs WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()

    return ScoringSummaryOut(
        final_band=summary_row["final_band"],
        confidence=summary_row["confidence"],
        used_moderator=bool(summary_row["used_moderator"]),
        runs=[
            ScoringRunOut(
                pass_number=r["pass_number"], band_value=r["band_value"], rationale=r["rationale"], temperature=r["temperature"]
            )
            for r in run_rows
        ],
    )
