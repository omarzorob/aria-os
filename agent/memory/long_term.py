"""
Long-term memory — persists facts, preferences, and history across sessions.
Backed by SQLite.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".aria" / "memory.db"


class LongTermMemory:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def remember(self, key: str, value: str, source: str = "user"):
        """Store a fact."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, source, updated_at) VALUES (?, ?, ?, ?)",
            (key, value, source, now)
        )
        self.conn.commit()

    def recall(self, key: str) -> str | None:
        """Retrieve a fact by key."""
        row = self.conn.execute(
            "SELECT value FROM facts WHERE key = ? ORDER BY updated_at DESC LIMIT 1",
            (key,)
        ).fetchone()
        return row[0] if row else None

    def set_preference(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def get_preference(self, key: str, default: str = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def log_turn(self, role: str, content: str, tool_calls: list = None):
        """Log a conversation turn."""
        self.conn.execute(
            "INSERT INTO history (role, content, tool_calls) VALUES (?, ?, ?)",
            (role, content, json.dumps(tool_calls) if tool_calls else None)
        )
        self.conn.commit()

    def recent_history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content FROM history ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def all_facts(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM facts ORDER BY updated_at DESC").fetchall()
        return {r[0]: r[1] for r in rows}
