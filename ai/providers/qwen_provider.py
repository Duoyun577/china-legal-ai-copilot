"""通义千问（Qwen）Provider 接口占位。"""

from __future__ import annotations

from typing import Any

from .base_provider import BaseProvider


class QwenProvider(BaseProvider):
    """未来接入通义千问兼容接口。"""

    provider_name = "qwen"

    def chat(self, prompt: str) -> str:
        """TODO: 配置 DashScope/Qwen endpoint、模型和认证策略。"""
        raise NotImplementedError("Qwen API provider is not connected yet.")

    def chat_json(self, prompt: str) -> dict[str, Any]:
        """TODO: 接入 JSON mode、schema 校验与服务异常处理。"""
        raise NotImplementedError("Qwen API provider is not connected yet.")
