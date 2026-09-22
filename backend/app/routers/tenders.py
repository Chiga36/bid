"""Tenders, scoring bands, document upload, and question listing.

Document upload reads the file with app/document_extraction.py (plain text extraction, no
AI/ML) and then runs the real Ingestion agent (app/agents/ingestion.py) over its text to
identify questions — use POST /questions to add or fix entries by hand if a document still
doesn't split as expected.
"""
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile

from app.agents.ingestion import extract_questions
from app.config import settings
from app.db import db_session
from app.document_extraction import exclude_sheets, read_document
from app.models import QuestionOut, ScoringBandIn, TenderCreate, TenderOut

router = APIRouter(tags=["tenders"])

# The "Questionnaire" upload category is the Award Questionnaire only — the Selection
# Questionnaire sheet is dropped before the Ingestion agent ever sees it, so it cannot end up
# extracting questions from it (it never sees that text at all).
_EXCLUDED_SHEET_PATTERNS = ["selection questionnaire"]


@router.post("/tenders", response_model=TenderOut)
def create_tender(tender: TenderCreate):
    """Idempotent by name (case-insensitive): creating a tender whose competition_name already
    exists returns the *existing* row instead of a new, isolated one. Without this, retyping the
    same tender name on a fresh launch — or just by habit — silently forked the evidence library
    and question set in two, since every tender is otherwise fully isolated by design."""
    with db_session() as conn:
        existing = conn.execute(
            "SELECT * FROM tenders WHERE lower(competition_name) = lower(?)", (tender.competition_name,)
        ).fetchone()
        if existing is not None:
            return dict(existing)

        cur = conn.execute(
            """
            INSERT INTO tenders (competition_name, contract_reference, purchasing_authority, procedure_type)
            VALUES (?, ?, ?, ?)
            """,
            (tender.competition_name, tender.contract_reference, tender.purchasing_authority, tender.procedure_type),
        )
        row = conn.execute("SELECT * FROM tenders WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.get("/tenders", response_model=List[TenderOut])
def list_tenders():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM tenders ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@router.get("/tenders/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: int):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return dict(row)


@router.post("/tenders/{tender_id}/scoring-bands")
def set_scoring_bands(tender_id: int, bands: List[ScoringBandIn]):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        conn.execute("DELETE FROM scoring_bands WHERE tender_id = ?", (tender_id,))
        for band in bands:
            conn.execute(
                "INSERT INTO scoring_bands (tender_id, band_value, descriptor_text) VALUES (?, ?, ?)",
                (tender_id, band.band_value, band.descriptor_text),
            )
    return {"tender_id": tender_id, "bands_set": len(bands)}


@router.get("/tenders/{tender_id}/scoring-bands", response_model=List[ScoringBandIn])
def get_scoring_bands(tender_id: int):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        rows = conn.execute(
            "SELECT band_value, descriptor_text FROM scoring_bands WHERE tender_id = ? ORDER BY band_value",
            (tender_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/tenders/{tender_id}/documents", response_model=List[QuestionOut])
async def upload_document(tender_id: int, file: UploadFile):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")

    tender_dir: Path = settings.data_dir / "tenders" / str(tender_id)
    tender_dir.mkdir(parents=True, exist_ok=True)
    dest_path = tender_dir / file.filename
    contents = await file.read()
    dest_path.write_bytes(contents)

    parsed = read_document(dest_path)
    document_text = exclude_sheets(parsed.full_text, _EXCLUDED_SHEET_PATTERNS)
    candidates = extract_questions(document_text)

    created: List[dict] = []
    with db_session() as conn:
        doc_cur = conn.execute(
            "INSERT INTO documents (tender_id, file_path, original_filename) VALUES (?, ?, ?)",
            (tender_id, str(dest_path), file.filename),
        )
        document_id = doc_cur.lastrowid

        for candidate in candidates:
            q_cur = conn.execute(
                """
                INSERT INTO questions (tender_id, title, question_text, category, source_ref)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tender_id,
                    candidate.title,
                    candidate.question_text,
                    candidate.category,
                    f"document:{document_id}",
                ),
            )
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (q_cur.lastrowid,)).fetchone()
            created.append(dict(row))

    return created


@router.post("/tenders/{tender_id}/questions", response_model=QuestionOut)
def add_question_manually(tender_id: int, title: str, question_text: str, category: str, source_ref: str = None):
    if category not in ("sq", "pass_fail", "scored"):
        raise HTTPException(status_code=400, detail="category must be one of: sq, pass_fail, scored")
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        cur = conn.execute(
            "INSERT INTO questions (tender_id, title, question_text, category, source_ref) VALUES (?, ?, ?, ?, ?)",
            (tender_id, title, question_text, category, source_ref),
        )
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.get("/tenders/{tender_id}/questions", response_model=List[QuestionOut])
def list_questions(tender_id: int):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM questions WHERE tender_id = ? ORDER BY id", (tender_id,)).fetchall()
    return [dict(r) for r in rows]
