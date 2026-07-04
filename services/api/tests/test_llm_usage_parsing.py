"""Tests that OllamaClient/NetlifyAIGatewayClient extract real token counts from
their provider's own response, instead of the character-count guess this
replaced (see agent_loop/llm.py, docs ADR on agent-finops wiring)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_loop.llm import NetlifyAIGatewayClient, OllamaClient


class OllamaUsageParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_real_prompt_and_completion_counts(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: {
            "response": "market is up",
            "prompt_eval_count": 512,
            "eval_count": 128,
        }
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await OllamaClient(base_url="http://localhost:11434").complete("sys", "user")
        self.assertEqual(result.text, "market is up")
        self.assertEqual(result.prompt_tokens, 512)
        self.assertEqual(result.completion_tokens, 128)
        self.assertEqual(result.provider, "ollama")

    async def test_returns_zero_tokens_on_failure(self) -> None:
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=RuntimeError("down"))
            result = await OllamaClient().complete("sys", "user")
        self.assertIsNone(result.text)
        self.assertEqual(result.prompt_tokens, 0)
        self.assertEqual(result.completion_tokens, 0)


class NetlifyGatewayUsageParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_real_usage_from_openai_compatible_response(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: {
            "choices": [{"message": {"content": "content plan"}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 90},
        }
        client = NetlifyAIGatewayClient()
        client.base_url = "https://gateway.example"
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await client.complete("sys", "user")
        self.assertEqual(result.text, "content plan")
        self.assertEqual(result.prompt_tokens, 300)
        self.assertEqual(result.completion_tokens, 90)

    async def test_no_base_url_configured_returns_zero_tokens(self) -> None:
        client = NetlifyAIGatewayClient()
        client.base_url = None
        result = await client.complete("sys", "user")
        self.assertIsNone(result.text)
        self.assertEqual(result.prompt_tokens, 0)


if __name__ == "__main__":
    unittest.main()
