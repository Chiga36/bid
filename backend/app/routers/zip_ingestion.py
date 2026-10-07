"""ZIP-based Data Ingestion: upload one .zip containing a tender's whole document pack, get each
file auto-classified into a Data Ingestion category by filename (see app/zip_classification.py),
review/correct the suggestions on the frontend, then commit — which runs each file through the
exact same ingestion logic a manual single-file upload already uses
(routers/tenders.py's _ingest_document_bytes, routers/evidence.py's _ingest_evidence_bytes), so
results are identical in shape either way.

Two-step, stateless between calls except for a staging directory on disk — no new DB table. The
classification mapping round-trips through the frontend (sent back in the commit request body)
rather than being persisted anywhere.

Zip-slip safety: only the basename of each zip member is ever used to build a path (via
Path(name).name) — any directory component, including a malicious "../" prefix, is discarded
before it's ever used to construct a filesystem path, so nothing in a zip can write outside its
own staging directory.
"""
import io
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List, Set

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import settings
from app.db import db_session
from app.document_extraction import SUPPORTED_EXTENSIONS
from app.models import ZipCommitFileResult, ZipCommitIn, ZipCommitOut, ZipInspectFile, ZipInspectOut
from app.routers.evidence import _ingest_evidence_bytes
from app.routers.tenders import _ingest_document_bytes
from app.zip_classification import classify_filename

router = APIRouter(tags=["zip-ingestion"])

# The one category that routes to question extraction (_ingest_document_bytes); every other
# category routes to the evidence pipeline (_ingest_evidence_bytes) — same split DataIngestion.tsx
# already encodes via each category's `target` field.
_DOCUMENT_CATEGORY = "competition_info"


def _staging_dir(tender_id: int, staging_id: str) -> Path:
    return settings.data_dir / "tenders" / str(tender_id) / "zip_staging" / staging_id


def _require_tender(tender_id: int) -> None:
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")


def _dedupe_name(basename: str, used: Set[str]) -> str:
    """Zip entries from different folders can share a basename once folder structure is dropped
    (e.g. "docs/strategy.xlsx" and "archive/strategy.xlsx") — append "(1)", "(2)"... rather than
    silently overwriting one staged file with another."""
    if basename not in used:
        return basename
    stem, suffix = Path(basename).stem, Path(basename).suffix
    n = 1
    while f"{stem} ({n}){suffix}" in used:
        n += 1
    return f"{stem} ({n}){suffix}"


@router.post("/tenders/{tender_id}/zip-upload", response_model=ZipInspectOut)
async def inspect_zip_upload(tender_id: int, file: UploadFile):
    _require_tender(tender_id)
    contents = await file.read()

    try:
        zf = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="That file isn't a valid ZIP archive.")

    staging_id = uuid.uuid4().hex
    staging_dir = _staging_dir(tender_id, staging_id)
    staging_dir.mkdir(parents=True, exist_ok=True)

    files: List[ZipInspectFile] = []
    used_names: Set[str] = set()
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            basename = Path(info.filename).name  # discards any folder path / ".." components
            if not basename or Path(basename).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue  # unsupported file type (image, .DS_Store, a nested zip...) — skip silently

            target_name = _dedupe_name(basename, used_names)
            used_names.add(target_name)

            data = zf.read(info)
            (staging_dir / target_name).write_bytes(data)
            files.append(
                ZipInspectFile(filename=target_name, suggested_category=classify_filename(target_name), size_bytes=len(data))
            )

    if not files:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400, detail="No supported files (.docx, .xlsx, .pdf, .pptx) were found in that ZIP."
        )

    return ZipInspectOut(staging_id=staging_id, files=files)


@router.post("/tenders/{tender_id}/zip-upload/{staging_id}/commit", response_model=ZipCommitOut)
def commit_zip_upload(tender_id: int, staging_id: str, body: ZipCommitIn):
    _require_tender(tender_id)
    staging_dir = _staging_dir(tender_id, staging_id)
    if not staging_dir.is_dir():
        raise HTTPException(status_code=404, detail="This ZIP upload has expired or was already committed.")

    results: List[ZipCommitFileResult] = []
    try:
        for filename, category in body.assignments.items():
            if category is None:
                continue  # user chose "Skip this file" in the review step
            staged_path = staging_dir / filename
            if not staged_path.is_file():
                results.append(
                    ZipCommitFileResult(
                        filename=filename, category=category, success=False, message="File was not found in the staged upload."
                    )
                )
                continue

            contents = staged_path.read_bytes()
            try:
                if category == _DOCUMENT_CATEGORY:
                    questions = _ingest_document_bytes(tender_id, filename, contents)
                    message = f"{len(questions)} question(s) extracted."
                else:
                    result = _ingest_evidence_bytes(tender_id, filename, contents, category)
                    message = f"{result['chunks_ingested']} evidence chunk(s) ingested."
                results.append(ZipCommitFileResult(filename=filename, category=category, success=True, message=message))
            except Exception as exc:
                message = str(exc) or "Something went wrong."
                results.append(ZipCommitFileResult(filename=filename, category=category, success=False, message=message))
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    return ZipCommitOut(results=results)
