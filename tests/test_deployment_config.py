from pathlib import Path

from app.health import health_status
from config.settings import PROJECT_ROOT, settings


def test_database_paths_can_be_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CASE_DATABASE_PATH", str(tmp_path / "cases.db"))
    monkeypatch.setenv("USAGE_DATABASE_PATH", "runtime/usage.db")
    monkeypatch.setenv("ANALYSIS_CACHE_DATABASE_PATH", "runtime/cache.db")

    assert settings.case_database_path == tmp_path / "cases.db"
    assert settings.usage_database_path == PROJECT_ROOT / "runtime" / "usage.db"
    assert settings.analysis_cache_database_path == PROJECT_ROOT / "runtime" / "cache.db"


def test_health_status() -> None:
    assert health_status() == {"status": "ok", "service": "china-legal-ai-copilot"}
