"""SQLite connection helper. One file database, no server process, travels with the project folder."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Creates all tables if they don't exist yet. Safe to call on every startup."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
        _migrate_constraint_kind_to_sub_question(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_constraint_kind_to_sub_question(conn: sqlite3.Connection) -> None:
    """One-time, defensive migration: CREATE TABLE IF NOT EXISTS is a no-op against an
    already-materialized `elements` table, so a database created before the 'constraint' ->
    'sub_question' rename would keep its old CHECK constraint forever (rejecting every future
    'sub_question' insert) unless the table is actually rebuilt. Detects the old constraint via
    sqlite_master's stored CREATE TABLE text, and if found, rebuilds the table under the current
    schema and copies every row across, remapping kind='constraint' -> 'sub_question'. Safe to
    run on every startup — it's a no-op once the table is already current."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'elements'"
    ).fetchone()
    if row is None or "'constraint'" not in row["sql"]:
        return

    # legacy_alter_table=ON stops SQLite from rewriting other tables' REFERENCES elements(id)
    # clauses to point at the temporary renamed table — without it, completeness_results'/
    # clarifications' foreign keys would end up pointing at a table we're about to drop.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("ALTER TABLE elements RENAME TO elements_pre_sub_question_rename")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO elements (
                id, question_id, kind, value_text, source_quote, extraction_method, locked, created_at
            )
            SELECT
                id, question_id,
                CASE WHEN kind = 'constraint' THEN 'sub_question' ELSE kind END,
                value_text, source_quote, extraction_method, locked, created_at
            FROM elements_pre_sub_question_rename
            """
        )
        conn.execute("DROP TABLE elements_pre_sub_question_rename")
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")


@contextmanager
def db_session():
    """Yields a connection, commits on success, rolls back on error, always closes."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
