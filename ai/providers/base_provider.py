"""LLM Provider 的统一抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """所有模型供应商适配器必须实现的最小接口。"""

    provider_name = "base"

    @abstractmethod
    def chat(self, prompt: str) -> str:
        """发送文本提示并返回文本结果。"""
        raise NotImplementedError

    @abstractmethod
    def chat_json(self, prompt: str) -> dict[str, Any]:
        """发送提示并返回 JSON 对象。"""
        raise NotImplementedError
