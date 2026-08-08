"""Build and score multi-agent collaboration trajectories for AegisLoop.

Prefers golden-eval-registry.scorecard when installed (CI); ships a compatible
local scorer so the runtime stays usable without the sibling checkout.
"""

from __future__ import annotations

from typing import Any

from agent_loop.models import AgentContext

try:
    from golden_eval_registry.scorecard import ScorecardResult, score_trajectory
except ImportError:  # pragma: no cover - local fallback when GER not on path
    from agent_loop.scorecard_local import ScorecardResult, score_trajectory


def build_trajectory(context: AgentContext) -> dict[str, Any]:
    """Derive a scorecard trajectory from mission artifacts + agent events."""
    producers: dict[str, str] = {}
    consumers: dict[str, list[str]] = {}
    agent_order: list[str] = []

    for event in context.trace:
        if event.agent not in agent_order:
            agent_order.append(event.agent)
        for key in event.artifact_keys:
            if key not in producers:
                producers[key] = event.agent
            else:
                consumers.setdefault(key, [])
                if event.agent != producers[key] and event.agent not in consumers[key]:
                    consumers[key].append(event.agent)

    skip_keys = {
        "runtime_ms",
        "lineage",
        "gateway",
        "telemetry_spans",
        "collaboration_trajectory",
        "scorecard",
        "market_data",
        "source_status",
        "tool_calls",
        "contradictions",
        "duplicate_work",
        "escalations",
        "handoffs",
    }
    default_producer = agent_order[0] if agent_order else "system"
    for key in context.artifacts:
        if key in skip_keys:
            continue
        if key not in producers:
            producers[key] = default_producer

    explicit = context.artifacts.get("collaboration_trajectory")
    if isinstance(explicit, dict):
        merged = dict(explicit)
        merged.setdefault("workflow_id", context.run_id)
        if "artifacts" not in merged:
            merged["artifacts"] = [
                {
                    "id": key,
                    "produced_by": producer,
                    "consumed_by": list(consumers.get(key) or []),
                }
                for key, producer in producers.items()
            ]
        return merged

    if context.artifacts.get("final_markdown") and "final_markdown" in producers:
        sinks = consumers.setdefault("final_markdown", [])
        if "ship" not in sinks:
            sinks.append("ship")

    artifacts = [
        {
            "id": key,
            "produced_by": producer,
            "consumed_by": list(consumers.get(key) or []),
        }
        for key, producer in producers.items()
    ]

    tool_calls = [t for t in (context.artifacts.get("tool_calls") or []) if isinstance(t, dict)]
    contradictions = [c for c in (context.artifacts.get("contradictions") or []) if isinstance(c, dict)]
    duplicates = [d for d in (context.artifacts.get("duplicate_work") or []) if isinstance(d, dict)]
    escalations = [e for e in (context.artifacts.get("escalations") or []) if isinstance(e, dict)]

    handoffs: list[dict[str, Any]] = []
    raw_hand = context.artifacts.get("handoffs")
    if isinstance(raw_hand, list):
        handoffs = [h for h in raw_hand if isinstance(h, dict)]
    elif len(agent_order) >= 2:
        for left, right in zip(agent_order, agent_order[1:]):
            handoffs.append(
                {
                    "from": left,
                    "to": right,
                    "preserved": ["evidence", "constraints", "uncertainty"],
                    "lost": [],
                }
            )

    runtime_ms = int(context.artifacts.get("runtime_ms", 0) or 0)
    latency_ok = runtime_ms == 0 or runtime_ms < 120_000
    has_final = bool(context.artifacts.get("final_markdown"))

    gateway = context.artifacts.get("gateway")
    policy_ok = True
    approval_ok = True
    policy_violation = False
    if isinstance(gateway, dict):
        decision = str(gateway.get("decision", "")).lower()
        if decision in {"deny", "denied", "block", "blocked"}:
            policy_ok = False
            policy_violation = True
        if gateway.get("requires_approval") and context.request.loop_mode != "human":
            approval_ok = False

    return {
        "workflow_id": context.run_id,
        "outcome": {
            "task_success": has_final,
            "state_verified": has_final,
        },
        "artifacts": artifacts,
        "handoffs": handoffs,
        "contradictions": contradictions,
        "duplicate_work": duplicates,
        "escalations": escalations,
        "tool_calls": tool_calls,
        "economics": {
            "cost_usd": float(context.finops_cost_usd or 0.0),
            "max_cost_usd": None,
            "latency_ok": latency_ok,
            "cost_ok": not context.finops_breached,
        },
        "governance": {
            "policy_ok": policy_ok,
            "approval_ok": approval_ok,
            "policy_violation": policy_violation,
            "requires_human_review": context.request.loop_mode == "human",
        },
    }


def score_context(context: AgentContext) -> ScorecardResult:
    return score_trajectory(build_trajectory(context))
