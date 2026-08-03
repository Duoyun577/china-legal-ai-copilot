from __future__ import annotations

import unittest
from unittest.mock import patch

from ai.llm_client import ProviderLLMClient
from ai.providers.deepseek_provider import DeepSeekProvider, DeepSeekProviderError
from ai.providers.mock_provider import MockProvider


class DeepSeekProviderTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_has_clear_error(self) -> None:
        provider = DeepSeekProvider()
        with self.assertRaisesRegex(DeepSeekProviderError, "DEEPSEEK_API_KEY"):
            provider.chat("hello")

    def test_initialization(self) -> None:
        provider = DeepSeekProvider()
        self.assertEqual(provider.provider_name, "deepseek")
        self.assertEqual(provider.model, "deepseek-chat")

    @patch("ai.providers.deepseek_provider.requests.post")
    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "centralized-key"}, clear=True)
    def test_api_key_is_read_from_central_settings(self, post) -> None:
        post.return_value.ok = True
        post.return_value.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        DeepSeekProvider().chat("hello")

        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer centralized-key"

    def test_llm_client_resolves_deepseek(self) -> None:
        client = ProviderLLMClient(provider="deepseek")
        self.assertEqual(client.provider_name, "deepseek")

    def test_chat_json_parses_plain_json(self) -> None:
        provider = DeepSeekProvider()
        with patch.object(provider, "chat", return_value='{"a": 1}'):
            self.assertEqual(provider.chat_json("prompt"), {"a": 1})

    def test_chat_json_parses_markdown_json_block(self) -> None:
        provider = DeepSeekProvider()
        content = '```json\n{"a": 1}\n```'
        with patch.object(provider, "chat", return_value=content):
            self.assertEqual(provider.chat_json("prompt"), {"a": 1})

    def test_chat_json_parses_json_surrounded_by_explanation(self) -> None:
        provider = DeepSeekProvider()
        content = 'Here is the result:\n{"a": 1}\nThis is the requested object.'
        with patch.object(provider, "chat", return_value=content):
            self.assertEqual(provider.chat_json("prompt"), {"a": 1})

    def test_chat_json_rejects_content_without_json_object(self) -> None:
        provider = DeepSeekProvider()
        with patch.object(provider, "chat", return_value="no json here"):
            with self.assertRaises(DeepSeekProviderError):
                provider.chat_json("prompt")


class MockProviderTests(unittest.TestCase):
    def test_mock_provider_still_works(self) -> None:
        provider = MockProvider()
        self.assertEqual(provider.chat("hello"), "[MOCK:text] hello")
        self.assertTrue(provider.chat_json("hello")["mock"])
        self.assertEqual(ProviderLLMClient(provider="mock").provider_name, "mock")


if __name__ == "__main__":
    unittest.main()
