# AUTHOR: IAN SAVINO
# DATE: 2026

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def _resolve_db_path() -> str:
    """Where the storage database lives.

    Anchored to a stable, user-level location so the installed `anvil`
    command uses one database no matter which directory it runs from - a
    bare relative "storage.db" would scatter a fresh, empty DB per cwd.
    Override with the ANVIL_STORAGE_DB environment variable.
    """
    override = os.environ.get("ANVIL_STORAGE_DB")
    if override:
        return override
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    data_dir = Path(base) / "anvil"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "storage.db")


DB_PATH = _resolve_db_path()


@contextmanager
def get_connection(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                name TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                specialty TEXT,
                tier TEXT NOT NULL CHECK(tier IN ('planner', 'worker')),
                base_url TEXT,
                key_name TEXT
            )
        """)
        # Migrate pre-existing databases that lack the newer columns
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(models)")
        }
        for column in ("base_url", "key_name"):
            if column not in existing_cols:
                conn.execute(f"ALTER TABLE models ADD COLUMN {column} TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_text TEXT NOT NULL,
                final_answer TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                subtask_index INTEGER NOT NULL,
                subtask_text TEXT NOT NULL,
                result TEXT,
                model TEXT REFERENCES models(name),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Seed the known models
        conn.executemany(
            "INSERT OR IGNORE INTO models "
            "(name, model_id, provider, specialty, tier, base_url, key_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "claude",
                    "claude-sonnet-4-6",
                    "anthropic",
                    "task planning and synthesis",
                    "planner",
                    None,
                    "ANTHROPIC_API_KEY",
                ),
                (
                    "qwen",
                    "qwen2.5-coder:3b",
                    "ollama",
                    "code generation",
                    "worker",
                    "http://localhost:11434/v1",
                    None,
                ),
            ],
        )
        # Backfill seeded rows from databases created before these columns existed
        conn.execute(
            "UPDATE models SET key_name = 'ANTHROPIC_API_KEY' "
            "WHERE name = 'claude' AND key_name IS NULL"
        )
        conn.execute(
            "UPDATE models SET base_url = 'http://localhost:11434/v1' "
            "WHERE name = 'qwen' AND base_url IS NULL"
        )


def get_models(tier: str, db_path: str = DB_PATH) -> list[dict]:
    """Return all model rows for a tier ('planner' or 'worker')."""
    with get_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM models WHERE tier = ?", (tier,)
        ).fetchall()
        return [dict(row) for row in rows]


def save_request(
    request_text: str,
    subtasks: list[str],
    results: dict[str, str],
    final_answer: str,
    model: str,
    db_path: str = DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO requests (request_text, final_answer) VALUES (?, ?)",
            (request_text, final_answer),
        )
        request_id = cur.lastrowid
        for i, subtask in enumerate(subtasks):
            result = results.get(f"subtask_{i + 1}", "")
            conn.execute(
                "INSERT INTO subtasks "
                "(request_id, subtask_index, subtask_text, result, model) "
                "VALUES (?, ?, ?, ?, ?)",
                (request_id, i + 1, subtask, result, model),
            )
        return request_id


def get_history(limit: int = 10, db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        requests = conn.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

        history = []
        for request in requests:
            subtasks = conn.execute(
                "SELECT * FROM subtasks WHERE request_id = ? ORDER BY subtask_index",
                (request["id"],),
            ).fetchall()
            history.append({
                "id": request["id"],
                "request_text": request["request_text"],
                "final_answer": request["final_answer"],
                "created_at": request["created_at"],
                "subtasks": [dict(sub) for sub in subtasks],
            })
        return history
