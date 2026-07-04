from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from agent_loop.main import app


class MissionAuthTests(unittest.TestCase):
    """/api/missions/run and /api/missions/stream call a real LLM and cost real
    money per hit — see docs/ADR-* for the AEGISLOOP_API_KEY gate added after
    finding these had zero caller authentication."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_missions_run_open_when_no_api_key_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with patch("agent_loop.main.run_mission", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {"mission": "research"}
                resp = self.client.post(
                    "/api/missions/run",
                    json={
                        "mission": "research",
                        "input": {
                            "topic": "AI agents",
                            "audience": "execs",
                            "region": "US",
                            "horizon": "1yr",
                            "sources": "public web",
                        },
                    },
                )
        self.assertEqual(resp.status_code, 200)

    def test_missions_run_rejects_missing_key_when_required(self) -> None:
        with patch.dict("os.environ", {"AEGISLOOP_API_KEY": "secret-key"}, clear=False):
            resp = self.client.post(
                "/api/missions/run",
                json={
                    "mission": "research",
                    "input": {
                        "topic": "AI agents",
                        "audience": "execs",
                        "region": "US",
                        "horizon": "1yr",
                        "sources": "public web",
                    },
                },
            )
        self.assertEqual(resp.status_code, 401)

    def test_missions_run_accepts_correct_key(self) -> None:
        with patch.dict("os.environ", {"AEGISLOOP_API_KEY": "secret-key"}, clear=False):
            with patch("agent_loop.main.run_mission", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = {"mission": "research"}
                resp = self.client.post(
                    "/api/missions/run",
                    json={
                        "mission": "research",
                        "input": {
                            "topic": "AI agents",
                            "audience": "execs",
                            "region": "US",
                            "horizon": "1yr",
                            "sources": "public web",
                        },
                    },
                    headers={"X-API-Key": "secret-key"},
                )
        self.assertEqual(resp.status_code, 200)

    def test_health_stays_open_regardless_of_key(self) -> None:
        with patch.dict("os.environ", {"AEGISLOOP_API_KEY": "secret-key"}, clear=False):
            resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
