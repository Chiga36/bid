"""Evidence library ingestion for the Recommendation agent. Reads an uploaded case
study/CV/credential document with app/document_extraction.py (plain text extraction, no AI/ML),
chunks it at paragraph level, and embeds each chunk into the tender-scoped Chroma collection —
this tender's evidence, never another's (see app/vector_store.py's hard tender_id filter)."""
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app import vector_store
from app.agents.methodology import extract_methodology
from app.agents.procurement_timeline import extract_procurement_stages
from app.agents.scoring_matrix import extract_scoring_bands
from app.agents.tender_requirements import extract_requirements
from app.config import settings
from app.db import db_session
from app.document_extraction import read_document

router = APIRouter(tags=["evidence"])

_MIN_CHUNK_CHARS = 40
_METHODOLOGY_CATEGORY = "strategy_and_context"


@router.post("/tenders/{tender_id}/evidence")
async def upload_evidence(tender_id: int, file: UploadFile, category: str = Form(default="general")):
    """`category` is a UI grouping label only (see app/schema.sql) — it never scopes retrieval,
    which stays tender-wide by design."""
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")

    evidence_dir: Path = settings.data_dir / "tenders" / str(tender_id) / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    dest_path = evidence_dir / file.filename
    dest_path.write_bytes(await file.read())

    parsed = read_document(dest_path)
    chunk_texts = [p for p in parsed.paragraphs if len(p) >= _MIN_CHUNK_CHARS]

    chunk_ids = [f"ev-{uuid.uuid4().hex}" for _ in chunk_texts]
    vector_store.add_evidence(tender_id, chunk_ids, chunk_texts, source_document=file.filename)

    with db_session() as conn:
        for text in chunk_texts:
            conn.execute(
                "INSERT INTO evidence_chunks (tender_id, source_document, category, chunk_text) VALUES (?, ?, ?, ?)",
                (tender_id, file.filename, category, text),
            )

    methodology_extracted = False
    requirements_extracted = 0
    scoring_bands_extracted = 0
    procurement_stages_extracted = 0
    if category == _METHODOLOGY_CATEGORY:
        # Best-effort: a failure here (including missing Azure credentials) must never break
        # evidence upload, which otherwise works with no Azure configuration at all since
        # Chroma's embedding is local.
        try:
            summary = extract_methodology(parsed.full_text)
            if summary:
                with db_session() as conn:
                    conn.execute(
                        "INSERT INTO evaluation_methodology (tender_id, source_document, content_text) VALUES (?, ?, ?)",
                        (tender_id, file.filename, summary),
                    )
                methodology_extracted = True
        except Exception:
            pass

        try:
            requirements = extract_requirements(parsed.full_text)
            if requirements:
                with db_session() as conn:
                    for req in requirements:
                        conn.execute(
                            "INSERT INTO tender_requirements (tender_id, source_document, category, requirement_text, strength) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (tender_id, file.filename, req.category, req.requirement_text, req.strength),
                        )
                req_chunk_ids = [f"tr-{uuid.uuid4().hex}" for _ in requirements]
                req_chunk_texts = [req.requirement_text for req in requirements]
                vector_store.add_tender_requirements(tender_id, req_chunk_ids, req_chunk_texts, source_document=file.filename)
                requirements_extracted = len(requirements)
        except Exception:
            pass

        try:
            bands = extract_scoring_bands(parsed.tables)
            if bands:
                with db_session() as conn:
                    # Same replace semantics as the manual POST /tenders/{id}/scoring-bands
                    # endpoint (routers/tenders.py) — a later corrected re-upload supersedes the
                    # old bands, whether they were set by hand or by extraction.
                    conn.execute("DELETE FROM scoring_bands WHERE tender_id = ?", (tender_id,))
                    for band in bands:
                        conn.execute(
                            "INSERT INTO scoring_bands (tender_id, band_value, descriptor_text) VALUES (?, ?, ?)",
                            (tender_id, band.band_value, band.descriptor_text),
                        )
                scoring_bands_extracted = len(bands)
        except Exception:
            pass

        try:
            stages = extract_procurement_stages(parsed.tables, parsed.full_text)
            if stages:
                with db_session() as conn:
                    for stage in stages:
                        conn.execute(
                            "INSERT INTO procurement_stages (tender_id, source_document, stage_name, stage_date) "
                            "VALUES (?, ?, ?, ?)",
                            (tender_id, file.filename, stage.stage_name, stage.stage_date),
                        )
                procurement_stages_extracted = len(stages)
        except Exception:
            pass

    return {
        "tender_id": tender_id,
        "source_document": file.filename,
        "category": category,
        "chunks_ingested": len(chunk_texts),
        "methodology_extracted": methodology_extracted,
        "requirements_extracted": requirements_extracted,
        "scoring_bands_extracted": scoring_bands_extracted,
        "procurement_stages_extracted": procurement_stages_extracted,
    }


@router.get("/tenders/{tender_id}/evidence")
def list_evidence(tender_id: int) -> List[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, source_document, category, chunk_text, created_at FROM evidence_chunks WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/tenders/{tender_id}/procurement-stages")
def list_procurement_stages(tender_id: int) -> List[dict]:
    """Raw rows, in extraction order — unlike Tender Requirements (only ever consumed via Chroma
    retrieval), this is displayed as-is in Competition Info, so it needs its own listing
    endpoint rather than just a vector_store query function."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, source_document, stage_name, stage_date, created_at FROM procurement_stages "
            "WHERE tender_id = ? ORDER BY id",
            (tender_id,),
        ).fetchall()
    return [dict(r) for r in rows]
