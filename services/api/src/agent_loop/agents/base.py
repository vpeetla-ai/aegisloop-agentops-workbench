from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from re import sub

from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext, AgentEvent


@dataclass(frozen=True)
class AgentResult:
    detail: str
    artifact_keys: list[str]


class Agent(ABC):
    name: str
    task: str

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def __call__(self, context: AgentContext) -> AgentResult:
        self.emit(context, "running", f"{self.name} started.")
        result = await self.run(context)
        self.emit(context, "done", result.detail, result.artifact_keys)
        return result

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        ...

    def emit(self, context: AgentContext, status: str, detail: str, artifact_keys: list[str] | None = None) -> None:
        context.trace.append(
            AgentEvent(
                agent=self.name,
                status=status,  # type: ignore[arg-type]
                task=self.task,
                detail=detail,
                artifact_keys=artifact_keys or [],
            )
        )


def sentences(text: str) -> list[str]:
    return [item.strip() for item in sub(r"\s+", " ", text).split(".") if item.strip()]


def keywords(text: str, limit: int = 8) -> list[str]:
    stop = {
        "about",
        "after",
        "common",
        "from",
        "include",
        "into",
        "next",
        "service",
        "strong",
        "that",
        "this",
        "want",
        "with",
    }
    words = [word for word in sub(r"[^a-zA-Z0-9 ]", " ", text).lower().split() if len(word) > 3 and word not in stop]
    return [word for word, _ in Counter(words).most_common(limit)]


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)

