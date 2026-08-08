from __future__ import annotations

import json
from time import perf_counter
from uuid import uuid4

from agent_loop.agents import content_agents, incident_agents, migration_agents, research_agents, security_agents
from agent_loop.collab_eval import build_trajectory, score_context
from agent_loop.integrations.aegis_gateway import authorize_mission_ship
from agent_loop.integrations.vap_delegate import delegate_to_vap
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
    """Collaboration-aware gate: vector scorecard + hard fails (not trace-length theater)."""
    provider_status = extract_provider_status(context)
    live_sources = sum(1 for status in provider_status.values() if status.startswith("live"))
    rate_limited = sum(1 for status in provider_status.values() if "rate_limited" in status)
    runtime_ms = int(context.artifacts.get("runtime_ms", 0) or 0)
    has_final = bool(context.artifacts.get("final_markdown"))

    scored = score_context(context)
    trajectory = build_trajectory(context)
    context.artifacts["collaboration_trajectory"] = trajectory
    context.artifacts["scorecard"] = {
        "vector": scored.vector,
        "hard_gate_failures": list(scored.hard_gate_failures),
        "release_ok": scored.release_ok,
        "components": scored.components,
        "quality_score": scored.quality_score(),
    }

    checks: dict[str, str] = {
        "Goal alignment": "pass" if scored.outcome >= 1.0 else ("review" if scored.outcome >= 0.5 else "fail"),
        "Evidence quality": (
            "pass"
            if len(context.artifacts) >= 3 and (context.request.mission != "research" or live_sources > 0)
            else "review"
        ),
        "Policy compliance": (
            "fail"
            if "policy_violation" in scored.hard_gate_failures
            else ("review" if context.request.loop_mode == "human" else "pass")
        ),
        "Cost and latency": "pass" if scored.economics >= 0.9 else "review",
        "Stop condition": "pass" if has_final else "fail",
        "Coordination": (
            "fail"
            if any(g in scored.hard_gate_failures for g in ("unresolved_contradiction", "escalation_bypass"))
            else ("pass" if scored.coordination >= 0.7 else "review")
        ),
        "Tool use": "pass" if scored.tool_use >= 0.7 else "review",
    }

    quality = scored.quality_score()
    if context.request.mission == "research" and rate_limited:
        quality = min(quality, 88)
    if runtime_ms >= 120_000:
        quality = min(quality, 80)

    if not scored.release_ok:
        gate = ", ".join(scored.hard_gate_failures)
        decision = f"Block: collaboration hard gate failed ({gate})"
    elif context.request.loop_mode == "human":
        decision = "Human approval required before ship"
    elif not has_final:
        decision = "Iterate: final artifact missing"
    elif scored.coordination < 0.55 or scored.tool_use < 0.55:
        decision = "Iterate: collaboration or tool-use below threshold"
    else:
        decision = "Ship: quality gate passed"

    css = scored.components.get("css") or {}
    tue = scored.components.get("tue") or {}
    reasons = {
        "Goal alignment": (
            "Final artifact exists and matches the mission contract."
            if has_final
            else "Final artifact missing."
        ),
        "Evidence quality": f"{live_sources} live/free data sources available; {rate_limited} provider paths rate-limited.",
        "Policy compliance": (
            "Human approval requested by loop mode."
            if context.request.loop_mode == "human"
            else "No unsafe external action was executed."
        ),
        "Cost and latency": f"Runtime {runtime_ms}ms; FinOps estimate attached to response cost_usd.",
        "Stop condition": "Loop stopped after final artifact and evaluation gate.",
        "Coordination": (
            f"CSS synergy={css.get('synergy_score', scored.coordination):.2f}; "
            f"orphans={css.get('orphan_count', 0)}; duplicates={css.get('duplicate_count', 0)}; "
            f"unresolved_contradictions={css.get('unresolved_contradiction_count', 0)}; "
            f"escalation_bypass={css.get('escalation_bypass_count', 0)}."
        ),
        "Tool use": (
            f"TUE={tue.get('tue', scored.tool_use):.2f} "
            f"(sel={tue.get('sel', 1):.2f} arg={tue.get('arg', 1):.2f} "
            f"exec={tue.get('exec', 1):.2f} out={tue.get('out', 1):.2f} eff={tue.get('eff', 1):.2f})."
        ),
    }
    return Evaluation(
        quality_score=quality,
        decision=decision,
        checks=checks,  # type: ignore[arg-type]
        reasons=reasons,
        source_coverage=provider_status,
    )


