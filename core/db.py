import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "juldyz.db"
DB_PATH.parent.mkdir(exist_ok=True)


class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id         TEXT UNIQUE,
                full_name     TEXT DEFAULT '{}',
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

    # --- candidates ---

    def upsert_candidate(self, tg_id: str, full_name: str = None) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM candidates WHERE tg_id=?", (tg_id,)
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO candidates (tg_id, full_name) VALUES (?,?)",
                (tg_id, full_name)
            )
            return cur.lastrowid

    def get_candidate_by_tg(self, tg_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidates WHERE tg_id=?", (tg_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_candidates(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, tg_id, name, status, created_at FROM candidates ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def set_form_data(self, candidate_id: int, payload: dict):
        full_name = payload.get("Ваше имя", None)
        with self._connect() as conn:
            conn.execute(
                """UPDATE candidates 
                SET form_data=?, status='form_submitted', full_name=COALESCE(?,full_name)
                WHERE id=?""",
                (json.dumps(payload, ensure_ascii=False), full_name, candidate_id)
            )
            conn.execute(
                "INSERT INTO form_submissions (candidate_id, raw_payload) VALUES (?,?)",
                (candidate_id, json.dumps(payload, ensure_ascii=False))
            )

    def set_bot_data(self, candidate_id: int, data: dict):
        with self._connect() as conn:
            conn.execute(
                "UPDATE candidates SET bot_data=?, status='interviewed' WHERE id=?",
                (json.dumps(data, ensure_ascii=False), candidate_id)
            )

    def set_external_data(self, candidate_id: int, data: dict):
        with self._connect() as conn:
            conn.execute(
                "UPDATE candidates SET external_data=? WHERE id=?",
                (json.dumps(data, ensure_ascii=False), candidate_id)
            )

    # --- scores ---

    def save_score(self, candidate_id: int, scores: dict, explanation: dict, ai_suspicion: str):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO scores (candidate_id, motivation, experience, leadership, growth, total, ai_suspicion, explanation)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    motivation=excluded.motivation,
                    experience=excluded.experience,
                    leadership=excluded.leadership,
                    growth=excluded.growth,
                    total=excluded.total,
                    ai_suspicion=excluded.ai_suspicion,
                    explanation=excluded.explanation,
                    scored_at=datetime('now')
            """, (
                candidate_id,
                scores["motivation"], scores["experience"],
                scores["leadership"], scores["growth"], scores["total"],
                ai_suspicion,
                json.dumps(explanation, ensure_ascii=False)
            ))
            conn.execute(
                "INSERT INTO audit_log (candidate_id, action, new_score) VALUES (?,?,?)",
                (candidate_id, "auto_score", scores["total"])
            )

    def manual_override(self, candidate_id: int, new_total: float, note: str, changed_by: str):
        with self._connect() as conn:
            old = conn.execute(
                "SELECT total FROM scores WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
            conn.execute(
                "UPDATE scores SET total=? WHERE candidate_id=?",
                (new_total, candidate_id)
            )
            conn.execute("""
                INSERT INTO audit_log (candidate_id, action, old_score, new_score, note, changed_by)
                VALUES (?,?,?,?,?,?)
            """, (candidate_id, "manual_override", old["total"] if old else None, new_total, note, changed_by))

    def get_shortlist(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT c.id, c.tg_id, c.name, c.status,
                       s.total, s.motivation, s.experience, s.leadership, s.growth,
                       s.ai_suspicion, s.explanation, s.scored_at
                FROM candidates c
                JOIN scores s ON s.candidate_id = c.id
                ORDER BY s.total DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


db = Database()