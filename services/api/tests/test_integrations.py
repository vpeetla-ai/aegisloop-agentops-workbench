from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agent_loop.integrations.aegis_gateway import authorize_mission_ship, gateway_enabled
from agent_loop.integrations.vap_delegate import MISSION_ORCHESTRATOR, vap_delegation_enabled


class IntegrationFlagTests(unittest.TestCase):
    def test_gateway_disabled_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(gateway_enabled())
            self.assertFalse(vap_delegation_enabled())

    def test_mission_orchestrator_map(self) -> None:
        self.assertEqual(MISSION_ORCHESTRATOR["research"], "research")
        self.assertEqual(MISSION_ORCHESTRATOR["migration"], "architecture")


class GatewayAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_human_loop_without_gateway_still_requires_approval(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            authz = await authorize_mission_ship(case_id="run-1", mission="research", loop_mode="human")
            self.assertTrue(authz.requires_approval)


if __name__ == "__main__":
    unittest.main()
