"""Cross-tender evidence library. Not scoped to any tender — a case study, CV, or high-scoring
response uploaded here is picked up automatically by every tender's Recommendation agent and
Decomposition's evidence_suggestion, via vector_store.query_evidence's merge with the
_GLOBAL_TENDER_ID sentinel, so a bid team never has to re-upload the same evidence for every bid
they write.

Same category vocabulary as the per-tender evidence categories (see DataIngestion's
OPTIONAL_CATEGORIES) so the two feel like the same kind of thing to a user, just at a different
scope.
"""
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app import vector_store
from app.config import settings
from app.db import db_session
from app.document_extraction import read_document
from app.models import GlobalEvidenceChunkOut, GlobalEvidenceUploadOut

router = APIRouter(tags=["evidence-library"])

_MIN_CHUNK_CHARS = 40


@router.post("/evidence-library", response_model=GlobalEvidenceUploadOut)
async def upload_global_evidence(file: UploadFile, category: str = Form(default="general")):
    evidence_dir: Path = settings.data_dir / "global_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    dest_path = evidence_dir / file.filename
    dest_path.write_bytes(await file.read())

    parsed = read_document(dest_path)
    chunk_texts = [p for p in parsed.paragraphs if len(p) >= _MIN_CHUNK_CHARS]
    chunk_ids = [f"gev-{uuid.uuid4().hex}" for _ in chunk_texts]

    vector_store.add_global_evidence(chunk_ids, chunk_texts, source_document=file.filename)

    with db_session() as conn:
        for chunk_id, text in zip(chunk_ids, chunk_texts):
            conn.execute(
                "INSERT INTO global_evidence_chunks (source_document, category, chunk_text, chroma_chunk_id) "
                "VALUES (?, ?, ?, ?)",
                (file.filename, category, text, chunk_id),
            )

    return GlobalEvidenceUploadOut(source_document=file.filename, category=category, chunks_ingested=len(chunk_texts))


@router.get("/evidence-library", response_model=List[GlobalEvidenceChunkOut])
def list_global_evidence():
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, source_document, category, chunk_text, created_at FROM global_evidence_chunks ORDER BY id"
        ).fetchall()
    return [GlobalEvidenceChunkOut(**dict(r)) for r in rows]


@router.delete("/evidence-library/document/{source_document}")
def delete_global_evidence_document(source_document: str):
    """Deletes every chunk belonging to one uploaded document — a user thinks in terms of "remove
    this case study", not individual paragraph chunks, so deletion is document-scoped."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, chroma_chunk_id FROM global_evidence_chunks WHERE source_document = ?",
            (source_document,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No global evidence found for that document")
        conn.execute("DELETE FROM global_evidence_chunks WHERE source_document = ?", (source_document,))

    vector_store.delete_chunks([r["chroma_chunk_id"] for r in rows])
    return {"source_document": source_document, "chunks_deleted": len(rows)}
