"""生产环境配置，统一从环境变量和项目根目录的 .env 读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name} 必须为正整数。") from exc
    if value <= 0:
        raise ValueError(f"环境变量 {name} 必须为正整数。")
    return value


def _boolean(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"环境变量 {name} 必须为 true 或 false。")


def _email_set(name: str) -> frozenset[str]:
    return frozenset(
        value.strip().lower()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    )


def _path(name: str, default: Path) -> Path:
    """Resolve a configurable path, keeping relative values project-local."""
    raw_value = os.getenv(name, "").strip()
    path = Path(raw_value).expanduser() if raw_value else default
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    """保持环境变量可在测试和部署进程中覆盖。"""

    @property
    def deepseek_api_key(self) -> str | None:
        value = os.getenv("DEEPSEEK_API_KEY", "").strip()
        return value or None

    @property
    def database_url(self) -> str | None:
        value = os.getenv("DATABASE_URL", "").strip()
        return value or None

    @property
    def max_upload_bytes(self) -> int:
        return _positive_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)

    @property
    def case_database_path(self) -> Path:
        return _path("CASE_DATABASE_PATH", PROJECT_ROOT / "data" / "cases.db")

    @property
    def usage_database_path(self) -> Path:
        return _path("USAGE_DATABASE_PATH", PROJECT_ROOT / "data" / "usage.db")

    @property
    def analysis_cache_database_path(self) -> Path:
        return _path("ANALYSIS_CACHE_DATABASE_PATH", PROJECT_ROOT / "data" / "analysis_cache.db")

    @property
    def family_auth_enabled(self) -> bool:
        return _boolean("FAMILY_AUTH_ENABLED", False)

    @property
    def allowed_user_emails(self) -> frozenset[str]:
        return _email_set("ALLOWED_USER_EMAILS")

    @property
    def admin_user_emails(self) -> frozenset[str]:
        return _email_set("ADMIN_USER_EMAILS")

    @property
    def daily_api_limit(self) -> int:
        return _positive_int("DAILY_API_LIMIT", 20)

    @property
    def monthly_api_limit(self) -> int:
        return _positive_int("MONTHLY_API_LIMIT", 300)

    allowed_upload_extensions: frozenset[str] = frozenset({".txt", ".docx", ".pdf"})
    allowed_upload_mime_types: frozenset[str] = frozenset({
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    })


settings = Settings()
