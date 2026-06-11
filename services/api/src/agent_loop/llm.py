from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLMClient(Protocol):
    async def complete(self, system: str, user: str) -> str | None:
        ...


class LocalHeuristicLLM:
    """Zero-dollar deterministic fallback used when no model service is configured."""

    async def complete(self, system: str, user: str) -> str | None:
        return None


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    async def complete(self, system: str, user: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"{system}\n\n{user}",
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 700},
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return payload.get("response")
        except Exception:
            return None


class NetlifyAIGatewayClient:
    """OpenAI-compatible Netlify AI Gateway adapter.

    In Netlify, OPENAI_BASE_URL is injected when AI Gateway is enabled.
    For local FastAPI runs, set OPENAI_BASE_URL and OPENAI_API_KEY manually if
    you want to test this adapter outside Netlify.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.api_key = os.getenv("OPENAI_API_KEY", "netlify-gateway")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def complete(self, system: str, user: str) -> str | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return payload["choices"][0]["message"]["content"]
        except Exception:
            return None


def make_llm(mode: str) -> LLMClient:
    if mode == "ollama":
        return OllamaClient()
    if mode == "gateway":
        return NetlifyAIGatewayClient()
    return LocalHeuristicLLM()

