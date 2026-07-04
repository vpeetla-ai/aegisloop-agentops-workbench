"""Tests for real A2A discovery gating VAP delegation (see this repo's A2A ADR
and venkat-ai-platform's ADR-007). Delegation must call the peer's real
/orchestrators/{id}/agent-card before ever invoking /run — not guess."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agent_loop.integrations.vap_delegate import delegate_to_vap
from agent_loop.models import MissionInput, MissionRequest


def _request(mission: str = "research") -> MissionRequest:
    return MissionRequest(
        mission=mission,
        mode="local",
        loop_mode="closed",
        input=MissionInput(topic="test topic", audience="engineers", region="US", horizon="1w", sources="web docs"),
    )


class VapA2ADiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_delegation_skipped_when_disabled(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = await delegate_to_vap(_request())
        self.assertIsNone(result)

    async def test_delegation_never_calls_run_when_agent_card_discovery_fails(self) -> None:
        env = {"VAP_API_BASE_URL": "http://localhost:9", "VAP_DELEGATION_ENABLED": "true"}
        with patch.dict("os.environ", env, clear=True):
            with patch("agent_loop.integrations.vap_delegate._fetch_agent_card", AsyncMock(return_value=None)):
                with patch("httpx.AsyncClient.post", AsyncMock()) as mock_post:
                    result = await delegate_to_vap(_request())
        self.assertIsNone(result)
        mock_post.assert_not_called()

    async def test_delegation_runs_after_successful_agent_card_discovery(self) -> None:
        env = {"VAP_API_BASE_URL": "http://localhost:9", "VAP_DELEGATION_ENABLED": "true"}
        card = {"name": "Deep Research Pipeline", "skills": [{"id": "research"}]}
        run_response = AsyncMock()
        run_response.json = lambda: {"final": "brief text", "intent": "deep_research", "outputs": {}}
        run_response.raise_for_status = lambda: None
        with patch.dict("os.environ", env, clear=True):
            with patch("agent_loop.integrations.vap_delegate._fetch_agent_card", AsyncMock(return_value=card)):
                with patch("httpx.AsyncClient.post", AsyncMock(return_value=run_response)):
                    result = await delegate_to_vap(_request())
        assert result is not None
        self.assertTrue(result["a2a_protocol"])
        self.assertEqual(result["vap_agent_card"]["name"], "Deep Research Pipeline")
        self.assertEqual(result["final_markdown"], "brief text")


if __name__ == "__main__":
    unittest.main()
