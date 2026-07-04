from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from re import sub

from agent_finops_client import FinOpsClient

from agent_loop.llm import CompletionResult, LLMClient
from agent_loop.models import AgentContext, AgentEvent

MISSION_BUDGET_USD = float(os.getenv("MISSION_BUDGET_USD", "2.00"))
# Stable scope (not the ephemeral per-mission run_id) so an operator can actually
# set a real budget on it ahead of time via agent-finops's PUT /v1/budget.
FINOPS_SCOPE_TYPE = "repo"
FINOPS_SCOPE_VALUE = "aegisloop-agentops-workbench"


@dataclass(frozen=True)
class AgentResult:
    detail: str
    artifact_keys: list[str]


class Agent(ABC):
    name: str
    task: str

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self._finops = FinOpsClient(
            base_url=os.getenv("AGENTFINOPS_API_URL"),
            api_key=os.getenv("AGENTFINOPS_API_KEY"),
        )

    async def __call__(self, context: AgentContext) -> AgentResult:
        self.emit(context, "running", f"{self.name} started.")
        result = await self.run(context)
        self.emit(context, "done", result.detail, result.artifact_keys)
        return result

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        ...

    def meter_llm(self, context: AgentContext, completion: CompletionResult) -> None:
        """Record real usage for a real LLM call (no-op for the local heuristic,
        which never makes one — prompt_tokens/completion_tokens stay 0).

        Two independent budget signals, either can halt the mission:
        - MISSION_BUDGET_USD: this mission run's own accumulated cost (local check)
        - agent-finops's own breach signal on the stable repo-wide scope, which an
          operator can set a real cross-mission budget on via PUT /v1/budget
        """
        if completion.prompt_tokens == 0 and completion.completion_tokens == 0:
            return
        result = self._finops.record_usage(
            scope_type=FINOPS_SCOPE_TYPE,
            scope_value=FINOPS_SCOPE_VALUE,
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
        )
        context.finops_cost_usd += result.cost_usd
        if result.breached or context.finops_cost_usd > MISSION_BUDGET_USD:
            context.finops_breached = True

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

