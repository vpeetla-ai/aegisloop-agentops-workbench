"""Optional delegation to Venkat AI Platform orchestrators."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agent_loop.models import MissionRequest

logger = logging.getLogger(__name__)

MISSION_ORCHESTRATOR = {
    "research": "research",
    "content": "platform",
    "incident": "platform",
    "migration": "architecture",
    "security": "platform",
}


def vap_delegation_enabled() -> bool:
    return bool(os.getenv("VAP_API_BASE_URL")) and os.getenv("VAP_DELEGATION_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _mission_message(request: MissionRequest) -> str:
    payload = request.input
    return (
        f"Mission: {request.mission}\n"
        f"Topic: {payload.topic}\n"
        f"Audience: {payload.audience}\n"
        f"Region: {payload.region}\n"
        f"Horizon: {payload.horizon}\n"
        f"Sources: {payload.sources}"
    )


async def _fetch_agent_card(base: str, orchestrator: str) -> dict[str, Any] | None:
    """Real A2A discovery step — VAP's actual /orchestrators/{id}/agent-card
    endpoint (ADR-007), not a guess. Delegation only proceeds once the peer's
    own Agent Card confirms the orchestrator exists and what it does."""
    url = f"{base.rstrip('/')}/orchestrators/{orchestrator}/agent-card"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("A2A agent-card discovery failed for '%s': %s", orchestrator, exc)
        return None


async def delegate_to_vap(request: MissionRequest) -> dict[str, Any] | None:
    base = os.getenv("VAP_API_BASE_URL")
    if not vap_delegation_enabled() or not base:
        return None
    orchestrator = os.getenv("VAP_ORCHESTRATOR_ID") or MISSION_ORCHESTRATOR.get(request.mission, "platform")

    agent_card = await _fetch_agent_card(base, orchestrator)
    if agent_card is None:
        return None

    url = f"{base.rstrip('/')}/orchestrators/{orchestrator}/run"
    body = {"message": _mission_message(request), "notify_channels": []}
    headers = {"X-API-Key": api_key} if (api_key := os.getenv("VAP_API_KEY")) else {}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("VAP delegation failed: %s", exc)
        return None

    final = str(data.get("final") or "")
    return {
        "final_markdown": final,
        "vap_orchestrator": orchestrator,
        "vap_agent_card": {
            "name": agent_card.get("name"),
            "skills": [skill.get("id") for skill in agent_card.get("skills", [])],
        },
        "vap_intent": data.get("intent", ""),
        "vap_outputs": data.get("outputs", {}),
        "delegated": True,
        "a2a_protocol": True,
    }
