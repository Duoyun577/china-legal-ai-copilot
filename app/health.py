"""Deployment health status shared by checks and tests."""

from __future__ import annotations

from typing import Any


def health_status() -> dict[str, Any]:
    """Return a dependency-free liveness payload without touching business data."""
    return {"status": "ok", "service": "china-legal-ai-copilot"}
