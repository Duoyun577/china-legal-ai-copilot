"""Per-user usage metering, quotas, and privacy-safe administration."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterator

from config.settings import settings
from utils.database import Database
from utils.logger import log_exception


EVENT_CONTRACT_REVIEW = "contract_review"
EVENT_LEGAL_CONSULTATION = "legal_consultation"
EVENT_DOCUMENT_GENERATION = "document_generation"
SUPPORTED_EVENTS = {EVENT_CONTRACT_REVIEW, EVENT_LEGAL_CONSULTATION, EVENT_DOCUMENT_GENERATION}


class UsageQuotaExceeded(RuntimeError):
    """Raised before a paid AI operation when the user's quota is exhausted."""


@dataclass(frozen=True)
class UsageStatistics:
    contract_review_count: int
    legal_consultation_count: int
    document_generation_count: int
    average_response_time: float


@dataclass(frozen=True)
class QuotaStatus:
    daily_used: int
    daily_limit: int
    monthly_used: int
    monthly_limit: int

    @property
    def daily_remaining(self) -> int:
        return max(0, self.daily_limit - self.daily_used)

    @property
    def monthly_remaining(self) -> int:
        return max(0, self.monthly_limit - self.monthly_used)


class UsageTracker:
    def __init__(
        self,
        database_path: str | Path | None = None,
        *,
        user_id: str = "local",
        daily_limit: int | None = None,
        monthly_limit: int | None = None,
        quota_exempt: bool = False,
    ) -> None:
        target = database_path if database_path is not None else (settings.database_url or settings.usage_database_path)
        self._database = Database(target)
        self.database_path = self._database.path
        self.user_id = user_id
        self.daily_limit = daily_limit or settings.daily_api_limit
        self.monthly_limit = monthly_limit or settings.monthly_api_limit
        self.quota_exempt = quota_exempt
        with self._connect() as connection:
            sqlite_schema = (
                "CREATE TABLE IF NOT EXISTS usage_events ("
                "event_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL DEFAULT 'local', "
                "event_type TEXT NOT NULL, duration_seconds REAL NOT NULL, succeeded INTEGER NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);"
                "CREATE TABLE IF NOT EXISTS user_profiles ("
                "user_id TEXT PRIMARY KEY, email TEXT NOT NULL, display_name TEXT NOT NULL, "
                "is_admin INTEGER NOT NULL DEFAULT 0, last_seen_at TEXT NOT NULL);"
            )
            postgres_schema = [
                "CREATE TABLE IF NOT EXISTS usage_events (event_id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'local', event_type TEXT NOT NULL, duration_seconds DOUBLE PRECISION NOT NULL, succeeded INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text))",
                "CREATE TABLE IF NOT EXISTS user_profiles (user_id TEXT PRIMARY KEY, email TEXT NOT NULL, display_name TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0, last_seen_at TEXT NOT NULL)",
                "ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'local'",
                "CREATE INDEX IF NOT EXISTS idx_usage_user_created ON usage_events(user_id, created_at)",
            ]
            self._database.execute_script(connection, sqlite_schema, postgres_schema)
            columns = self._database.columns(connection, "usage_events")
            if "user_id" not in columns:
                connection.execute("ALTER TABLE usage_events ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_created ON usage_events(user_id, created_at)")

    def _connect(self):
        return self._database.connect()

    def register_user(self, email: str, display_name: str, *, is_admin: bool = False) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO user_profiles (user_id, email, display_name, is_admin, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "email = excluded.email, display_name = excluded.display_name, "
                "is_admin = excluded.is_admin, last_seen_at = excluded.last_seen_at",
                (self.user_id, email.strip().lower(), display_name.strip(), int(is_admin), now),
            )

    def record(self, event_type: str, duration_seconds: float, *, succeeded: bool = True) -> None:
        if event_type not in SUPPORTED_EVENTS:
            raise ValueError(f"不支持的统计事件：{event_type}")
        if duration_seconds < 0:
            raise ValueError("响应时间不能为负数。")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO usage_events (user_id, event_type, duration_seconds, succeeded) VALUES (?, ?, ?, ?)",
                (self.user_id, event_type, float(duration_seconds), int(succeeded)),
            )

    def quota_status(self, *, now: datetime | None = None) -> QuotaStatus:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            daily = connection.execute(
                "SELECT COUNT(*) FROM usage_events WHERE user_id = ? AND created_at >= ?",
                (self.user_id, day_start),
            ).fetchone()[0]
            monthly = connection.execute(
                "SELECT COUNT(*) FROM usage_events WHERE user_id = ? AND created_at >= ?",
                (self.user_id, month_start),
            ).fetchone()[0]
        return QuotaStatus(int(daily), self.daily_limit, int(monthly), self.monthly_limit)

    def check_quota(self) -> QuotaStatus:
        status = self.quota_status()
        if self.quota_exempt:
            return status
        if status.daily_used >= status.daily_limit:
            raise UsageQuotaExceeded(f"今日 AI 使用次数已达到上限（{status.daily_limit} 次），请明天再试。")
        if status.monthly_used >= status.monthly_limit:
            raise UsageQuotaExceeded(f"本月 AI 使用次数已达到上限（{status.monthly_limit} 次），请联系管理员。")
        return status

    @contextmanager
    def measure(self, event_type: str) -> Iterator[None]:
        self.check_quota()
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
        with self._connect() as connection:
            for event_type, count in connection.execute(
                "SELECT event_type, COUNT(*) FROM usage_events "
                "WHERE user_id = ? AND succeeded = 1 GROUP BY event_type",
                (self.user_id,),
            ):
                counts[event_type] = int(count)
            row = connection.execute(
                "SELECT COALESCE(AVG(duration_seconds), 0) FROM usage_events "
                "WHERE user_id = ? AND succeeded = 1",
                (self.user_id,),
            ).fetchone()
        return UsageStatistics(
            counts[EVENT_CONTRACT_REVIEW], counts[EVENT_LEGAL_CONSULTATION],
            counts[EVENT_DOCUMENT_GENERATION], float(row[0]),
        )

    def admin_summary(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT p.user_id, p.email, p.display_name, p.is_admin, p.last_seen_at, "
                "COUNT(e.event_id) AS total_calls, "
                "SUM(CASE WHEN e.succeeded = 1 THEN 1 ELSE 0 END) AS successful_calls "
                "FROM user_profiles p LEFT JOIN usage_events e ON e.user_id = p.user_id "
                "GROUP BY p.user_id, p.email, p.display_name, p.is_admin, p.last_seen_at "
                "ORDER BY p.last_seen_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
