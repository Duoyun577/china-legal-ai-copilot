"""可切换 LLM Provider 的统一客户端门面。

当前默认使用 MockProvider；真实模型适配器仅定义接口，不执行网络调用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ai.providers.base_provider import BaseProvider
from ai.providers.deepseek_provider import DeepSeekProvider
from ai.providers.mock_provider import MockProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.providers.qwen_provider import QwenProvider


@dataclass(frozen=True)
class LLMMessage:
    """模型调用中的单条消息。"""

    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """兼容既有 AI 分析层的供应商无关响应。"""

    content: str
    model: str
    is_mock: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """既有业务层依赖的统一 complete 契约。"""

    def complete(self, messages: list[LLMMessage], *, response_format: str = "text") -> LLMResponse:
        ...


class ProviderLLMClient:
    """将统一的 complete 调用转换为可替换 Provider 调用。"""

    def __init__(self, provider: BaseProvider | str = "mock") -> None:
        self._provider = self._resolve_provider(provider)

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    def set_provider(self, provider: BaseProvider | str) -> None:
        """在运行时切换 Provider；切换不会自动建立网络连接。"""
        self._provider = self._resolve_provider(provider)

    def load_prompt(self, prompt_name: str, variables: dict[str, str] | None = None) -> str:
        """从 ai/prompts 加载 Prompt，并替换 ``{{variable}}`` 占位符。

        TODO: 增加 Prompt 版本、哈希、审计记录和环境配置。
        TODO: 接入 Prompt schema 校验，确保法律场景必需段落未被删除。
        """
        if Path(prompt_name).name != prompt_name or not prompt_name.endswith(".md"):
            raise ValueError("prompt_name 只能是 ai/prompts 下的 Markdown 文件名。")
        prompt_path = Path(__file__).resolve().parent / "prompts" / prompt_name
        if not prompt_path.is_file():
            raise FileNotFoundError(f"Prompt 不存在：{prompt_name}")
        prompt = prompt_path.read_text(encoding="utf-8")
        for key, value in (variables or {}).items():
            prompt = prompt.replace("{{" + key + "}}", value)
        return prompt

    def complete(self, messages: list[LLMMessage], *, response_format: str = "text") -> LLMResponse:
        prompt = "\n".join(f"{message.role}: {message.content}" for message in messages)
        is_mock = self._provider.provider_name == "mock"
        if response_format == "json":
            result = self._provider.chat_json(prompt)
            content = f"[MOCK:json] {json.dumps(result, ensure_ascii=False)}" if is_mock else json.dumps(result, ensure_ascii=False)
        else:
            content = self._provider.chat(prompt)
        return LLMResponse(
            content=content,
            model=f"{self._provider.provider_name}-provider",
            is_mock=is_mock,
            metadata={"provider": self._provider.provider_name, "response_format": response_format},
        )

    @staticmethod
    def _resolve_provider(provider: BaseProvider | str) -> BaseProvider:
        if not isinstance(provider, str):
            return provider
        provider = provider.lower().strip()
        providers = {
            "mock": MockProvider,
            "openai": OpenAIProvider,
            "deepseek": DeepSeekProvider,
            "qwen": QwenProvider,
        }
        if provider not in providers:
            raise ValueError(f"未知 LLM Provider：{provider}")
        return providers[provider]()


class MockLLMClient(ProviderLLMClient):
    """保留原有 MockLLMClient 名称的兼容包装。"""

    def __init__(self) -> None:
        super().__init__(provider="mock")
