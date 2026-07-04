from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class CompletionResult:
    """Real completion + real usage — provider/model/tokens feed agent-finops
    metering directly, no guessing from output length."""

    text: str | None
    provider: str = "local"
    model: str = "heuristic"
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    async def complete(self, system: str, user: str) -> CompletionResult:
        ...


class LocalHeuristicLLM:
    """Zero-dollar deterministic fallback used when no model service is configured."""

    async def complete(self, system: str, user: str) -> CompletionResult:
        return CompletionResult(text=None, provider="local", model="heuristic")


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    async def complete(self, system: str, user: str) -> CompletionResult:
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
                return CompletionResult(
                    text=payload.get("response"),
                    provider="ollama",
                    model=self.model,
                    # Real counts from Ollama's own response — genuinely free (local
                    # model), but metered honestly rather than assumed zero-cost-so-
                    # untracked.
                    prompt_tokens=int(payload.get("prompt_eval_count") or 0),
                    completion_tokens=int(payload.get("eval_count") or 0),
                )
        except Exception:
            return CompletionResult(text=None, provider="ollama", model=self.model)


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

    async def complete(self, system: str, user: str) -> CompletionResult:
        if not self.base_url:
            return CompletionResult(text=None, provider="gateway", model=self.model)
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
                usage = payload.get("usage") or {}
                return CompletionResult(
                    text=payload["choices"][0]["message"]["content"],
                    provider="gateway",
                    model=self.model,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                )
        except Exception:
            return CompletionResult(text=None, provider="gateway", model=self.model)


def make_llm(mode: str) -> LLMClient:
    if mode == "ollama":
        return OllamaClient()
    if mode == "gateway":
        return NetlifyAIGatewayClient()
    return LocalHeuristicLLM()
