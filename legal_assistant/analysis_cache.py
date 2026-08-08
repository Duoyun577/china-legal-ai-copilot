"""法律咨询和案件分析共用的持久化结果缓存。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config.settings import settings
from utils.database import Database


class AnalysisCache:
    def __init__(self, database_path: str | Path | None = None, *, user_id: str = "local") -> None:
        target = database_path if database_path is not None else (settings.database_url or settings.analysis_cache_database_path)
        self._database = Database(target)
        self.database_path = self._database.path
        self.user_id = user_id
        with self._database.connect() as connection:
            sqlite_schema = "CREATE TABLE IF NOT EXISTS analysis_cache (cache_key TEXT PRIMARY KEY, namespace TEXT NOT NULL, value_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);"
            postgres_schema = ["CREATE TABLE IF NOT EXISTS analysis_cache (cache_key TEXT PRIMARY KEY, namespace TEXT NOT NULL, value_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text))"]
            self._database.execute_script(connection, sqlite_schema, postgres_schema)

    @staticmethod
    def key(namespace: str, payload: Any) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return f"{namespace}:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"

    def get(self, namespace: str, payload: Any) -> Any | None:
        cache_key = f"{self.user_id}:{self.key(namespace, payload)}"
        with self._database.connect() as connection:
            row = connection.execute("SELECT value_json FROM analysis_cache WHERE cache_key = ?", (cache_key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, namespace: str, payload: Any, value: Any) -> None:
        cache_key = f"{self.user_id}:{self.key(namespace, payload)}"
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO analysis_cache (cache_key, namespace, value_json) VALUES (?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET value_json = excluded.value_json, created_at = CURRENT_TIMESTAMP",
                (cache_key, namespace, encoded),
            )
