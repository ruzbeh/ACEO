"""DatabaseManager module — connection lifecycle, WAL pragma, and schema bootstrap.

Connection string is read from the DB_URL environment variable and defaults to
'sqlite:///bug_analysis.db'.  Only the sqlite scheme is implemented; a
postgresql scheme raises NotImplementedError as a forward-compatibility stub.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator


def get_db_url() -> str:
    """Return the database URL from DB_URL env var (default: sqlite:///bug_analysis.db)."""
    return os.environ.get("DB_URL", "sqlite:///bug_analysis.db")


def _parse_sqlite_path(db_url: str) -> str:
    """Extract the filesystem path from a sqlite:/// URL.

    Supports both relative (sqlite:///relative/path.db) and absolute
    (sqlite:////abs/path.db) forms.
    """
    # sqlite:/// prefix is 10 characters
    return db_url[len("sqlite:///"):]


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a sqlite3.Connection with WAL mode enabled.

    Usage::

        with get_connection() as conn:
            conn.execute("SELECT 1")

    Raises:
        NotImplementedError: If DB_URL scheme is not 'sqlite'.
    """
    db_url = get_db_url()

    if db_url.startswith("sqlite:///"):
        db_path = _parse_sqlite_path(db_url)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Enable WAL mode to prevent 'database is locked' under concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()
    elif db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        raise NotImplementedError(
            "PostgreSQL support is not yet implemented. "
            "Set DB_URL to a sqlite:/// connection string, "
            "or implement the PostgreSQL path in db.py."
        )
    else:
        raise NotImplementedError(
            f"Unsupported DB_URL scheme in '{db_url}'. "
            "Only 'sqlite:///' is currently supported."
        )


def init_schema() -> None:
    """Create analysis_runs and bug_findings tables if they do not already exist.

    All CREATE statements are idempotent (IF NOT EXISTS).  Also creates an
    index on bug_findings(file_path, category, created_at) to support the
    /trends query efficiently.
    """
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                analysis_id           TEXT PRIMARY KEY,
                directory             TEXT NOT NULL,
                analysis_types        TEXT NOT NULL,
                total_files_analyzed  INTEGER NOT NULL DEFAULT 0,
                total_findings        INTEGER NOT NULL DEFAULT 0,
                critical_issues       INTEGER NOT NULL DEFAULT 0,
                high_issues           INTEGER NOT NULL DEFAULT 0,
                medium_issues         INTEGER NOT NULL DEFAULT 0,
                low_issues            INTEGER NOT NULL DEFAULT 0,
                info_issues           INTEGER NOT NULL DEFAULT 0,
                analysis_time         REAL    NOT NULL DEFAULT 0.0,
                summary               TEXT    NOT NULL DEFAULT '',
                created_at            TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bug_findings (
                id            TEXT    PRIMARY KEY,
                analysis_id   TEXT    NOT NULL REFERENCES analysis_runs(analysis_id),
                file_path     TEXT    NOT NULL,
                line_number   INTEGER NOT NULL,
                column_number INTEGER NOT NULL DEFAULT 0,
                severity      TEXT    NOT NULL,
                category      TEXT    NOT NULL,
                message       TEXT    NOT NULL,
                code_snippet  TEXT    NOT NULL DEFAULT '',
                detector      TEXT    NOT NULL,
                confidence    REAL    NOT NULL DEFAULT 0.0,
                created_at    TEXT    NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_bug_findings_trends
                ON bug_findings (file_path, category, created_at);
        """)

        # created_at lives on analysis_runs; the index above references it via
        # a join in /trends queries.  Add a dedicated index on analysis_runs
        # so date-range filtering is fast too.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at "
            "ON analysis_runs (created_at)"
        )
        conn.commit()
