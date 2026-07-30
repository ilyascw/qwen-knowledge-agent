from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from knowledge_agent.models import MemoryRecord

_MAX_KEY_LENGTH = 120
_MAX_CONTENT_LENGTH = 20_000
_SEARCH_SCAN_LIMIT = 1_000


class MemoryError(ValueError):
    """A requested memory operation is invalid."""


class SQLiteMemoryStore:
    """The agent's only persistent writable storage."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def remember(self, key: str, content: str) -> MemoryRecord:
        normalized_key = self._validate_key(key)
        normalized_content = content.strip()
        if not normalized_content:
            raise MemoryError("Memory content must not be empty")
        if len(normalized_content) > _MAX_CONTENT_LENGTH:
            raise MemoryError(f"Memory content exceeds {_MAX_CONTENT_LENGTH} characters")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (key, content)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (normalized_key, normalized_content),
            )
            row = connection.execute(
                """
                SELECT key, content, created_at, updated_at
                FROM memories
                WHERE key = ?
                """,
                (normalized_key,),
            ).fetchone()

        if row is None:
            raise RuntimeError("Memory was not persisted")
        return self._to_record(row)

    def recall(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        normalized_limit = self._validate_limit(limit)
        query_terms = {term for term in query.casefold().split() if term}

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT key, content, created_at, updated_at
                FROM memories
                ORDER BY updated_at DESC, key ASC
                LIMIT ?
                """,
                (_SEARCH_SCAN_LIMIT,),
            ).fetchall()

        records = [self._to_record(row) for row in rows]
        if not query_terms:
            return records[:normalized_limit]

        ranked: list[tuple[int, MemoryRecord]] = []
        for record in records:
            haystack = f"{record.key} {record.content}".casefold()
            score = sum(term in haystack for term in query_terms)
            if score:
                ranked.append((score, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in ranked[:normalized_limit]]

    def forget(self, key: str) -> bool:
        normalized_key = self._validate_key(key)
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE key = ?", (normalized_key,))
        return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM memories").fetchone()
        return int(row[0]) if row is not None else 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _validate_key(key: str) -> str:
        normalized = key.strip()
        if not normalized:
            raise MemoryError("Memory key must not be empty")
        if len(normalized) > _MAX_KEY_LENGTH:
            raise MemoryError(f"Memory key exceeds {_MAX_KEY_LENGTH} characters")
        if any(character.isspace() for character in normalized):
            raise MemoryError("Memory key must not contain whitespace")
        return normalized

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not 1 <= limit <= 50:
            raise MemoryError("Memory result limit must be between 1 and 50")
        return limit

    @staticmethod
    def _to_record(row: Iterable[object]) -> MemoryRecord:
        key, content, created_at, updated_at = row
        return MemoryRecord(
            key=str(key),
            content=str(content),
            created_at=str(created_at),
            updated_at=str(updated_at),
        )
