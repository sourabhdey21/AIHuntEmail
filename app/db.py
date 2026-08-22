import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DB_PATH
from app.roles import DEFAULT_HEADLINE, DEFAULT_PITCH, DEFAULT_SKILLS, DEFAULT_WATCH_KEYWORDS


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT NOT NULL DEFAULT '',
                headline TEXT NOT NULL DEFAULT '',
                skills TEXT NOT NULL DEFAULT '',
                pitch TEXT NOT NULL DEFAULT '',
                resume_path TEXT NOT NULL DEFAULT '',
                resume_name TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                recruiter_name TEXT NOT NULL DEFAULT '',
                recruiter_email TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                UNIQUE(source, external_id)
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                error TEXT NOT NULL DEFAULT '',
                sent_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS watchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keywords TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        existing = conn.execute("SELECT id FROM profile WHERE id = 1").fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO profile (id, full_name, headline, skills, pitch, updated_at)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (
                    "Sourabh Dey",
                    DEFAULT_HEADLINE,
                    DEFAULT_SKILLS,
                    DEFAULT_PITCH,
                    utc_now(),
                ),
            )
        else:
            current = conn.execute("SELECT headline FROM profile WHERE id = 1").fetchone()
            if current and current["headline"] == "Software engineer looking for the next role":
                conn.execute(
                    """
                    UPDATE profile
                    SET headline = ?, skills = ?, pitch = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (DEFAULT_HEADLINE, DEFAULT_SKILLS, DEFAULT_PITCH, utc_now()),
                )

        watcher = conn.execute("SELECT id FROM watchers LIMIT 1").fetchone()
        if not watcher:
            conn.execute(
                """
                INSERT INTO watchers (keywords, location, active, created_at)
                VALUES (?, 'remote', 1, ?)
                """,
                (DEFAULT_WATCH_KEYWORDS, utc_now()),
            )


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
