"""Unit tests for per-tender skill (prompt) override resolution — llm_client._resolve_template().
Uses a real, isolated temp SQLite DB (via settings.database_path monkeypatched to a tmp_path
file + init_db()) rather than mocking SQL, since the whole point is proving the actual query
against the actual schema behaves correctly. No Azure OpenAI call is made anywhere here — this
only exercises the template-resolution step, before any model call would happen."""
import pytest

from app import llm_client
from app.config import settings
from app.db import db_session, init_db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test_overrides.db"))
    init_db()
    # _resolve_template only ever reads from prompt_overrides — no need to seed a real tenders
    # row for these tests, since the foreign key check only bites on INSERT into prompt_overrides
    # itself, and every test here either doesn't insert or inserts against tender_id=1 which we
    # create below.
    with db_session() as conn:
        conn.execute("INSERT INTO tenders (id, competition_name) VALUES (1, 'Test Tender')")
    yield


def test_no_tender_id_uses_disk_default(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_prompt", lambda f: f"DEFAULT CONTENT for {f}")
    result = llm_client._resolve_template("some_prompt_v1.txt", None)
    assert result == "DEFAULT CONTENT for some_prompt_v1.txt"


def test_tender_with_no_override_falls_back_to_disk_default(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_prompt", lambda f: f"DEFAULT CONTENT for {f}")
    result = llm_client._resolve_template("some_prompt_v1.txt", tender_id=1)
    assert result == "DEFAULT CONTENT for some_prompt_v1.txt"


def test_tender_with_override_wins_over_disk_default(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_prompt", lambda f: "should never be used")
    with db_session() as conn:
        conn.execute(
            "INSERT INTO prompt_overrides (tender_id, prompt_file, content_text) VALUES (1, ?, ?)",
            ("some_prompt_v1.txt", "MY CUSTOM WORDING"),
        )
    result = llm_client._resolve_template("some_prompt_v1.txt", tender_id=1)
    assert result == "MY CUSTOM WORDING"


def test_override_is_scoped_to_its_own_tender_only(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_prompt", lambda f: f"DEFAULT CONTENT for {f}")
    with db_session() as conn:
        conn.execute("INSERT INTO tenders (id, competition_name) VALUES (2, 'Other Tender')")
        conn.execute(
            "INSERT INTO prompt_overrides (tender_id, prompt_file, content_text) VALUES (1, ?, ?)",
            ("some_prompt_v1.txt", "MY CUSTOM WORDING"),
        )
    # Tender 2 has no override of its own — must still get the default, never tender 1's.
    result = llm_client._resolve_template("some_prompt_v1.txt", tender_id=2)
    assert result == "DEFAULT CONTENT for some_prompt_v1.txt"


def test_override_resolution_reads_fresh_every_call_not_cached(monkeypatch):
    """The disk-loaded default IS cached (_prompt_cache) — the override lookup must not be, so a
    just-saved edit takes effect on the very next call without a process restart."""
    monkeypatch.setattr(llm_client, "_load_prompt", lambda f: "default")
    with db_session() as conn:
        conn.execute(
            "INSERT INTO prompt_overrides (tender_id, prompt_file, content_text) VALUES (1, ?, ?)",
            ("some_prompt_v1.txt", "first version"),
        )
    assert llm_client._resolve_template("some_prompt_v1.txt", tender_id=1) == "first version"

    with db_session() as conn:
        conn.execute(
            "UPDATE prompt_overrides SET content_text = ? WHERE tender_id = 1 AND prompt_file = ?",
            ("second version", "some_prompt_v1.txt"),
        )
    assert llm_client._resolve_template("some_prompt_v1.txt", tender_id=1) == "second version"
