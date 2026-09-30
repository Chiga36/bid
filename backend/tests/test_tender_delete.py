"""Unit tests for DELETE /tenders/{id} (app.routers.tenders.delete_tender). Uses a real, isolated
temp SQLite DB (same pattern as test_prompt_overrides.py) rather than mocking SQL, since the whole
point is proving the cascade actually succeeds against the real schema's foreign-key graph in the
right order — a wrong order would raise sqlite3.IntegrityError, not silently do the wrong thing,
so "no exception + every row gone" is a meaningful assertion here, not a formality.

vector_store.delete_tender_evidence and the on-disk tender folder are exercised through the real
function/path but never touch a real Chroma collection or need real files to exist — the function
early-returns on an empty/nonexistent collection and the folder delete is a no-op if the folder
was never created, so nothing here needs mocking to stay safe."""
import pytest

from app.config import settings
from app.db import db_session, init_db
from app.routers.tenders import delete_tender

_ALL_TENDER_SCOPED_TABLES = [
    "documents",
    "scoring_bands",
    "prompt_overrides",
    "business_rules",
    "evaluation_methodology",
    "evidence_chunks",
    "tender_requirements",
    "procurement_stages",
    "kyc_insights",
    "clarifications",
    "benchmark_cases",
    "questions",
]


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test_delete.db"))
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    init_db()
    yield


def _seed_full_tender(conn, tender_id: int, name: str) -> None:
    conn.execute("INSERT INTO tenders (id, competition_name) VALUES (?, ?)", (tender_id, name))
    conn.execute(
        "INSERT INTO documents (tender_id, file_path, original_filename) VALUES (?, 'p', 'f.docx')", (tender_id,)
    )
    q_cur = conn.execute(
        "INSERT INTO questions (tender_id, title, question_text, category) VALUES (?, 'Q', 'text', 'scored')",
        (tender_id,),
    )
    question_id = q_cur.lastrowid
    el_cur = conn.execute(
        "INSERT INTO elements (question_id, kind, value_text, extraction_method) VALUES (?, 'sub_question', 'v', 'llm')",
        (question_id,),
    )
    element_id = el_cur.lastrowid
    d_cur = conn.execute(
        "INSERT INTO drafts (question_id, version_number, content_text) VALUES (?, 1, 'draft text')", (question_id,)
    )
    draft_id = d_cur.lastrowid
    conn.execute(
        "INSERT INTO completeness_results (draft_id, element_id, status, verified) VALUES (?, ?, 'addressed', 1)",
        (draft_id, element_id),
    )
    conn.execute(
        "INSERT INTO recommendations (draft_id, rank, element_id, fix_summary) VALUES (?, 1, ?, 'fix')",
        (draft_id, element_id),
    )
    conn.execute(
        """
        INSERT INTO theme_reviews (
            draft_id, theme, theme_fit, evaluator_summary, strengths, gaps, prioritised_improvements,
            suggested_wording, evidence_required, improved_answer_plan,
            score_compliance, score_practicality, score_evidence, score_client_specificity, score_evaluator_confidence
        ) VALUES (?, 'Theme', 'fit', 'summary', '[]', '[]', '[]', '[]', '[]', 'plan', 3, 3, 3, 3, 3)
        """,
        (draft_id,),
    )
    conn.execute(
        "INSERT INTO deterministic_check_results (draft_id, check_type, passed) VALUES (?, 'word_count', 1)",
        (draft_id,),
    )
    conn.execute(
        "INSERT INTO scoring_runs (draft_id, pass_number, band_value) VALUES (?, '1', 75)", (draft_id,)
    )
    conn.execute(
        "INSERT INTO scoring_summary (draft_id, final_band, confidence) VALUES (?, 75, 'high')", (draft_id,)
    )
    bc_cur = conn.execute(
        "INSERT INTO benchmark_cases (tender_id, question_id, historical_draft_text, known_band) VALUES (?, ?, 'hist', 50)",
        (tender_id, question_id),
    )
    benchmark_case_id = bc_cur.lastrowid
    conn.execute(
        "INSERT INTO benchmark_results (benchmark_case_id, predicted_band, predicted_confidence, band_delta) "
        "VALUES (?, 50, 'high', 0)",
        (benchmark_case_id,),
    )
    conn.execute(
        "INSERT INTO clarifications (tender_id, question_id, content_text, version_number) VALUES (?, ?, 'c', 1)",
        (tender_id, question_id),
    )
    conn.execute("INSERT INTO scoring_bands (tender_id, band_value, descriptor_text) VALUES (?, 50, 'd')", (tender_id,))
    conn.execute(
        "INSERT INTO prompt_overrides (tender_id, prompt_file, content_text) VALUES (?, 'x.txt', 'y')", (tender_id,)
    )
    conn.execute(
        "INSERT INTO business_rules (tender_id, rule_key, rule_value) VALUES (?, 'k', 'v')", (tender_id,)
    )
    conn.execute(
        "INSERT INTO evaluation_methodology (tender_id, source_document, content_text) VALUES (?, 'f', 'm')",
        (tender_id,),
    )
    conn.execute(
        "INSERT INTO evidence_chunks (tender_id, source_document, chunk_text) VALUES (?, 'f', 'c')", (tender_id,)
    )
    conn.execute(
        "INSERT INTO tender_requirements (tender_id, source_document, category, requirement_text, strength) "
        "VALUES (?, 'f', 'cat', 'req', 'mandatory')",
        (tender_id,),
    )
    conn.execute(
        "INSERT INTO procurement_stages (tender_id, source_document, stage_name, stage_date) VALUES (?, 'f', 's', 'd')",
        (tender_id,),
    )
    conn.execute(
        "INSERT INTO kyc_insights (tender_id, source_document, key_facts, considerations) VALUES (?, 'f', '[]', '[]')",
        (tender_id,),
    )


