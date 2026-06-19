from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from shared.llm.chat_result import LlmResponse


_TRUE_ENV = {"1", "true", "yes", "on"}
_CACHE_LOCK = threading.Lock()
_CACHE_INSTANCE: "SqliteLlmCache | None" = None
_CACHE_ENABLED_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "llm_cache_enabled_override",
    default=None,
)


def _cache_enabled() -> bool:
    override = _CACHE_ENABLED_OVERRIDE.get()
    if override is not None:
        return override
    return llm_cache_env_enabled()


def llm_cache_env_enabled() -> bool:
    """Return whether the process-level ``LLM_CACHE`` setting is enabled."""

    value = os.getenv("LLM_CACHE", "")
    return value.strip().lower() in _TRUE_ENV


def _cache_db_path() -> Path:
    return Path(os.getenv("LLM_CACHE_DB_PATH", ".cache/llm_cache.db"))


@contextmanager
def llm_cache_enabled(enabled: bool | None) -> Iterator[None]:
    """Temporarily override the ambient LLM cache setting for the current request."""

    if enabled is None:
        yield
        return
    token = _CACHE_ENABLED_OVERRIDE.set(enabled)
    try:
        yield
    finally:
        _CACHE_ENABLED_OVERRIDE.reset(token)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _request_hash(envelope: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(envelope).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LlmCacheEntry:
    """Cached raw LLM response payload."""

    request: dict[str, Any]
    response: LlmResponse
    created_at: float


@dataclass(frozen=True)
class LlmCachePayloadEntry:
    """Cached raw LLM response payload as plain JSON data."""

    request: dict[str, Any]
    response: dict[str, Any]
    created_at: float


class SqliteLlmCache:
    """Simple persistent cache for normalized raw LLM requests."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        existing_columns = self._column_names()
        expected_columns = {
            "request_hash",
            "request_json",
            "response_json",
            "created_at",
        }
        if existing_columns and existing_columns != expected_columns:
            self._conn.execute("DROP TABLE llm_cache")
            self._conn.commit()

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                request_hash TEXT PRIMARY KEY,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def _column_names(self) -> set[str]:
        row = self._conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'llm_cache'
            """
        ).fetchone()
        if row is None:
            return set()
        rows = self._conn.execute("PRAGMA table_info(llm_cache)").fetchall()
        return {str(item["name"]) for item in rows}

    def get(self, request: dict[str, Any]) -> LlmCacheEntry | None:
        entry = self.get_payload(request)
        if entry is None:
            return None
        return LlmCacheEntry(
            request=entry.request,
            response=LlmResponse.from_json(entry.response),
            created_at=entry.created_at,
        )

    def get_payload(self, request: dict[str, Any]) -> LlmCachePayloadEntry | None:
        """Return a cached JSON response payload for a normalized request."""

        request_hash = _request_hash(request)
        with _CACHE_LOCK:
            row = self._conn.execute(
                """
                SELECT request_json, response_json, created_at
                FROM llm_cache
                WHERE request_hash = ?
                """,
                (request_hash,),
            ).fetchone()
        if row is None:
            return None
        response = json.loads(str(row["response_json"]))
        if not isinstance(response, dict):
            raise ValueError("Cached LLM response payload must be a JSON object.")
        return LlmCachePayloadEntry(
            request=json.loads(str(row["request_json"])),
            response=response,
            created_at=float(row["created_at"]),
        )

    def put(
        self,
        request: dict[str, Any],
        *,
        response: LlmResponse,
    ) -> None:
        self.put_payload(request, response=response.to_json())

    def put_payload(
        self,
        request: dict[str, Any],
        *,
        response: dict[str, Any],
    ) -> None:
        """Store a cacheable JSON response payload for a normalized request."""

        request_hash = _request_hash(request)
        created_at = time.time()
        request_json = _canonical_json(request)
        response_json = _canonical_json(response)
        with _CACHE_LOCK:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (
                    request_hash,
                    request_json,
                    response_json,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    request_hash,
                    request_json,
                    response_json,
                    created_at,
                ),
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        self._conn.close()


def get_llm_cache() -> SqliteLlmCache | None:
    """Return the shared LLM cache instance when caching is enabled."""

    global _CACHE_INSTANCE
    if not _cache_enabled():
        return None
    if _CACHE_INSTANCE is None:
        _CACHE_INSTANCE = SqliteLlmCache(_cache_db_path())
    return _CACHE_INSTANCE


def reset_llm_cache() -> None:
    """Drop the shared cache instance so tests can swap DB paths safely."""

    global _CACHE_INSTANCE
    if _CACHE_INSTANCE is not None:
        _CACHE_INSTANCE.close()
        _CACHE_INSTANCE = None
