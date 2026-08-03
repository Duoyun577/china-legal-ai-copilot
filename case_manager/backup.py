"""案件 SQLite 数据库的在线备份与安全恢复。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class DatabaseBackupError(RuntimeError):
    """数据库备份或恢复失败。"""


class CaseDatabaseBackup:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()

    def backup(self, destination: str | Path) -> Path:
        target = self._resolve_backup_target(destination)
        if not self.database_path.is_file():
            raise DatabaseBackupError(f"案件数据库不存在：{self.database_path}")
        if target == self.database_path:
            raise DatabaseBackupError("备份文件不能与案件数据库相同。")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(self.database_path)) as source:
                with closing(sqlite3.connect(target)) as output:
                    source.backup(output)
            self._verify(target)
        except (OSError, sqlite3.Error) as exc:
            target.unlink(missing_ok=True)
            raise DatabaseBackupError(f"案件数据库备份失败：{exc}") from exc
        return target

    def automatic_backup(self, backup_directory: str | Path, *, retain: int = 7) -> Path | None:
        """每天至多创建一个自动备份，并仅保留最近若干份。"""
        if retain <= 0:
            raise ValueError("自动备份保留数量必须为正整数。")
        if not self.database_path.is_file():
            return None
        directory = Path(backup_directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        target = directory / f"cases_auto_{day}.db"
        if not target.exists():
            self.backup(target)
        backups = sorted(directory.glob("cases_auto_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for expired in backups[retain:]:
            expired.unlink(missing_ok=True)
        return target

    def restore(self, backup_path: str | Path) -> Path:
        source_path = Path(backup_path).resolve()
        if not source_path.is_file():
            raise DatabaseBackupError(f"备份文件不存在：{source_path}")
        if source_path == self.database_path:
            raise DatabaseBackupError("恢复来源不能与案件数据库相同。")
        self._verify(source_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(source_path)) as source:
                with closing(sqlite3.connect(self.database_path)) as output:
                    source.backup(output)
            self._verify(self.database_path)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseBackupError(f"案件数据库恢复失败：{exc}") from exc
        return self.database_path

    def _resolve_backup_target(self, destination: str | Path) -> Path:
        target = Path(destination).resolve()
        if target.exists() and target.is_dir():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            return target / f"cases_{timestamp}.db"
        return target

    @staticmethod
    def _verify(path: Path) -> None:
        try:
            with closing(sqlite3.connect(path)) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            raise DatabaseBackupError(f"无效的 SQLite 备份：{exc}") from exc
        if not result or result[0] != "ok":
            raise DatabaseBackupError("SQLite 备份完整性检查失败。")
