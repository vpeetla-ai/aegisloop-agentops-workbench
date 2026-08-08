"""Tests for tool-call recording helper."""

from __future__ import annotations

import unittest

from agent_loop.models import AgentContext, MissionInput, MissionRequest
from agent_loop.tool_calls import record_tool_call


class ToolCallTests(unittest.TestCase):
    def test_record_tool_call_appends_tue_shape(self) -> None:
        context = AgentContext(
            run_id="t1",
            request=MissionRequest(
                mission="research",
                mode="local",
                loop_mode="closed",
                input=MissionInput(
                    topic="markets",
                    audience="builders",
                    region="us",
                    horizon="today",
                    sources="public feeds",
                ),
            ),
        )
        record_tool_call(context, tool="fetch_market_snapshot", necessary=True)
        self.assertEqual(len(context.artifacts["tool_calls"]), 1)
        self.assertEqual(context.artifacts["tool_calls"][0]["tool"], "fetch_market_snapshot")
        self.assertTrue(context.artifacts["tool_calls"][0]["selected_correct"])


if __name__ == "__main__":
    unittest.main()
