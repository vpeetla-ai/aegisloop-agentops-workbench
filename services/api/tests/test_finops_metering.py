"""Tests for real usage metering + budget-halt wiring — see docs/ADR for the
agent-finops consumer wiring. agent-finops's own budget math is tested in
that repo; these cover this repo's reaction to real/breached usage."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent_finops_client import UsageResult

from agent_loop.agents.base import Agent, AgentResult
from agent_loop.llm import CompletionResult, LocalHeuristicLLM
from agent_loop.models import AgentContext, MissionInput, MissionRequest


class _NoopAgent(Agent):
    name = "Test Agent"
    task = "test"

    async def run(self, context: AgentContext) -> AgentResult:
        return AgentResult("done", [])


def _context() -> AgentContext:
    return AgentContext(
        run_id="run-1",
        request=MissionRequest(
            mission="research",
            mode="gateway",
            loop_mode="closed",
            input=MissionInput(topic="test topic", audience="engineers", region="us", horizon="today", sources="public feeds"),
        ),
    )


class LocalHeuristicTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_llm_reports_zero_tokens(self) -> None:
        result = await LocalHeuristicLLM().complete("sys", "user")
        self.assertIsNone(result.text)
        self.assertEqual(result.prompt_tokens, 0)
        self.assertEqual(result.completion_tokens, 0)


class MeterLlmTests(unittest.TestCase):
    def test_zero_token_completion_is_not_metered(self) -> None:
        agent = _NoopAgent(LocalHeuristicLLM())
        context = _context()
        with patch.object(agent._finops, "record_usage") as mock_record:
            agent.meter_llm(context, CompletionResult(text=None, prompt_tokens=0, completion_tokens=0))
        mock_record.assert_not_called()
        self.assertEqual(context.finops_cost_usd, 0.0)

    def test_real_completion_accumulates_cost(self) -> None:
        agent = _NoopAgent(LocalHeuristicLLM())
        context = _context()
        with patch.object(
            agent._finops,
            "record_usage",
            return_value=UsageResult(cost_usd=0.5, total_cost_usd=0.5, budget_usd=None, breached=False),
        ):
            agent.meter_llm(
                context,
                CompletionResult(text="hi", provider="gateway", model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=200),
            )
        self.assertEqual(context.finops_cost_usd, 0.5)
        self.assertFalse(context.finops_breached)

    def test_agent_finops_breach_signal_halts(self) -> None:
        agent = _NoopAgent(LocalHeuristicLLM())
        context = _context()
        with patch.object(
            agent._finops,
            "record_usage",
            return_value=UsageResult(cost_usd=0.5, total_cost_usd=50.0, budget_usd=10.0, breached=True),
        ):
            agent.meter_llm(
                context,
                CompletionResult(text="hi", provider="gateway", model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=200),
            )
        self.assertTrue(context.finops_breached)

    def test_local_mission_budget_threshold_halts_even_without_agentfinops_breach(self) -> None:
        agent = _NoopAgent(LocalHeuristicLLM())
        context = _context()
        # agent-finops itself says not breached (no budget configured there), but
        # this mission's own accumulated cost already exceeds MISSION_BUDGET_USD.
        with patch("agent_loop.agents.base.MISSION_BUDGET_USD", 1.0):
            with patch.object(
                agent._finops,
                "record_usage",
                return_value=UsageResult(cost_usd=5.0, total_cost_usd=5.0, budget_usd=None, breached=False),
            ):
                agent.meter_llm(
                    context,
                    CompletionResult(text="hi", provider="gateway", model="gpt-4o-mini", prompt_tokens=100000, completion_tokens=1000),
                )
        self.assertTrue(context.finops_breached)


if __name__ == "__main__":
    unittest.main()
