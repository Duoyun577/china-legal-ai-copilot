"""不记录业务正文和个人信息的基础使用统计。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterator

from config.settings import settings
from utils.logger import log_exception


EVENT_CONTRACT_REVIEW = "contract_review"
EVENT_LEGAL_CONSULTATION = "legal_consultation"
EVENT_DOCUMENT_GENERATION = "document_generation"
SUPPORTED_EVENTS = {EVENT_CONTRACT_REVIEW, EVENT_LEGAL_CONSULTATION, EVENT_DOCUMENT_GENERATION}


@dataclass(frozen=True)
class UsageStatistics:
    contract_review_count: int
    legal_consultation_count: int
    document_generation_count: int
    average_response_time: float


class UsageTracker:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path is not None else settings.usage_database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS usage_events ("
                "event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, "
                "duration_seconds REAL NOT NULL, succeeded INTEGER NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )

    def record(self, event_type: str, duration_seconds: float, *, succeeded: bool = True) -> None:
        if event_type not in SUPPORTED_EVENTS:
            raise ValueError(f"不支持的统计事件：{event_type}")
        if duration_seconds < 0:
            raise ValueError("响应时间不能为负数。")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO usage_events (event_type, duration_seconds, succeeded) VALUES (?, ?, ?)",
                (event_type, float(duration_seconds), int(succeeded)),
            )

    @contextmanager
    def measure(self, event_type: str) -> Iterator[None]:
        started_at = perf_counter()
        succeeded = False
        try:
            yield
            succeeded = True
        except Exception as exc:
            log_exception(f"core_operation_failed event_type={event_type}", exc)
            raise
        finally:
            self.record(event_type, perf_counter() - started_at, succeeded=succeeded)

    def statistics(self) -> UsageStatistics:
        counts = {event: 0 for event in SUPPORTED_EVENTS}
        with sqlite3.connect(self.database_path) as connection:
            for event_type, count in connection.execute(
                "SELECT event_type, COUNT(*) FROM usage_events WHERE succeeded = 1 GROUP BY event_type"
            ):
                counts[event_type] = int(count)
            row = connection.execute(
                "SELECT COALESCE(AVG(duration_seconds), 0) FROM usage_events WHERE succeeded = 1"
            ).fetchone()
        return UsageStatistics(
            counts[EVENT_CONTRACT_REVIEW], counts[EVENT_LEGAL_CONSULTATION],
            counts[EVENT_DOCUMENT_GENERATION], float(row[0]),
        )
