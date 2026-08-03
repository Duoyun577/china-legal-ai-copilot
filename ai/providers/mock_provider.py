"""离线 Mock Provider。"""

from __future__ import annotations

from typing import Any

from .base_provider import BaseProvider


class MockProvider(BaseProvider):
    """确定性、不联网的 Provider，供开发和测试使用。"""

    provider_name = "mock"

    def chat(self, prompt: str) -> str:
        return f"[MOCK:text] {prompt[:200]}"

    def chat_json(self, prompt: str) -> dict[str, Any]:
        return {"provider": self.provider_name, "mock": True, "prompt_preview": prompt[:200]}