def test_delete_tender_removes_every_dependent_row_without_fk_errors(monkeypatch):
    monkeypatch.setattr("app.routers.tenders.vector_store.delete_tender_evidence", lambda tid: None)

    with db_session() as conn:
        _seed_full_tender(conn, 1, "Tender One")

    delete_tender(1)  # must not raise sqlite3.IntegrityError

    with db_session() as conn:
        assert conn.execute("SELECT * FROM tenders WHERE id = 1").fetchone() is None
        assert conn.execute("SELECT * FROM elements").fetchone() is None
        assert conn.execute("SELECT * FROM drafts").fetchone() is None
        assert conn.execute("SELECT * FROM completeness_results").fetchone() is None
        assert conn.execute("SELECT * FROM recommendations").fetchone() is None
        assert conn.execute("SELECT * FROM theme_reviews").fetchone() is None
        assert conn.execute("SELECT * FROM deterministic_check_results").fetchone() is None
        assert conn.execute("SELECT * FROM scoring_runs").fetchone() is None
        assert conn.execute("SELECT * FROM scoring_summary").fetchone() is None
        assert conn.execute("SELECT * FROM benchmark_results").fetchone() is None
        for table in _ALL_TENDER_SCOPED_TABLES:
            assert conn.execute(f"SELECT * FROM {table} WHERE tender_id = 1").fetchone() is None, table


def test_delete_tender_does_not_touch_another_tenders_data(monkeypatch):
    monkeypatch.setattr("app.routers.tenders.vector_store.delete_tender_evidence", lambda tid: None)

    with db_session() as conn:
        _seed_full_tender(conn, 1, "Tender One")
        _seed_full_tender(conn, 2, "Tender Two")

    delete_tender(1)

    with db_session() as conn:
        assert conn.execute("SELECT * FROM tenders WHERE id = 2").fetchone() is not None
        for table in _ALL_TENDER_SCOPED_TABLES:
            assert conn.execute(f"SELECT * FROM {table} WHERE tender_id = 2").fetchone() is not None, table


def test_delete_tender_404s_for_unknown_tender():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        delete_tender(999)
    assert exc_info.value.status_code == 404


def test_delete_tender_never_touches_global_evidence(monkeypatch):
    monkeypatch.setattr("app.routers.tenders.vector_store.delete_tender_evidence", lambda tid: None)

    with db_session() as conn:
        _seed_full_tender(conn, 1, "Tender One")
        conn.execute(
            "INSERT INTO global_evidence_chunks (source_document, category, chunk_text, chroma_chunk_id) "
            "VALUES ('g.pdf', 'credentials', 'text', 'gev-1')"
        )

    delete_tender(1)

    with db_session() as conn:
        assert conn.execute("SELECT * FROM global_evidence_chunks").fetchone() is not None
