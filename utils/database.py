"""Small DB-API compatibility layer for SQLite and PostgreSQL."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class DatabaseConfigurationError(RuntimeError):
    """Raised when the configured persistent database cannot be used."""


class _CursorProxy:
    def __init__(self, cursor: Any, identity_column: str | None = None) -> None:
        self._cursor = cursor
        self._identity_column = identity_column
        self._lastrowid = None
        if identity_column is not None:
            row = cursor.fetchone()
            self._lastrowid = row[identity_column]

    @property
    def lastrowid(self) -> Any:
        return self._lastrowid if self._identity_column is not None else self._cursor.lastrowid

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> Any:
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class _ConnectionProxy:
    _IDENTITIES = {
        "cases": "case_id",
        "case_records": "record_id",
        "case_files": "file_id",
        "case_events": "event_id",
        "usage_events": "event_id",
    }

    def __init__(self, connection: Any, *, postgres: bool) -> None:
        self._connection = connection
        self._postgres = postgres

    def execute(self, sql: str, parameters: tuple | list = ()) -> _CursorProxy:
        statement = sql.replace("?", "%s") if self._postgres else sql
        identity = None
        if self._postgres and statement.lstrip().upper().startswith("INSERT INTO") and "RETURNING" not in statement.upper():
            table = statement.lstrip().split()[2].strip('"').lower()
            if table in self._IDENTITIES and "ON CONFLICT" not in statement.upper():
                identity = self._IDENTITIES[table]
                statement = f"{statement} RETURNING {identity}"
        cursor = self._connection.execute(statement, parameters)
        return _CursorProxy(cursor, identity)

    def executescript(self, script: str) -> None:
        if self._postgres:
            raise DatabaseConfigurationError("PostgreSQL 初始化必须使用专用迁移语句。")
        self._connection.executescript(script)


class Database:
    def __init__(self, target: str | Path) -> None:
        self.target = target
        self.is_postgres = isinstance(target, str) and target.startswith(("postgresql://", "postgres://"))
        if not self.is_postgres:
            self.path = Path(target)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.path = None

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise DatabaseConfigurationError(
                    "已配置 DATABASE_URL，但缺少 psycopg 依赖。"
                ) from exc
            try:
                with psycopg.connect(str(self.target), row_factory=dict_row, connect_timeout=10) as connection:
                    yield _ConnectionProxy(connection, postgres=True)
            except DatabaseConfigurationError:
                raise
            except Exception as exc:
                raise DatabaseConfigurationError(f"PostgreSQL 数据库操作失败：{exc}") from exc
            return

        try:
            connection = sqlite3.connect(self.path, timeout=15)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                with connection:
                    yield _ConnectionProxy(connection, postgres=False)
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise DatabaseConfigurationError(f"SQLite 数据库操作失败：{exc}") from exc

    def execute(self, connection: Any, sql: str, parameters: tuple | list = ()) -> Any:
        statement = sql.replace("?", "%s") if self.is_postgres else sql
        return connection.execute(statement, parameters)

    def execute_script(self, connection: Any, sqlite_script: str, postgres_statements: list[str]) -> None:
        if self.is_postgres:
            for statement in postgres_statements:
                connection.execute(statement)
        else:
            connection.executescript(sqlite_script)

    def columns(self, connection: Any, table: str) -> set[str]:
        if self.is_postgres:
            rows = connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            ).fetchall()
            return {str(row["column_name"]) for row in rows}
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
