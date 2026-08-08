"""使用本地 SQLite 保存案件、工作记录和文件。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from utils.database import Database


@dataclass(frozen=True)
class CaseSummary:
    case_id: int
    name: str
    parties: str
    case_type: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CaseRecord:
    record_id: int
    case_id: int
    record_type: str
    title: str
    content: Any
    created_at: str


@dataclass(frozen=True)
class StoredFile:
    file_id: int
    case_id: int
    category: str
    filename: str
    mime_type: str
    size: int
    created_at: str


@dataclass(frozen=True)
class CaseEvent:
    event_id: int
    case_id: int
    event_type: str
    title: str
    details: Any
    created_at: str


class CaseManager:
    """案件中心的 SQLite Repository。"""

    def __init__(self, database_path: str | Path | None = None, *, user_id: str = "local") -> None:
        target = database_path if database_path is not None else (settings.database_url or settings.case_database_path)
        self._database = Database(target)
        self.database_target = target
        self.database_path = self._database.path
        self.user_id = user_id.strip()
        if not self.user_id:
            raise ValueError("用户 ID 不能为空。")
        self._initialize()

    def _connect(self):
        return self._database.connect()

    def _initialize(self) -> None:
        with self._connect() as connection:
            sqlite_schema = """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL DEFAULT 'local',
                    name TEXT NOT NULL,
                    parties TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                    record_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_files (
                    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    content BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_case_records_case_id ON case_records(case_id);
                CREATE INDEX IF NOT EXISTS idx_case_files_case_id ON case_files(case_id);
                CREATE TABLE IF NOT EXISTS case_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_case_events_case_id ON case_events(case_id);
                """
            postgres_schema = [
                "CREATE TABLE IF NOT EXISTS cases (case_id BIGSERIAL PRIMARY KEY, owner_id TEXT NOT NULL DEFAULT 'local', name TEXT NOT NULL, parties TEXT NOT NULL, case_type TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS case_records (record_id BIGSERIAL PRIMARY KEY, case_id BIGINT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE, record_type TEXT NOT NULL, title TEXT NOT NULL, content_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS case_files (file_id BIGSERIAL PRIMARY KEY, case_id BIGINT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE, category TEXT NOT NULL, filename TEXT NOT NULL, mime_type TEXT NOT NULL, content BYTEA NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS case_events (event_id BIGSERIAL PRIMARY KEY, case_id BIGINT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE, event_type TEXT NOT NULL, title TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE INDEX IF NOT EXISTS idx_case_records_case_id ON case_records(case_id)",
                "CREATE INDEX IF NOT EXISTS idx_case_files_case_id ON case_files(case_id)",
                "CREATE INDEX IF NOT EXISTS idx_case_events_case_id ON case_events(case_id)",
                "ALTER TABLE cases ADD COLUMN IF NOT EXISTS owner_id TEXT NOT NULL DEFAULT 'local'",
            ]
            self._database.execute_script(connection, sqlite_schema, postgres_schema)
            columns = self._database.columns(connection, "cases")
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE cases ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_owner_id ON cases(owner_id)")

    def create_case(self, name: str, parties: str, case_type: str) -> CaseSummary:
        values = [value.strip() for value in (name, parties, case_type)]
        if not all(values):
            raise ValueError("案件名称、当事人和案件类型均不能为空。")
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO cases (owner_id, name, parties, case_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self.user_id, *values, now, now),
            )
            case_id = int(cursor.lastrowid)
            connection.execute(
                "INSERT INTO case_events (case_id, event_type, title, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (case_id, "case_created", "创建案件", json.dumps({"name": values[0], "parties": values[1], "case_type": values[2]}, ensure_ascii=False), now),
            )
        return self.get_case(case_id)

    def add_event(self, case_id: int, event_type: str, title: str, details: Any | None = None) -> CaseEvent:
        self.get_case(case_id)
        if not event_type.strip() or not title.strip():
            raise ValueError("事件类型和标题不能为空。")
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO case_events (case_id, event_type, title, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (case_id, event_type.strip(), title.strip(), json.dumps(details or {}, ensure_ascii=False), now),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now, case_id))
            event_id = int(cursor.lastrowid)
        return self._get_event(event_id)

    def list_events(self, case_id: int) -> list[CaseEvent]:
        self.get_case(case_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM case_events WHERE case_id = ? ORDER BY created_at DESC, event_id DESC", (case_id,)
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def get_case(self, case_id: int) -> CaseSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_id, name, parties, case_type, created_at, updated_at "
                "FROM cases WHERE case_id = ? AND owner_id = ?",
                (case_id, self.user_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"案件不存在：{case_id}")
        return self._case_from_row(row)

    def list_cases(self) -> list[CaseSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id, name, parties, case_type, created_at, updated_at FROM cases "
                "WHERE owner_id = ? ORDER BY updated_at DESC, case_id DESC",
                (self.user_id,),
            ).fetchall()
        return [self._case_from_row(row) for row in rows]

    def add_record(self, case_id: int, record_type: str, title: str, content: Any) -> CaseRecord:
        self.get_case(case_id)
        if not record_type.strip() or not title.strip():
            raise ValueError("记录类型和标题不能为空。")
        now = self._now()
        content_json = json.dumps(content, ensure_ascii=False)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO case_records (case_id, record_type, title, content_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (case_id, record_type.strip(), title.strip(), content_json, now),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now, case_id))
            record_id = int(cursor.lastrowid)
        return self._get_record(record_id)

    def list_records(self, case_id: int) -> list[CaseRecord]:
        self.get_case(case_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM case_records WHERE case_id = ? ORDER BY created_at DESC, record_id DESC", (case_id,)
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def save_file(self, case_id: int, category: str, filename: str, content: bytes, mime_type: str) -> StoredFile:
        self.get_case(case_id)
        if not category.strip() or not Path(filename).name or not content:
            raise ValueError("文件类别、文件名和文件内容均不能为空。")
        safe_name = Path(filename).name
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO case_files (case_id, category, filename, mime_type, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, category.strip(), safe_name, mime_type.strip() or "application/octet-stream", content, now),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now, case_id))
            if category.strip() == "generated_document":
                connection.execute(
                    "INSERT INTO case_events (case_id, event_type, title, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (case_id, "generated_file", f"生成文件：{safe_name}", json.dumps({"filename": safe_name, "mime_type": mime_type}, ensure_ascii=False), now),
                )
            file_id = int(cursor.lastrowid)
        return self._get_file_metadata(file_id)

    def list_files(self, case_id: int) -> list[StoredFile]:
        self.get_case(case_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_files.file_id, case_files.case_id, case_files.category, case_files.filename, "
                "case_files.mime_type, length(case_files.content) AS size, case_files.created_at "
                "FROM case_files WHERE case_id = ? ORDER BY created_at DESC, file_id DESC",
                (case_id,),
            ).fetchall()
        return [self._file_from_row(row) for row in rows]

    def get_file_content(self, file_id: int) -> bytes:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_files.content FROM case_files JOIN cases USING(case_id) "
                "WHERE case_files.file_id = ? AND cases.owner_id = ?",
                (file_id, self.user_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"文件不存在：{file_id}")
        return bytes(row["content"])

    def _get_record(self, record_id: int) -> CaseRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_records.* FROM case_records JOIN cases USING(case_id) "
                "WHERE case_records.record_id = ? AND cases.owner_id = ?",
                (record_id, self.user_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"记录不存在：{record_id}")
        return self._record_from_row(row)

    def _get_file_metadata(self, file_id: int) -> StoredFile:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_files.file_id, case_files.case_id, case_files.category, case_files.filename, "
                "case_files.mime_type, length(case_files.content) AS size, case_files.created_at "
                "FROM case_files JOIN cases USING(case_id) "
                "WHERE case_files.file_id = ? AND cases.owner_id = ?", (file_id, self.user_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"文件不存在：{file_id}")
        return self._file_from_row(row)

    def _get_event(self, event_id: int) -> CaseEvent:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_events.* FROM case_events JOIN cases USING(case_id) "
                "WHERE case_events.event_id = ? AND cases.owner_id = ?",
                (event_id, self.user_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"事件不存在：{event_id}")
        return self._event_from_row(row)

    @staticmethod
    def _case_from_row(row) -> CaseSummary:
        return CaseSummary(**dict(row))

    @staticmethod
    def _record_from_row(row) -> CaseRecord:
        return CaseRecord(
            record_id=row["record_id"], case_id=row["case_id"], record_type=row["record_type"],
            title=row["title"], content=json.loads(row["content_json"]), created_at=row["created_at"],
        )

    @staticmethod
    def _file_from_row(row) -> StoredFile:
        return StoredFile(**dict(row))

    @staticmethod
    def _event_from_row(row) -> CaseEvent:
        return CaseEvent(
            event_id=row["event_id"], case_id=row["case_id"], event_type=row["event_type"],
            title=row["title"], details=json.loads(row["details_json"]), created_at=row["created_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def admin_case_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT owner_id, COUNT(*) AS case_count FROM cases GROUP BY owner_id ORDER BY owner_id"
            ).fetchall()
        return {str(row["owner_id"]): int(row["case_count"]) for row in rows}
