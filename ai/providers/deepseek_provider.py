"""DeepSeek API provider."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from config.settings import settings
from .base_provider import BaseProvider


class DeepSeekProviderError(RuntimeError):
    """Raised when a DeepSeek request cannot produce a valid response."""


class DeepSeekProvider(BaseProvider):
    """Provider for DeepSeek's OpenAI-compatible chat completions API."""

    provider_name = "deepseek"
    api_url = "https://api.deepseek.com/chat/completions"

    def __init__(self, *, model: str = "deepseek-chat", timeout: float = 60.0) -> None:
        self.model = model
        self.timeout = timeout

    def chat(self, prompt: str) -> str:
        data = self._request(prompt)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekProviderError("DeepSeek API 返回格式错误：缺少回复内容") from exc
        if not isinstance(content, str):
            raise DeepSeekProviderError("DeepSeek API 返回格式错误：回复内容不是字符串")
        return content

    def chat_json(self, prompt: str) -> dict[str, Any]:
        content = self.chat(prompt)
        try:
            result = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            result = self._extract_json_object(content)

        if result is None:
            raise DeepSeekProviderError("DeepSeek 回复 JSON 解析失败")
        if not isinstance(result, dict):
            raise DeepSeekProviderError("DeepSeek 回复 JSON 解析失败：顶层必须是对象")
        return result

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any] | None:
        """Extract the first JSON object from Markdown or explanatory text."""
        decoder = json.JSONDecoder()
        fenced_blocks = re.findall(
            r"```(?:json)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL
        )

        for candidate in [*fenced_blocks, content]:
            for match in re.finditer(r"\{", candidate):
                try:
                    result, _ = decoder.raw_decode(candidate, match.start())
                except json.JSONDecodeError:
                    continue
                if isinstance(result, dict):
                    return result
        return None

    def _request(self, prompt: str) -> dict[str, Any]:
        api_key = settings.deepseek_api_key
        if not api_key:
            raise DeepSeekProviderError("缺少环境变量 DEEPSEEK_API_KEY")

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DeepSeekProviderError(f"DeepSeek API 网络错误：{exc}") from exc

        if not response.ok:
            detail = response.text.strip()[:500]
            suffix = f"：{detail}" if detail else ""
            raise DeepSeekProviderError(
                f"DeepSeek API 返回错误（HTTP {response.status_code}）{suffix}"
            )

        try:
            data = response.json()
        except (requests.exceptions.JSONDecodeError, ValueError) as exc:
            raise DeepSeekProviderError("DeepSeek API 响应 JSON 解析失败") from exc
        if not isinstance(data, dict):
            raise DeepSeekProviderError("DeepSeek API 返回格式错误：顶层必须是对象")
        return data
