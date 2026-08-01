from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def hosted_mode() -> bool:
    """True when running on a hosted environment without persistent storage
    (Vercel or TRIHUMANIZER_HOSTED=1). Server-side history is disabled there;
    the browser keeps history in localStorage instead."""
    return bool(os.environ.get("VERCEL") or os.environ.get("TRIHUMANIZER_HOSTED"))


class HistoryStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
        if db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _execute(self, sql: str, params: tuple = ()) -> tuple[sqlite3.Cursor, sqlite3.Connection]:
        """Run a statement with an explicitly closed connection (Windows-safe)."""
        connection = self._connect()
        try:
            cursor = connection.execute(sql, params)
            connection.commit()
            return cursor, connection
        except BaseException:
            connection.close()
            raise

    def _init_db(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    context TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def add(self, payload: dict, result: dict) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO history (
                    created_at, source_language, target_language, mode,
                    context, source_text, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    payload.get("source_language", "auto"),
                    payload.get("target_language", "en"),
                    payload.get("mode", "business"),
                    payload.get("context", ""),
                    payload.get("text", ""),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            lastrowid = int(cursor.lastrowid)
            connection.execute(
                """
                DELETE FROM history
                WHERE id NOT IN (
                    SELECT id FROM history ORDER BY id DESC LIMIT 100
                )
                """
            )
            connection.commit()
            return lastrowid
        finally:
            connection.close()

    def list(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 100))
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            connection.close()
        result = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json"))
            result.append(item)
        return result

    def delete(self, history_id: int) -> bool:
        cursor, connection = self._execute("DELETE FROM history WHERE id = ?", (history_id,))
        try:
            return cursor.rowcount > 0
        finally:
            connection.close()

    def clear(self) -> None:
        _, connection = self._execute("DELETE FROM history")
        connection.close()


class NullHistoryStore(HistoryStore):
    """In-memory no-op store for hosted environments. History lives in the
    browser (localStorage) so no persistent writable filesystem is needed."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = None

    def _connect(self) -> sqlite3.Connection:  # pragma: no cover - never used
        raise RuntimeError("NullHistoryStore has no database")

    def _init_db(self) -> None:  # pragma: no cover - never used
        return

    def add(self, payload: dict, result: dict) -> int:
        return 0

    def list(self, limit: int = 100) -> list[dict]:
        return []

    def delete(self, history_id: int) -> bool:
        return True

    def clear(self) -> None:
        return


def make_store(db_path: Path) -> HistoryStore:
    if hosted_mode():
        return NullHistoryStore()
    return HistoryStore(db_path)
