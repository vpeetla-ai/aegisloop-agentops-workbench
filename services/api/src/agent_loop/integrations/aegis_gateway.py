"""AegisAI governance gateway for AgentOps missions."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayAuthz:
    allowed: bool
    requires_approval: bool
    blocked: bool
    decision: str
    reason: str
    case_id: str | None = None
    raw: dict[str, Any] | None = None


def gateway_enabled() -> bool:
    return bool(os.getenv("AEGISAI_API_BASE_URL")) and os.getenv("AEGISAI_GATEWAY_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def authorize_mission_ship(*, case_id: str, mission: str, loop_mode: str) -> GatewayAuthz:
    if loop_mode != "human":
        return GatewayAuthz(
            allowed=True,
            requires_approval=False,
            blocked=False,
            decision="allow",
            reason="loop_mode_not_human",
            case_id=case_id,
        )
    if not gateway_enabled():
        return GatewayAuthz(
            allowed=True,
            requires_approval=True,
            blocked=False,
            decision="approval_required",
            reason="gateway_disabled_local_human_mode",
            case_id=case_id,
        )

    payload = {
        "tenant_id": os.getenv("AEGISAI_TENANT_ID", "bank-demo"),
        "agent_id": os.getenv("AEGISAI_AGENT_ID", "aegisloop-agentops"),
        "principal_id": os.getenv("AEGISAI_PRINCIPAL_ID", "agentops-orchestrator"),
        "tool_name": "mission.ship_artifact",
        "action_type": "ship",
        "target_system": mission,
        "amount_usd": 0.0,
        "data_classification": "internal",
        "reversible": True,
        "customer_impact": False,
        "grounding_score": 0.9,
        "safety_score": 0.9,
        "policy_compliance_score": 0.9,
        "case_id": case_id,
        "proposal_id": case_id,
    }
    headers = {"Content-Type": "application/json"}
    if bearer := os.getenv("AEGISAI_AUTH_BEARER"):
        headers["Authorization"] = f"Bearer {bearer}"
    if principal := os.getenv("AEGISAI_PRINCIPAL_ID", "agentops-orchestrator"):
        headers["X-AegisAI-Principal"] = principal
    if tenant := os.getenv("AEGISAI_TENANT_ID", "bank-demo"):
        headers["X-AegisAI-Tenant"] = tenant
    headers["X-AegisAI-Roles"] = os.getenv("AEGISAI_ROLES", "workflow_owner,execution_broker")

    url = f"{os.environ['AEGISAI_API_BASE_URL'].rstrip('/')}/api/gateway/tool-request"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("AegisAI gateway unreachable: %s", exc)
        if os.getenv("AEGISAI_GATEWAY_FAIL_OPEN", "true").lower() in {"1", "true", "yes", "on"}:
            return GatewayAuthz(
                allowed=True,
                requires_approval=True,
                blocked=False,
                decision="approval_required",
                reason=f"gateway_error_fail_open:{exc}",
                case_id=case_id,
            )
        return GatewayAuthz(
            allowed=False,
            requires_approval=False,
            blocked=True,
            decision="block",
            reason=f"gateway_error:{exc}",
            case_id=case_id,
        )

    decision = str(data.get("gateway_decision", "block"))
    token = data.get("execution_token")
    allowed = decision == "allow" and bool(token)
    requires_approval = decision == "approval_required"
    blocked = decision in {"block", "deny", "frozen"}
    return GatewayAuthz(
        allowed=allowed,
        requires_approval=requires_approval,
        blocked=blocked,
        decision=decision,
        reason=str(data.get("business_explanation", decision)),
        case_id=str(data.get("case_id") or case_id),
        raw=data,
    )
