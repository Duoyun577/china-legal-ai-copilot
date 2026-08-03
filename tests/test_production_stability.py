import logging
import sqlite3

import pytest

from analytics.usage_tracker import (
    EVENT_CONTRACT_REVIEW,
    EVENT_DOCUMENT_GENERATION,
    EVENT_LEGAL_CONSULTATION,
    UsageTracker,
)
from case_manager import CaseDatabaseBackup, CaseManager
from utils.logger import initialize_logging, log_exception


def test_case_database_can_be_backed_up_and_restored(tmp_path) -> None:
    database = tmp_path / "cases.db"
    manager = CaseManager(database)
    original = manager.create_case("原案件", "甲 / 乙", "合同纠纷")
    backup = CaseDatabaseBackup(database).backup(tmp_path / "backups" / "snapshot.db")
    manager.create_case("备份后案件", "丙 / 丁", "侵权纠纷")

    CaseDatabaseBackup(database).restore(backup)
    restored = CaseManager(database)

    assert [case.case_id for case in restored.list_cases()] == [original.case_id]
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_automatic_backup_is_daily_and_applies_retention(tmp_path) -> None:
    database = tmp_path / "cases.db"
    CaseManager(database).create_case("案件", "甲 / 乙", "合同纠纷")
    service = CaseDatabaseBackup(database)

    first = service.automatic_backup(tmp_path / "backups", retain=1)
    second = service.automatic_backup(tmp_path / "backups", retain=1)

    assert first == second
    assert first is not None and first.is_file()
    assert len(list((tmp_path / "backups").glob("cases_auto_*.db"))) == 1


def test_error_logger_writes_exception_trace(tmp_path) -> None:
    log_path = tmp_path / "app.log"
    logger = initialize_logging(log_path)
    try:
        raise RuntimeError("测试核心异常")
    except RuntimeError as exc:
        log_exception("core_test_failed", exc)
    for handler in logger.handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "core_test_failed" in content
    assert "RuntimeError: 测试核心异常" in content
    assert logger.level == logging.INFO


def test_usage_tracker_counts_successes_and_average_response_time(tmp_path) -> None:
    tracker = UsageTracker(tmp_path / "usage.db")
    tracker.record(EVENT_CONTRACT_REVIEW, 1.0)
    tracker.record(EVENT_CONTRACT_REVIEW, 3.0)
    tracker.record(EVENT_LEGAL_CONSULTATION, 2.0)
    tracker.record(EVENT_DOCUMENT_GENERATION, 4.0)
    tracker.record(EVENT_DOCUMENT_GENERATION, 100.0, succeeded=False)

    stats = tracker.statistics()

    assert stats.contract_review_count == 2
    assert stats.legal_consultation_count == 1
    assert stats.document_generation_count == 1
    assert stats.average_response_time == pytest.approx(2.5)


def test_usage_measure_logs_failure_and_reraises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = UsageTracker(tmp_path / "usage.db")
    messages = []
    monkeypatch.setattr("analytics.usage_tracker.log_exception", lambda context, exc: messages.append((context, str(exc))))

    with pytest.raises(RuntimeError, match="boom"):
        with tracker.measure(EVENT_LEGAL_CONSULTATION):
            raise RuntimeError("boom")

    assert messages == [("core_operation_failed event_type=legal_consultation", "boom")]
    assert tracker.statistics().legal_consultation_count == 0
