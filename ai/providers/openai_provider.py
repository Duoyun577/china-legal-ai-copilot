"""OpenAI Provider 接口占位。"""

from __future__ import annotations

from typing import Any

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    """未来接入 OpenAI Chat Completions 或 Responses API。"""

    provider_name = "openai"

    def chat(self, prompt: str) -> str:
        """TODO: 注入 API 客户端、模型、超时、重试和安全配置。"""
        raise NotImplementedError("OpenAI API provider is not connected yet.")

    def chat_json(self, prompt: str) -> dict[str, Any]:
        """TODO: 使用供应商结构化输出并通过 output_validator 校验。"""
        raise NotImplementedError("OpenAI API provider is not connected yet.")
