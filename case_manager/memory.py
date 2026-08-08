"""案件长期记忆的 SQLite 持久化层。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.database import Database


@dataclass(frozen=True)
class CaseMemory:
    case_id: int
    case_facts: list[Any] = field(default_factory=list)
    legal_relationships: list[Any] = field(default_factory=list)
    dispute_issues: list[Any] = field(default_factory=list)
    legal_analysis: Any = field(default_factory=dict)
    similar_cases: list[Any] = field(default_factory=list)
    evidence_status: list[Any] = field(default_factory=list)
    consultation_history: list[Any] = field(default_factory=list)
    updated_at: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class CaseMemoryStore:
    """与案件库同库保存记忆，但不改变现有 Repository 表。"""

    _JSON_FIELDS = (
        "case_facts", "legal_relationships", "dispute_issues", "legal_analysis",
        "similar_cases", "evidence_status", "consultation_history",
    )

    def __init__(self, database_path: str | Path) -> None:
        self.database_target = database_path
        self._database = Database(database_path)
        self.database_path = self._database.path
        self._initialize()

    def _connect(self):
        return self._database.connect()

    def _initialize(self) -> None:
        with self._connect() as connection:
            sqlite_schema = """
                CREATE TABLE IF NOT EXISTS case_memories (
                    case_id INTEGER PRIMARY KEY,
                    case_facts_json TEXT NOT NULL,
                    legal_relationships_json TEXT NOT NULL,
                    dispute_issues_json TEXT NOT NULL,
                    legal_analysis_json TEXT NOT NULL,
                    similar_cases_json TEXT NOT NULL,
                    evidence_status_json TEXT NOT NULL,
                    consultation_history_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
                )
                """
            postgres_schema = [
                "CREATE TABLE IF NOT EXISTS case_memories (case_id BIGINT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE, case_facts_json TEXT NOT NULL, legal_relationships_json TEXT NOT NULL, dispute_issues_json TEXT NOT NULL, legal_analysis_json TEXT NOT NULL, similar_cases_json TEXT NOT NULL, evidence_status_json TEXT NOT NULL, consultation_history_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
            ]
            self._database.execute_script(connection, sqlite_schema, postgres_schema)

    def load(self, case_id: int) -> CaseMemory:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM case_memories WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return CaseMemory(case_id=case_id)
        values = {field: json.loads(row[f"{field}_json"]) for field in self._JSON_FIELDS}
        return CaseMemory(case_id=case_id, updated_at=row["updated_at"], **values)

    def save(self, memory: CaseMemory) -> CaseMemory:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        values = [json.dumps(getattr(memory, field), ensure_ascii=False) for field in self._JSON_FIELDS]
        columns = ", ".join(f"{field}_json" for field in self._JSON_FIELDS)
        placeholders = ", ".join("?" for _ in self._JSON_FIELDS)
        updates = ", ".join(f"{field}_json = excluded.{field}_json" for field in self._JSON_FIELDS)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO case_memories (case_id, {columns}, updated_at) VALUES (?, {placeholders}, ?) "
                f"ON CONFLICT(case_id) DO UPDATE SET {updates}, updated_at = excluded.updated_at",
                (memory.case_id, *values, now),
            )
        return self.load(memory.case_id)
