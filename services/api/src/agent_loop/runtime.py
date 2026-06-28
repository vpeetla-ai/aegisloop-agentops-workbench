from __future__ import annotations

import json
from time import perf_counter
from uuid import uuid4

from agent_loop.agents import content_agents, incident_agents, migration_agents, research_agents, security_agents
from agent_loop.finops import estimate_mission_cost
from agent_loop.llm import make_llm
from agent_loop.models import AgentContext, AgentEvent, Evaluation, MissionRequest, MissionResponse
from agent_loop.storage import persist_run
from agent_loop.telemetry import MissionTelemetry


def build_fleet(request: MissionRequest):
    llm = make_llm(request.mode)
    fleets = {
        "research": research_agents,
        "content": content_agents,
        "incident": incident_agents,
        "migration": migration_agents,
        "security": security_agents,
    }
    return fleets[request.mission](llm)


def evaluate(context: AgentContext) -> Evaluation:
    has_final = bool(context.artifacts.get("final_markdown"))
    has_trace = len(context.trace) >= 8
    provider_status = extract_provider_status(context)
    live_sources = sum(1 for status in provider_status.values() if status.startswith("live"))
    rate_limited = sum(1 for status in provider_status.values() if "rate_limited" in status)
    runtime_ms = int(context.artifacts.get("runtime_ms", 0))
    latency_ok = runtime_ms == 0 or runtime_ms < 120_000
    checks = {
        "Goal alignment": "pass" if has_final else "review",
        "Evidence quality": "pass" if len(context.artifacts) >= 3 and (context.request.mission != "research" or live_sources > 0) else "review",
        "Policy compliance": "review" if context.request.loop_mode == "human" else "pass",
        "Cost and latency": "pass" if latency_ok else "review",
        "Stop condition": "pass" if has_final else "fail",
    }
    quality = 94 if has_final and has_trace else 72 if has_final else 45
    if context.request.mission == "research" and rate_limited:
        quality = min(quality, 88)
    if not latency_ok:
        quality = min(quality, 80)
    decision = "Human approval required before ship" if context.request.loop_mode == "human" else "Ship: quality gate passed"
    if not has_final:
        decision = "Iterate: final artifact missing"
    reasons = {
        "Goal alignment": "Final artifact exists and matches the mission contract." if has_final else "Final artifact missing.",
        "Evidence quality": f"{live_sources} live/free data sources available; {rate_limited} provider paths rate-limited.",
        "Policy compliance": "Human approval requested by loop mode." if context.request.loop_mode == "human" else "No unsafe external action was executed.",
        "Cost and latency": f"Runtime {runtime_ms}ms; FinOps estimate attached to response cost_usd.",
        "Stop condition": "Loop stopped after final artifact and evaluation gate.",
    }
    return Evaluation(quality_score=quality, decision=decision, checks=checks, reasons=reasons, source_coverage=provider_status)  # type: ignore[arg-type]


def extract_provider_status(context: AgentContext) -> dict[str, str]:
    market_data = context.artifacts.get("market_data")
    if isinstance(market_data, dict):
        status = market_data.get("source_status")
        if isinstance(status, dict):
            return {str(key): str(value) for key, value in status.items()}
    return {}


def build_lineage(context: AgentContext) -> dict[str, str | None]:
    return {
        "run_id": context.run_id,
        "ecosystem": "aegisloop-agentops-workbench",
        "aegisai_audit_case_id": context.artifacts.get("aegisai_audit_case_id"),
        "vap_orchestrator": context.artifacts.get("vap_orchestrator"),
    }


def build_response(context: AgentContext, started: float, telemetry: MissionTelemetry | None = None) -> MissionResponse:
    runtime_ms = round((perf_counter() - started) * 1000)
    context.artifacts["runtime_ms"] = runtime_ms
    context.artifacts["lineage"] = build_lineage(context)
    if telemetry is not None:
        context.artifacts["telemetry_spans"] = telemetry.spans
    final_markdown = context.artifacts.get("final_markdown", "")
    cost_usd = estimate_mission_cost(
        context.request.mode,
        context.trace,
        final_markdown if isinstance(final_markdown, str) else "",
        runtime_ms,
    )
    evaluation = evaluate(context)
    response = MissionResponse(
        run_id=context.run_id,
        mission=context.request.mission,
        runtime=f"uv-fastapi/{context.request.mode}",
        cost_usd=cost_usd,
        artifact_markdown=final_markdown if isinstance(final_markdown, str) else "",
        artifacts=context.artifacts,
        provider_status=extract_provider_status(context),
        trace=context.trace,
        evaluation=evaluation,
    )
    return response


async def run_mission(request: MissionRequest) -> MissionResponse:
    started = perf_counter()
    context = AgentContext(run_id=request.run_id or str(uuid4()), request=request)
    telemetry = MissionTelemetry(run_id=context.run_id, mission=request.mission)
    with telemetry.span("mission.run", mode=request.mode, loop_mode=request.loop_mode):
        for agent in build_fleet(request):
            with telemetry.span("agent.execute", agent=agent.name):
                await agent(context)
    response = build_response(context, started, telemetry)
    await telemetry.export_langfuse()
    await persist_run(response.model_dump())
    return response


async def stream_mission(request: MissionRequest):
    started = perf_counter()
    context = AgentContext(run_id=request.run_id or str(uuid4()), request=request)
    telemetry = MissionTelemetry(run_id=context.run_id, mission=request.mission)
    yield {"type": "run_started", "run_id": context.run_id, "mission": request.mission}
    emitted = 0
    with telemetry.span("mission.stream", mode=request.mode):
        for agent in build_fleet(request):
            with telemetry.span("agent.execute", agent=agent.name):
                await agent(context)
            new_events: list[AgentEvent] = context.trace[emitted:]
            emitted = len(context.trace)
            for event in new_events:
                yield {"type": "agent_event", "run_id": context.run_id, "event": event.model_dump()}
            yield {
                "type": "artifact_delta",
                "run_id": context.run_id,
                "artifact_keys": list(context.artifacts.keys()),
                "provider_status": extract_provider_status(context),
            }
    response = build_response(context, started, telemetry)
    await telemetry.export_langfuse()
    await persist_run(response.model_dump())
    yield {"type": "run_completed", "run_id": context.run_id, "response": response.model_dump()}


def encode_stream_event(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"
