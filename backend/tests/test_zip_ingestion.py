"""Unit tests for routers/zip_ingestion.py. _ingest_document_bytes / _ingest_evidence_bytes are
monkeypatched out — this file tests the ZIP-handling logic itself (extraction, classification,
staging, cleanup, skip-on-null-assignment, error cases), not the downstream agent pipelines those
functions call into (already covered by their own dedicated test files)."""
import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.db import db_session, init_db
from app.routers import zip_ingestion


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test_zip.db"))
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    init_db()
    with db_session() as conn:
        conn.execute("INSERT INTO tenders (id, competition_name) VALUES (1, 'Test Tender')")
    yield


def _make_zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _upload_file(zip_bytes: bytes, filename: str = "pack.zip") -> UploadFile:
    return UploadFile(file=io.BytesIO(zip_bytes), filename=filename)


def test_inspect_classifies_and_stages_supported_files():
    zip_bytes = _make_zip(
        {
            "docs/SR2_Award_Questionnaire.xlsx": b"questionnaire bytes",
            "Evaluation Criteria.docx": b"strategy bytes",
            "cover.jpg": b"not a supported type",  # must be silently skipped
        }
    )
    result = asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))

    names = {f.filename: f.suggested_category for f in result.files}
    assert names == {
        "SR2_Award_Questionnaire.xlsx": "competition_info",
        "Evaluation Criteria.docx": "strategy",
    }
    staging_dir = zip_ingestion._staging_dir(1, result.staging_id)
    assert (staging_dir / "SR2_Award_Questionnaire.xlsx").read_bytes() == b"questionnaire bytes"
    assert not (staging_dir / "cover.jpg").exists()


def test_inspect_dedupes_colliding_basenames_across_folders():
    zip_bytes = _make_zip({"a/strategy.docx": b"first", "b/strategy.docx": b"second"})
    result = asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))
    filenames = sorted(f.filename for f in result.files)
    assert filenames == ["strategy (1).docx", "strategy.docx"]


def test_inspect_rejects_invalid_zip():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(b"not a real zip")))
    assert exc_info.value.status_code == 400


def test_inspect_rejects_zip_with_no_supported_files():
    zip_bytes = _make_zip({"readme.txt": b"hello", "photo.jpg": b"img"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))
    assert exc_info.value.status_code == 400


def test_commit_routes_questionnaire_to_document_ingestion_and_others_to_evidence(monkeypatch):
    document_calls = []
    evidence_calls = []
    monkeypatch.setattr(
        zip_ingestion,
        "_ingest_document_bytes",
        lambda tender_id, filename, contents: document_calls.append((tender_id, filename)) or [{"id": 1}],
    )
    monkeypatch.setattr(
        zip_ingestion,
        "_ingest_evidence_bytes",
        lambda tender_id, filename, contents, category: evidence_calls.append((tender_id, filename, category))
        or {"chunks_ingested": 3},
    )

    zip_bytes = _make_zip({"SR2_Questionnaire.xlsx": b"q", "Evaluation.docx": b"e"})
    inspected = asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))

    result = zip_ingestion.commit_zip_upload(
        1,
        inspected.staging_id,
        zip_ingestion.ZipCommitIn(
            assignments={"SR2_Questionnaire.xlsx": "competition_info", "Evaluation.docx": "strategy"}
        ),
    )

    assert document_calls == [(1, "SR2_Questionnaire.xlsx")]
    assert evidence_calls == [(1, "Evaluation.docx", "strategy")]
    assert {r.filename: r.success for r in result.results} == {"SR2_Questionnaire.xlsx": True, "Evaluation.docx": True}

    # Staging directory is cleaned up after a successful commit.
    assert not zip_ingestion._staging_dir(1, inspected.staging_id).exists()


def test_commit_skips_files_assigned_null_category(monkeypatch):
    calls = []
    monkeypatch.setattr(zip_ingestion, "_ingest_evidence_bytes", lambda *a, **k: calls.append(a) or {"chunks_ingested": 1})

    zip_bytes = _make_zip({"random.pdf": b"x"})
    inspected = asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))

    result = zip_ingestion.commit_zip_upload(
        1, inspected.staging_id, zip_ingestion.ZipCommitIn(assignments={"random.pdf": None})
    )

    assert calls == []
    assert result.results == []


def test_commit_records_failure_without_losing_other_files(monkeypatch):
    def fake_ingest_evidence(tender_id, filename, contents, category):
        if filename == "bad.pdf":
            raise ValueError("Something exploded")
        return {"chunks_ingested": 2}

    monkeypatch.setattr(zip_ingestion, "_ingest_evidence_bytes", fake_ingest_evidence)

    zip_bytes = _make_zip({"bad.pdf": b"x", "good.pdf": b"y"})
    inspected = asyncio.run(zip_ingestion.inspect_zip_upload(1, _upload_file(zip_bytes)))

    result = zip_ingestion.commit_zip_upload(
        1,
        inspected.staging_id,
        zip_ingestion.ZipCommitIn(assignments={"bad.pdf": "standards", "good.pdf": "standards"}),
    )

    by_name = {r.filename: r for r in result.results}
    assert by_name["bad.pdf"].success is False
    assert "Something exploded" in by_name["bad.pdf"].message
    assert by_name["good.pdf"].success is True


def test_commit_unknown_staging_id_404s():
    with pytest.raises(HTTPException) as exc_info:
        zip_ingestion.commit_zip_upload(1, "nonexistent-staging-id", zip_ingestion.ZipCommitIn(assignments={}))
    assert exc_info.value.status_code == 404


def test_inspect_unknown_tender_404s():
    zip_bytes = _make_zip({"a.pdf": b"x"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(zip_ingestion.inspect_zip_upload(999, _upload_file(zip_bytes)))
    assert exc_info.value.status_code == 404
