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
    finally:
        conn.close()


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
