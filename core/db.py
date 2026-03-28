import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "juldyz.db"
DB_PATH.parent.mkdir(exist_ok=True)

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS candidates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id         TEXT UNIQUE,
            name          TEXT,
            form_data     TEXT DEFAULT '{}',
            bot_data      TEXT DEFAULT '{}',
            external_data TEXT DEFAULT '{}',
            status        TEXT DEFAULT 'new',
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS scores (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id  INTEGER UNIQUE REFERENCES candidates(id),
            motivation    REAL DEFAULT 0,
            experience    REAL DEFAULT 0,
            leadership    REAL DEFAULT 0,
            growth        REAL DEFAULT 0,
            total         REAL DEFAULT 0,
            ai_suspicion  TEXT DEFAULT 'unknown',
            explanation   TEXT DEFAULT '{}',
            scored_at     TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id  INTEGER REFERENCES candidates(id),
            action        TEXT,
            old_score     REAL,
            new_score     REAL,
            note          TEXT,
            changed_by    TEXT DEFAULT 'system',
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS form_submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id  INTEGER REFERENCES candidates(id),
            raw_payload   TEXT,
            received_at   TEXT DEFAULT (datetime('now'))
        );
        """)