def extract_provider_status(context: AgentContext) -> dict[str, str]:
    market_data = context.artifacts.get("market_data")
    if isinstance(market_data, dict):
        status = market_data.get("source_status")
        if isinstance(status, dict):
            return {str(key): str(value) for key, value in status.items()}
    return {}


def build_lineage(context: AgentContext) -> dict[str, str | None]:
    gateway = context.artifacts.get("gateway")
    audit_case_id = None
    if isinstance(gateway, dict):
        audit_case_id = gateway.get("case_id")
    return {
        "run_id": context.run_id,
        "ecosystem": "aegisloop-agentops-workbench",
        "aegisai_audit_case_id": audit_case_id or context.artifacts.get("aegisai_audit_case_id"),
        "vap_orchestrator": context.artifacts.get("vap_orchestrator"),
    }


def build_response(context: AgentContext, started: float, telemetry: MissionTelemetry | None = None) -> MissionResponse:
    runtime_ms = round((perf_counter() - started) * 1000)
    context.artifacts["runtime_ms"] = runtime_ms
    context.artifacts["lineage"] = build_lineage(context)
    if telemetry is not None:
        context.artifacts["telemetry_spans"] = telemetry.spans
    final_markdown = context.artifacts.get("final_markdown", "")
    evaluation = evaluate(context)
    response = MissionResponse(
        run_id=context.run_id,
        mission=context.request.mission,
        runtime=f"uv-fastapi/{context.request.mode}",
        cost_usd=context.finops_cost_usd,
        budget_exceeded=context.finops_breached,
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

    delegated = await delegate_to_vap(request)
    if delegated:
        context.artifacts.update(delegated)
        context.trace.append(
            AgentEvent(
                agent="VAP Delegation",
                status="done",
                task="Delegate mission to Venkat AI Platform orchestrator.",
                detail=f"Delegated to {delegated.get('vap_orchestrator', 'platform')}.",
                artifact_keys=["final_markdown", "vap_orchestrator"],
            )
        )
    else:
        with telemetry.span("mission.run", mode=request.mode, loop_mode=request.loop_mode):
            for agent in build_fleet(request):
                with telemetry.span("agent.execute", agent=agent.name):
                    await agent(context)
                if context.finops_breached:
                    break

    gateway = await authorize_mission_ship(
        case_id=context.run_id,
        mission=request.mission,
        loop_mode=request.loop_mode,
    )
    context.artifacts["gateway"] = {
        "decision": gateway.decision,
        "requires_approval": gateway.requires_approval,
        "case_id": gateway.case_id,
        "reason": gateway.reason,
    }
    if gateway.case_id:
        context.artifacts["aegisai_audit_case_id"] = gateway.case_id

    response = build_response(context, started, telemetry)
    await telemetry.export_langfuse()
    await persist_run(response.model_dump())
    return response


async def stream_mission(request: MissionRequest):
    started = perf_counter()
    context = AgentContext(run_id=request.run_id or str(uuid4()), request=request)
    telemetry = MissionTelemetry(run_id=context.run_id, mission=request.mission)
    yield {"type": "run_started", "run_id": context.run_id, "mission": request.mission}

    delegated = await delegate_to_vap(request)
    if delegated:
        context.artifacts.update(delegated)
        event = AgentEvent(
            agent="VAP Delegation",
            status="done",
            task="Delegate mission to Venkat AI Platform orchestrator.",
            detail=f"Delegated to {delegated.get('vap_orchestrator', 'platform')}.",
            artifact_keys=["final_markdown", "vap_orchestrator"],
        )
        context.trace.append(event)
        yield {"type": "agent_event", "run_id": context.run_id, "event": event.model_dump()}
        yield {
            "type": "artifact_delta",
            "run_id": context.run_id,
            "artifact_keys": list(context.artifacts.keys()),
            "provider_status": extract_provider_status(context),
        }
    else:
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
                if context.finops_breached:
                    break

    gateway = await authorize_mission_ship(
        case_id=context.run_id,
        mission=request.mission,
        loop_mode=request.loop_mode,
    )
    context.artifacts["gateway"] = {
        "decision": gateway.decision,
        "requires_approval": gateway.requires_approval,
        "case_id": gateway.case_id,
        "reason": gateway.reason,
    }
    if gateway.case_id:
        context.artifacts["aegisai_audit_case_id"] = gateway.case_id

    response = build_response(context, started, telemetry)
    await telemetry.export_langfuse()
    await persist_run(response.model_dump())
    yield {"type": "run_completed", "run_id": context.run_id, "response": response.model_dump()}


def encode_stream_event(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"
