from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


MissionKind = Literal["research", "content", "incident", "migration", "security"]
RuntimeMode = Literal["local", "ollama", "gateway"]


class MissionInput(BaseModel):
    topic: str = Field(min_length=3)
    audience: str = Field(min_length=2)
    region: str = Field(min_length=2)
    horizon: str = Field(min_length=2)
    sources: str = Field(min_length=5)


class MissionRequest(BaseModel):
    mission: MissionKind
    mode: RuntimeMode = "local"
    loop_mode: Literal["closed", "open", "human"] = "closed"
    input: MissionInput
    run_id: str | None = None


class AgentEvent(BaseModel):
    agent: str
    status: Literal["queued", "running", "done", "failed"]
    task: str
    detail: str
    artifact_keys: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Evaluation(BaseModel):
    quality_score: int
    decision: str
    checks: dict[str, Literal["pass", "review", "fail"]]
    reasons: dict[str, str] = Field(default_factory=dict)
    source_coverage: dict[str, str] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    run_id: str
    mission: MissionKind
    runtime: str
    cost_usd: float = 0.0
    artifact_markdown: str
    artifacts: dict[str, Any]
    provider_status: dict[str, str] = Field(default_factory=dict)
    trace: list[AgentEvent]
    evaluation: Evaluation


class AgentContext(BaseModel):
    run_id: str
    request: MissionRequest
    artifacts: dict[str, Any] = Field(default_factory=dict)
    trace: list[AgentEvent] = Field(default_factory=list)
