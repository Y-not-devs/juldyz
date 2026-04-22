import sqlite3
import json
from pathlib import Path

from core.form_fields import get_field_value, normalize_form_payload

DB_PATH = Path(__file__).parent.parent / "data" / "juldyz.db"
DB_PATH.parent.mkdir(exist_ok=True)

STAGE_COLUMN_MAP: dict[str, tuple[str, str]] = {
    "parser": ("parser_status", "parser_error"),
    "scoring": ("scoring_status", "scoring_error"),
    "notification": ("notification_status", "notification_error"),
}

CANDIDATE_RESPONSE_REQUIRED_COLUMNS: dict[str, str] = {
    "user_id": "INTEGER NOT NULL REFERENCES users(id)",
    "timestamp": "TEXT DEFAULT (datetime('now'))",
    "email": "TEXT",
    "last_name": "TEXT",
    "first_name": "TEXT",
    "patronymic": "TEXT",
    "dob": "TEXT",
    "mobile_phone": "TEXT",
    "instagram": "TEXT",
    "telegram_handle": "TEXT",
    "whatsapp": "TEXT",
    "program_applied": "TEXT",
    "major": "TEXT",
    "personal_presentation": "TEXT",
    "english_results": "TEXT",
    "english_test_certificate": "TEXT DEFAULT ''",
    "additional_documents": "TEXT DEFAULT ''",
    "essay_failure": "TEXT",
    "essay_beta": "TEXT",
    "honors_raw": "TEXT DEFAULT '[]'",
    "activities_raw": "TEXT DEFAULT '[]'",
    "social_certificate": "TEXT DEFAULT ''",
    "additional_info": "TEXT DEFAULT '{}'",
    "processing_status": "TEXT DEFAULT 'pending'",
    "processing_error": "TEXT",
    "processing_started_at": "TEXT",
    "processed_at": "TEXT",
    "parser_status": "TEXT DEFAULT 'pending'",
    "parser_error": "TEXT",
    "scoring_status": "TEXT DEFAULT 'pending'",
    "scoring_error": "TEXT",
    "notification_status": "TEXT DEFAULT 'pending'",
    "notification_error": "TEXT",
    "raw_payload": "TEXT DEFAULT '{}'",
}


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
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id               INTEGER NOT NULL REFERENCES users(id),
                timestamp             TEXT DEFAULT (datetime('now')),

                -- identity
                email                 TEXT,
                last_name             TEXT,
                first_name            TEXT,
                patronymic            TEXT,
                dob                   TEXT,
                mobile_phone          TEXT,

                -- contacts
                instagram             TEXT,
                telegram_handle       TEXT,
                whatsapp              TEXT,

                -- application
                program_applied       TEXT,
                major                 TEXT,
                personal_presentation TEXT,
                english_results       TEXT,

                -- essays
                essay_failure         TEXT,
                essay_beta            TEXT,

                -- semi-structured (stored as JSON)
                honors_raw            TEXT DEFAULT '[]',
                activities_raw        TEXT DEFAULT '[]',

                -- full payload
                raw_payload           TEXT DEFAULT '{}'
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

            CREATE TABLE IF NOT EXISTS workflow_jobs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id   INTEGER NOT NULL UNIQUE REFERENCES candidate_responses(id),
                user_id       INTEGER NOT NULL REFERENCES users(id),
                payload_json  TEXT NOT NULL,
                status        TEXT DEFAULT 'queued',
                current_stage TEXT DEFAULT 'queued',
                attempts      INTEGER DEFAULT 0,
                max_attempts  INTEGER DEFAULT 3,
                last_error    TEXT,
                available_at  TEXT DEFAULT (datetime('now')),
                locked_at     TEXT,
                completed_at  TEXT,
                created_at    TEXT DEFAULT (datetime('now')),
                updated_at    TEXT DEFAULT (datetime('now'))
            );
            """)
            self._ensure_candidate_response_columns(conn)

    def _ensure_candidate_response_columns(self, conn: sqlite3.Connection) -> None:
        existing_columns = self._table_columns(conn, "candidate_responses")
        for column_name, column_sql in CANDIDATE_RESPONSE_REQUIRED_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE candidate_responses ADD COLUMN {column_name} {column_sql}"
                )

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _payload_first(self, payload: dict, *keys: str, default=None):
        for key in keys:
            if key in payload:
                value = payload.get(key)
                if value is not None and str(value).strip() != "":
                    return value
        return default

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

    def get_user_by_candidate_id(self, candidate_id: str | int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id=?",
                (int(candidate_id),),
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
        payload = normalize_form_payload(payload)
        honors = {
            "Honors 1 title": payload.get("Honors 1 title", ""),
            "Honors 2 title": payload.get("Honors 2 title", ""),
            "Honors 3 title": payload.get("Honors 3 title", ""),
            "Honors 4 title": payload.get("Honors 4 title", ""),
            "Honors 5 title": payload.get("Honors 5 title", ""),
            "Grade level": payload.get("Grade level", ""),
            "Level(s) of recognition": self._payload_first(
                payload,
                "Level(s) of recognition",
                "Level of recognition",
            )
            or "",
            "Do you have other honors?": payload.get("Do you have other honors?", ""),
        }
        activities = {
            "Activity type": payload.get("Activity type", ""),
            "Position/Leadership description": self._payload_first(
                payload,
                "Position/Leadership description\n(Max characters: 50)",
                "Position/Leadership description (Max characters: 50)",
            )
            or "",
            "Organization Name": self._payload_first(
                payload,
                "Organization Name\n(Max characters: 50)",
                "Organization Name (Max characters: 50)",
            )
            or "",
            "Activity description": self._payload_first(
                payload,
                "Please describe this activity, including what you accomplished and any recognition you received, etc.\n(Max characters: 120)",
                "Please describe this activity, including what you accomplished and any recognition you received, etc.\n(Max characters: 150)",
                "Please describe this activity, including what you accomplished and any recognition you received, etc. (Max characters: 120)",
                "Please describe this activity, including what you accomplished and any recognition you received, etc. (Max characters: 150)",
            )
            or "",
        }

        additional_info = {
            "mobile_phone": get_field_value(payload, "mobile_phone"),
            "instagram": get_field_value(payload, "instagram"),
            "telegram_handle": get_field_value(payload, "telegram_handle"),
            "whatsapp": get_field_value(payload, "whatsapp"),
            "english_test_certificate": get_field_value(payload, "english_test_certificate"),
            "additional_documents": get_field_value(payload, "additional_documents"),
            "essay_failure": get_field_value(payload, "essay_failure"),
            "essay_beta": get_field_value(payload, "essay_beta"),
            "honors_raw": honors,
            "activities_raw": activities,
        }

        mapped = {
            "user_id": user_id,
            "timestamp": payload.get("timestamp"),
            "email": get_field_value(payload, "email"),
            "last_name": get_field_value(payload, "last_name"),
            "first_name": get_field_value(payload, "first_name"),
            "patronymic": get_field_value(payload, "patronymic"),
            "dob": get_field_value(payload, "dob"),
            "mobile_phone": get_field_value(payload, "mobile_phone"),
            "instagram": get_field_value(payload, "instagram"),
            "telegram_handle": get_field_value(payload, "telegram_handle"),
            "whatsapp": get_field_value(payload, "whatsapp"),
            "program_applied": get_field_value(payload, "program_applied"),
            "major": get_field_value(payload, "major"),
            "personal_presentation": get_field_value(payload, "personal_presentation"),
            "english_results": get_field_value(payload, "english_results"),
            "english_test_certificate": get_field_value(payload, "english_test_certificate") or "",
            "additional_documents": get_field_value(payload, "additional_documents") or "",
            "essay_failure": get_field_value(payload, "essay_failure"),
            "essay_beta": get_field_value(payload, "essay_beta"),
            "honors_raw": json.dumps(honors, ensure_ascii=False),
            "activities_raw": json.dumps(activities, ensure_ascii=False),
            "social_certificate": get_field_value(payload, "honor_certificate") or "",
            "additional_info": json.dumps(additional_info, ensure_ascii=False),
            "processing_status": "pending",
            "processing_error": None,
            "processing_started_at": None,
            "processed_at": None,
            "parser_status": "pending",
            "parser_error": None,
            "scoring_status": "pending",
            "scoring_error": None,
            "notification_status": "pending",
            "notification_error": None,
            "raw_payload": json.dumps(payload, ensure_ascii=False),
        }

        with self._connect() as conn:
            columns = self._table_columns(conn, "candidate_responses")
            missing_columns = sorted(
                key for key in CANDIDATE_RESPONSE_REQUIRED_COLUMNS if key not in columns
            )
            if missing_columns:
                raise sqlite3.OperationalError(
                    "candidate_responses schema is missing columns: "
                    + ", ".join(missing_columns)
                )
            insert_data = {key: value for key, value in mapped.items() if key in columns}

            column_names = ", ".join(insert_data.keys())
            value_names = ", ".join(f":{key}" for key in insert_data.keys())
            query = f"INSERT INTO candidate_responses ({column_names}) VALUES ({value_names})"
            cur = conn.execute(query, insert_data)
            return cur.lastrowid

    def update_candidate_response_processing(
        self,
        response_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        if status not in {"pending", "processing", "done", "failed"}:
            raise ValueError(f"Unsupported processing status: {status}")

        if status == "processing":
            started_at = "datetime('now')"
        elif status == "pending":
            started_at = "NULL"
        else:
            started_at = "processing_started_at"
        processed_at = "datetime('now')" if status in {"done", "failed"} else "NULL"
        error_value = error if status == "failed" else None

        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE candidate_responses
                SET processing_status=?,
                    processing_error=?,
                    processing_started_at={started_at},
                    processed_at={processed_at}
                WHERE id=?
                """,
                (status, error_value, int(response_id)),
            )

    def reset_candidate_response_stages(self, response_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE candidate_responses
                SET parser_status='pending',
                    parser_error=NULL,
                    scoring_status='pending',
                    scoring_error=NULL,
                    notification_status='pending',
                    notification_error=NULL
                WHERE id=?
                """,
                (int(response_id),),
            )

    def update_candidate_response_stage(
        self,
        response_id: int,
        stage: str,
        status: str,
        error: str | None = None,
    ) -> None:
        if stage not in STAGE_COLUMN_MAP:
            raise ValueError(f"Unsupported stage: {stage}")
        if status not in {"pending", "processing", "done", "failed", "skipped", "partial"}:
            raise ValueError(f"Unsupported stage status: {status}")

        status_column, error_column = STAGE_COLUMN_MAP[stage]
        error_value = error if status in {"failed", "partial"} else None

        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE candidate_responses
                SET {status_column}=?,
                    {error_column}=?
                WHERE id=?
                """,
                (status, error_value, int(response_id)),
            )

    def get_candidate_response(self, user_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_responses WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_candidate_response_by_id(self, response_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_responses WHERE id=?",
                (int(response_id),),
            ).fetchone()
        return dict(row) if row else None

    def enqueue_workflow_job(
        self,
        response_id: int,
        user_id: int,
        payload: dict,
        max_attempts: int = 3,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workflow_jobs (response_id, user_id, payload_json, max_attempts)
                VALUES (?,?,?,?)
                ON CONFLICT(response_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    payload_json=excluded.payload_json,
                    max_attempts=excluded.max_attempts,
                    status='queued',
                    current_stage='queued',
                    attempts=0,
                    last_error=NULL,
                    available_at=datetime('now'),
                    locked_at=NULL,
                    completed_at=NULL,
                    updated_at=datetime('now')
                """,
                (int(response_id), int(user_id), json.dumps(payload, ensure_ascii=False), int(max_attempts)),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM workflow_jobs WHERE response_id=?",
                (int(response_id),),
            ).fetchone()
            if not row:
                raise sqlite3.OperationalError("Failed to resolve workflow job id")
            return int(row["id"])

    def recover_stale_workflow_jobs(self, timeout_seconds: int = 900) -> int:
        timeout_seconds = max(1, int(timeout_seconds))
        stale_modifier = f"-{timeout_seconds} seconds"
        recovered = 0

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, response_id, attempts, max_attempts, current_stage
                FROM workflow_jobs
                WHERE status='processing'
                  AND locked_at IS NOT NULL
                  AND datetime(locked_at) <= datetime('now', ?)
                """,
                (stale_modifier,),
            ).fetchall()

            for row in rows:
                recovered += 1
                job_id = int(row["id"])
                attempts = int(row["attempts"])
                max_attempts = int(row["max_attempts"])
                response_id = int(row["response_id"]) if row["response_id"] is not None else None
                current_stage = str(row["current_stage"] or "").strip()
                stage_mapping = STAGE_COLUMN_MAP.get(current_stage)
                dead_letter_error = "workflow job timed out and exceeded max attempts"
                retry_error = "workflow job timed out and was re-queued"

                if attempts >= max_attempts:
                    conn.execute(
                        """
                        UPDATE workflow_jobs
                        SET status='dead_letter',
                            current_stage='dead_letter',
                            last_error=COALESCE(last_error, ?),
                            updated_at=datetime('now'),
                            completed_at=datetime('now')
                        WHERE id=?
                        """,
                        (dead_letter_error, job_id),
                    )
                    if response_id is not None:
                        if stage_mapping:
                            status_column, error_column = stage_mapping
                            conn.execute(
                                f"""
                                UPDATE candidate_responses
                                SET processing_status='failed',
                                    processing_error=?,
                                    processed_at=datetime('now'),
                                    {status_column}='failed',
                                    {error_column}=?
                                WHERE id=?
                                """,
                                (dead_letter_error, dead_letter_error, response_id),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE candidate_responses
                                SET processing_status='failed',
                                    processing_error=?,
                                    processed_at=datetime('now')
                                WHERE id=?
                                """,
                                (dead_letter_error, response_id),
                            )
                else:
                    conn.execute(
                        """
                        UPDATE workflow_jobs
                        SET status='retry',
                            current_stage='queued',
                            last_error=COALESCE(last_error, ?),
                            available_at=datetime('now'),
                            locked_at=NULL,
                            updated_at=datetime('now')
                        WHERE id=?
                        """,
                        (retry_error, job_id),
                    )
                    if response_id is not None:
                        if stage_mapping:
                            status_column, error_column = stage_mapping
                            conn.execute(
                                f"""
                                UPDATE candidate_responses
                                SET processing_status='pending',
                                    processing_error=NULL,
                                    processing_started_at=NULL,
                                    processed_at=NULL,
                                    {status_column}='failed',
                                    {error_column}=?
                                WHERE id=?
                                """,
                                (retry_error, response_id),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE candidate_responses
                                SET processing_status='pending',
                                    processing_error=NULL,
                                    processing_started_at=NULL,
                                    processed_at=NULL
                                WHERE id=?
                                """,
                                (response_id,),
                            )
        return recovered

    def claim_next_workflow_job(self) -> dict | None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT *
                FROM workflow_jobs
                WHERE status IN ('queued', 'retry')
                  AND datetime(COALESCE(available_at, datetime('now'))) <= datetime('now')
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                conn.commit()
                return None

            attempts = int(row["attempts"]) + 1
            conn.execute(
                """
                UPDATE workflow_jobs
                SET status='processing',
                    current_stage='workflow',
                    attempts=?,
                    locked_at=datetime('now'),
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (attempts, int(row["id"])),
            )
            updated = conn.execute(
                "SELECT * FROM workflow_jobs WHERE id=?",
                (int(row["id"]),),
            ).fetchone()
            conn.commit()
        return dict(updated) if updated else None

    def update_workflow_job_stage(self, job_id: int, stage: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE workflow_jobs
                SET current_stage=?,
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (stage, int(job_id)),
            )

    def get_workflow_job(self, job_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_jobs WHERE id=?",
                (int(job_id),),
            ).fetchone()
        return dict(row) if row else None

    def complete_workflow_job(self, job_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE workflow_jobs
                SET status='completed',
                    current_stage='completed',
                    locked_at=NULL,
                    completed_at=datetime('now'),
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (int(job_id),),
            )

    def fail_workflow_job(
        self,
        job_id: int,
        error: str,
        retry_delay_seconds: int = 30,
    ) -> dict:
        retry_delay_seconds = max(1, int(retry_delay_seconds))
        delay_modifier = f"+{retry_delay_seconds} seconds"

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_jobs WHERE id=?",
                (int(job_id),),
            ).fetchone()
            if not row:
                raise sqlite3.OperationalError(f"Workflow job {job_id} not found")

            attempts = int(row["attempts"])
            max_attempts = int(row["max_attempts"])
            final_status = "dead_letter" if attempts >= max_attempts else "retry"
            next_stage = "dead_letter" if final_status == "dead_letter" else "queued"
            completed_clause = "datetime('now')" if final_status == "dead_letter" else "NULL"
            available_clause = "NULL" if final_status == "dead_letter" else f"datetime('now', '{delay_modifier}')"

            conn.execute(
                f"""
                UPDATE workflow_jobs
                SET status=?,
                    current_stage=?,
                    last_error=?,
                    locked_at=NULL,
                    available_at={available_clause},
                    completed_at={completed_clause},
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (final_status, next_stage, str(error)[:2000], int(job_id)),
            )
            updated = conn.execute(
                "SELECT * FROM workflow_jobs WHERE id=?",
                (int(job_id),),
            ).fetchone()
        return dict(updated) if updated else {}

    # --- user_files ---
    def save_file(self, user_id: int, file_id: str, file_type: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO user_files (user_id, file_id, file_type) VALUES (?,?,?)",
                (user_id, file_id, file_type)
            )
            return cur.lastrowid

    def ensure_file(self, user_id: int, file_id: str, file_type: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM user_files WHERE user_id=? AND file_id=? LIMIT 1",
                (int(user_id), str(file_id)),
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO user_files (user_id, file_id, file_type) VALUES (?,?,?)",
                (int(user_id), str(file_id), str(file_type)),
            )
            return int(cur.lastrowid)

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

    def get_recent_scoring_results(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    user_id AS candidate_id,
                    total AS total_score,
                    motivation,
                    experience,
                    leadership,
                    growth,
                    ai_suspicion,
                    scored_at
                FROM scores
                ORDER BY scored_at DESC, user_id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_candidate_dashboard_rows(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.telegram_id,
                    u.created_at,
                    t.username,
                    t.first_name AS tg_first_name,
                    t.last_name AS tg_last_name,
                    r.email,
                    r.first_name AS form_first_name,
                    r.last_name AS form_last_name,
                    r.program_applied,
                    r.major,
                    r.personal_presentation,
                    r.english_results,
                    r.english_test_certificate,
                    r.additional_documents,
                    r.social_certificate,
                    r.additional_info,
                    r.processing_status,
                    r.processing_error,
                    r.processing_started_at,
                    r.processed_at,
                    r.parser_status,
                    r.parser_error,
                    r.scoring_status,
                    r.scoring_error,
                    r.notification_status,
                    r.notification_error,
                    r.raw_payload,
                    s.total AS total_score,
                    s.motivation,
                    s.experience,
                    s.leadership,
                    s.growth,
                    s.ai_suspicion,
                    s.scored_at
                FROM users u
                LEFT JOIN telegram_users t
                    ON t.telegram_id = u.telegram_id
                LEFT JOIN candidate_responses r
                    ON r.id = (
                        SELECT cr.id
                        FROM candidate_responses cr
                        WHERE cr.user_id = u.id
                        ORDER BY cr.id DESC
                        LIMIT 1
                    )
                LEFT JOIN scores s
                    ON s.user_id = u.id
                ORDER BY
                    CASE WHEN s.total IS NULL THEN 1 ELSE 0 END,
                    s.total DESC,
                    u.id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

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
