from pathlib import Path
import sqlite3

import pytest

from analytics.usage_tracker import EVENT_CONTRACT_REVIEW, UsageQuotaExceeded, UsageTracker
from case_manager import CaseManager
from legal_assistant.analysis_cache import AnalysisCache
from security.auth import user_from_claims, user_id_for_email
from utils.database import _ConnectionProxy


def test_family_allowlist_and_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "owner@example.com, family@example.com")
    monkeypatch.setenv("ADMIN_USER_EMAILS", "owner@example.com")

    owner = user_from_claims({"email": "OWNER@example.com", "name": "Owner"})
    family = user_from_claims({"email": "family@example.com", "name": "Family"})

    assert owner is not None and owner.is_admin
    assert family is not None and not family.is_admin
    assert user_from_claims({"email": "stranger@example.com"}) is None
    assert owner.user_id == user_id_for_email("owner@example.com")


def test_expired_identity_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "owner@example.com")
    monkeypatch.setattr("security.auth.time.time", lambda: 1000)

    assert user_from_claims({"email": "owner@example.com", "exp": 999}) is None


def test_case_data_is_isolated_between_users(tmp_path: Path) -> None:
    database = tmp_path / "cases.db"
    alice = CaseManager(database, user_id="alice")
    bob = CaseManager(database, user_id="bob")
    alice_case = alice.create_case("Alice case", "A / B", "contract")
    bob_case = bob.create_case("Bob case", "C / D", "contract")
    alice_file = alice.save_file(alice_case.case_id, "generated_document", "alice.txt", b"private", "text/plain")

    assert [item.case_id for item in alice.list_cases()] == [alice_case.case_id]
    assert [item.case_id for item in bob.list_cases()] == [bob_case.case_id]
    with pytest.raises(KeyError):
        bob.get_case(alice_case.case_id)
    with pytest.raises(KeyError):
        bob.get_file_content(alice_file.file_id)


def test_analysis_cache_is_namespaced_by_user(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    alice = AnalysisCache(database, user_id="alice")
    bob = AnalysisCache(database, user_id="bob")
    payload = {"question": "private facts"}

    alice.set("consultation", payload, {"answer": "alice-only"})

    assert alice.get("consultation", payload) == {"answer": "alice-only"}
    assert bob.get("consultation", payload) is None


def test_per_user_quota_blocks_paid_operation(tmp_path: Path) -> None:
    tracker = UsageTracker(tmp_path / "usage.db", user_id="family", daily_limit=1, monthly_limit=2)
    tracker.record(EVENT_CONTRACT_REVIEW, 0.1)

    with pytest.raises(UsageQuotaExceeded, match="今日"):
        tracker.check_quota()


def test_admin_quota_exemption_and_visual_summary(tmp_path: Path) -> None:
    database = tmp_path / "usage.db"
    tracker = UsageTracker(
        database, user_id="owner", daily_limit=1, monthly_limit=1, quota_exempt=True,
    )
    tracker.register_user("owner@example.com", "Owner", is_admin=True)
    tracker.record(EVENT_CONTRACT_REVIEW, 0.1)

    tracker.check_quota()
    summary = tracker.admin_summary()

    assert summary[0]["email"] == "owner@example.com"
    assert summary[0]["total_calls"] == 1


def test_postgres_adapter_uses_native_placeholders_and_returning() -> None:
    class Cursor:
        def fetchone(self):
            return {"case_id": 7}

    class Connection:
        def __init__(self):
            self.statement = ""
            self.parameters = ()

        def execute(self, statement, parameters):
            self.statement = statement
            self.parameters = parameters
            return Cursor()

    connection = Connection()
    proxy = _ConnectionProxy(connection, postgres=True)
    cursor = proxy.execute("INSERT INTO cases (owner_id) VALUES (?)", ("family",))

    assert connection.statement == "INSERT INTO cases (owner_id) VALUES (%s) RETURNING case_id"
    assert connection.parameters == ("family",)
    assert cursor.lastrowid == 7


def test_usage_tracker_migrates_legacy_sqlite_schema(tmp_path: Path) -> None:
    database = tmp_path / "legacy-usage.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE usage_events ("
            "event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, "
            "duration_seconds REAL NOT NULL, succeeded INTEGER NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO usage_events (event_type, duration_seconds, succeeded) VALUES (?, ?, ?)",
            (EVENT_CONTRACT_REVIEW, 0.1, 1),
        )

    local_tracker = UsageTracker(database, user_id="local", daily_limit=10, monthly_limit=10)
    family_tracker = UsageTracker(database, user_id="family", daily_limit=10, monthly_limit=10)

    assert local_tracker.quota_status().daily_used == 1
    assert family_tracker.quota_status().daily_used == 0


def test_case_manager_migrates_legacy_sqlite_schema(tmp_path: Path) -> None:
    database = tmp_path / "legacy-cases.db"
    legacy_manager = CaseManager(database)
    legacy_case = legacy_manager.create_case("Legacy", "A / B", "contract")

    family_manager = CaseManager(database, user_id="family")

    assert legacy_manager.get_case(legacy_case.case_id).name == "Legacy"
    assert family_manager.list_cases() == []
