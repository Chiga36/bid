"""Benchmark (offline) harness. No new agent logic: a historical case's draft text is run
through the *same* Completeness and Scoring agents used live, persisted as a normal draft/run
(so the full per-element findings are inspectable via the existing GET /drafts/{id}/completeness
and GET /drafts/{id}/score endpoints), and the predicted band is compared against the known,
already-scored outcome.
"""
from typing import List

from fastapi import APIRouter, HTTPException

from app.agents.completeness import COMPLETENESS_ELEMENT_KINDS, run_completeness
from app.agents.scoring import ScoringBandRow, run_scoring
from app.db import db_session
from app.models import BenchmarkCaseCreate, BenchmarkCaseOut, BenchmarkResultOut

router = APIRouter(tags=["benchmark"])


def compute_band_delta(predicted_band: int, known_band: int) -> int:
    """Positive: the agents scored the historical answer higher than it actually scored.
    Negative: lower. Zero: exact match. Pulled out as its own function so this comparison is
    unit-testable without a live database or an Azure OpenAI call."""
    return predicted_band - known_band


@router.post("/tenders/{tender_id}/benchmark/cases", response_model=BenchmarkCaseOut)
def add_case(tender_id: int, case: BenchmarkCaseCreate):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        question = conn.execute(
            "SELECT id FROM questions WHERE id = ? AND tender_id = ?", (case.question_id, tender_id)
        ).fetchone()
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found for this tender")
        cur = conn.execute(
            """
            INSERT INTO benchmark_cases (tender_id, question_id, historical_draft_text, known_band, outcome_notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tender_id, case.question_id, case.historical_draft_text, case.known_band, case.outcome_notes),
        )
        row = conn.execute("SELECT * FROM benchmark_cases WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.get("/tenders/{tender_id}/benchmark/cases", response_model=List[BenchmarkCaseOut])
def list_cases(tender_id: int):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM benchmark_cases WHERE tender_id = ? ORDER BY id", (tender_id,)).fetchall()
    return [dict(r) for r in rows]


@router.post("/benchmark/cases/{case_id}/run", response_model=BenchmarkResultOut)
def run_case(case_id: int):
    with db_session() as conn:
        case = conn.execute("SELECT * FROM benchmark_cases WHERE id = ?", (case_id,)).fetchone()
        if case is None:
            raise HTTPException(status_code=404, detail="Benchmark case not found")

        placeholders = ",".join("?" for _ in COMPLETENESS_ELEMENT_KINDS)
        locked_elements = conn.execute(
            f"SELECT id, value_text FROM elements WHERE question_id = ? AND locked = 1 AND kind IN ({placeholders})",
            (case["question_id"], *COMPLETENESS_ELEMENT_KINDS),
        ).fetchall()
        if not locked_elements:
            raise HTTPException(
                status_code=400,
                detail="This question has no locked preamble/constraint elements. Decompose and lock it first.",
            )

        band_rows = conn.execute(
            "SELECT band_value, descriptor_text FROM scoring_bands WHERE tender_id = ?", (case["tender_id"],)
        ).fetchall()
        if not band_rows:
            raise HTTPException(status_code=400, detail="This tender has no scoring bands set.")

        last = conn.execute(
            "SELECT MAX(version_number) AS v FROM drafts WHERE question_id = ?", (case["question_id"],)
        ).fetchone()
        next_version = (last["v"] or 0) + 1
        draft_cur = conn.execute(
            "INSERT INTO drafts (question_id, version_number, content_text) VALUES (?, ?, ?)",
            (case["question_id"], next_version, case["historical_draft_text"]),
        )
        draft_id = draft_cur.lastrowid

    elements = [{"id": r["id"], "value_text": r["value_text"]} for r in locked_elements]
    completeness_rows = run_completeness(case["historical_draft_text"], elements)
    bands = [ScoringBandRow(band_value=r["band_value"], descriptor_text=r["descriptor_text"]) for r in band_rows]
    summary = run_scoring(case["historical_draft_text"], bands)

    with db_session() as conn:
        for r in completeness_rows:
            conn.execute(
                """
                INSERT INTO completeness_results (draft_id, element_id, status, quote, rationale, verified)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (draft_id, r.element_id, r.status, r.quote, r.rationale, int(r.verified)),
            )
        for run in summary.runs:
            conn.execute(
                """
                INSERT INTO scoring_runs (draft_id, pass_number, band_value, rationale, temperature)
                VALUES (?, ?, ?, ?, ?)
                """,
                (draft_id, run.pass_number, run.band_value, run.rationale, run.temperature),
            )
        conn.execute(
            "INSERT INTO scoring_summary (draft_id, final_band, confidence, used_moderator) VALUES (?, ?, ?, ?)",
            (draft_id, summary.final_band, summary.confidence, int(summary.used_moderator)),
        )

        band_delta = compute_band_delta(summary.final_band, case["known_band"])
        result_cur = conn.execute(
            """
            INSERT INTO benchmark_results (benchmark_case_id, predicted_band, predicted_confidence, band_delta)
            VALUES (?, ?, ?, ?)
            """,
            (case_id, summary.final_band, summary.confidence, band_delta),
        )
        row = conn.execute("SELECT * FROM benchmark_results WHERE id = ?", (result_cur.lastrowid,)).fetchone()

    return dict(row)


@router.get("/benchmark/cases/{case_id}/results", response_model=List[BenchmarkResultOut])
def get_case_results(case_id: int):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM benchmark_results WHERE benchmark_case_id = ? ORDER BY id", (case_id,)
        ).fetchall()
    return [dict(r) for r in rows]
