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
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS telegram_users (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id         TEXT UNIQUE NOT NULL,
                username            TEXT,
                first_name          TEXT,
                last_name           TEXT,
                language_code       TEXT,
                is_bot              INTEGER DEFAULT 0,
                profile_photo_url   TEXT,
                raw                 TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS candidate_responses (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              INTEGER NOT NULL REFERENCES users(id),
                timestamp            TEXT DEFAULT (datetime('now')),
                email                TEXT,
                last_name            TEXT,
                first_name           TEXT,
                patronymic           TEXT,
                dob                  TEXT,
                citizenship          TEXT,
                iin                  TEXT,
                program_applied      TEXT,
                major                TEXT,
                personal_presentation TEXT,
                english_results      TEXT,
                social_certificate   TEXT,
                additional_info      TEXT,
                raw_payload          TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS user_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                file_id     TEXT NOT NULL,
                file_type   TEXT,
                uploaded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS user_links (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                link_url        TEXT NOT NULL,
                linked_file_id  INTEGER REFERENCES user_files(id),
                processed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS scores (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER UNIQUE REFERENCES users(id),
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
                user_id       INTEGER REFERENCES users(id),
                action        TEXT,
                old_score     REAL,
                new_score     REAL,
                note          TEXT,
                changed_by    TEXT DEFAULT 'system',
                created_at    TEXT DEFAULT (datetime('now'))
            );
            """)

    # --- users ---
    def upsert_user(self, telegram_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE telegram_id=?", (telegram_id,)
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,)
            )
            return cur.lastrowid

    def get_user_by_tg(self, telegram_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- adapter for form ---
    def get_candidate_by_tg(self, telegram_id: str) -> dict | None:
        return self.get_user_by_tg(telegram_id)

    # --- telegram_users ---
    def upsert_telegram_user(self, telegram_id: str, username: str = None,
                              first_name: str = None, last_name: str = None,
                              language_code: str = None, is_bot: bool = False,
                              profile_photo_url: str = None, raw: dict = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO telegram_users
                    (telegram_id, username, first_name, last_name, language_code, is_bot, profile_photo_url, raw)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_name=excluded.last_name,
                    language_code=excluded.language_code,
                    profile_photo_url=excluded.profile_photo_url,
                    raw=excluded.raw
            """, (
                telegram_id, username, first_name, last_name,
                language_code, int(is_bot), profile_photo_url,
                json.dumps(raw or {}, ensure_ascii=False)
            ))

    # --- candidate_responses ---
    def save_candidate_response(self, user_id: int, payload: dict) -> int:
        fields = [
            "email", "last_name", "first_name", "patronymic", "dob",
            "citizenship", "iin", "program_applied", "major",
            "personal_presentation", "english_results",
            "social_certificate", "additional_info"
        ]
        values = {f: payload.get(f) for f in fields}

        with self._connect() as conn:
            cur = conn.execute(f"""
                INSERT INTO candidate_responses
                    (user_id, email, last_name, first_name, patronymic, dob,
                     citizenship, iin, program_applied, major,
                     personal_presentation, english_results,
                     social_certificate, additional_info, raw_payload)
                VALUES
                    (:user_id, :email, :last_name, :first_name, :patronymic, :dob,
                     :citizenship, :iin, :program_applied, :major,
                     :personal_presentation, :english_results,
                     :social_certificate, :additional_info, :raw)
            """, {**values, "user_id": user_id,
                  "raw": json.dumps(payload, ensure_ascii=False)})
            return cur.lastrowid

    def get_candidate_response(self, user_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_responses WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- user_files ---
    def save_file(self, user_id: int, file_id: str, file_type: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO user_files (user_id, file_id, file_type) VALUES (?,?,?)",
                (user_id, file_id, file_type)
            )
            return cur.lastrowid

    def get_files(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_files WHERE user_id=? ORDER BY uploaded_at DESC",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- user_links ---
    def save_link(self, user_id: int, link_url: str, linked_file_id: int = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO user_links (user_id, link_url, linked_file_id) VALUES (?,?,?)",
                (user_id, link_url, linked_file_id)
            )
            return cur.lastrowid

    def mark_link_processed(self, link_id: int):
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_links SET processed_at=datetime('now') WHERE id=?",
                (link_id,)
            )

    def get_links(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_links WHERE user_id=? ORDER BY id DESC",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- scores ---
    def save_score(self, user_id: int, scores: dict, explanation: dict, ai_suspicion: str):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO scores (user_id, motivation, experience, leadership, growth, total, ai_suspicion, explanation)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    motivation=excluded.motivation,
                    experience=excluded.experience,
                    leadership=excluded.leadership,
                    growth=excluded.growth,
                    total=excluded.total,
                    ai_suspicion=excluded.ai_suspicion,
                    explanation=excluded.explanation,
                    scored_at=datetime('now')
            """, (
                user_id,
                scores["motivation"], scores["experience"],
                scores["leadership"], scores["growth"], scores["total"],
                ai_suspicion,
                json.dumps(explanation, ensure_ascii=False)
            ))
            conn.execute(
                "INSERT INTO audit_log (user_id, action, new_score) VALUES (?,?,?)",
                (user_id, "auto_score", scores["total"])
            )

    def manual_override(self, user_id: int, new_total: float, note: str, changed_by: str):
        with self._connect() as conn:
            old = conn.execute(
                "SELECT total FROM scores WHERE user_id=?", (user_id,)
            ).fetchone()
            conn.execute(
                "UPDATE scores SET total=? WHERE user_id=?",
                (new_total, user_id)
            )
            conn.execute("""
                INSERT INTO audit_log (user_id, action, old_score, new_score, note, changed_by)
                VALUES (?,?,?,?,?,?)
            """, (user_id, "manual_override",
                  old["total"] if old else None, new_total, note, changed_by))

    def get_shortlist(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT u.id, u.telegram_id, u.created_at,
                       t.username, t.first_name, t.last_name,
                       s.total, s.motivation, s.experience,
                       s.leadership, s.growth,
                       s.ai_suspicion, s.explanation, s.scored_at
                FROM users u
                JOIN scores s ON s.user_id = u.id
                LEFT JOIN telegram_users t ON t.telegram_id = u.telegram_id
                ORDER BY s.total DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


db = Database()