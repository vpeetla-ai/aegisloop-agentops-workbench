from __future__ import annotations

import unittest

from agent_loop.models import AgentContext, AgentEvent, MissionInput, MissionRequest
from agent_loop.runtime import evaluate, extract_provider_status
from agent_loop.finops import estimate_mission_cost


class EvaluateTests(unittest.TestCase):
    def _context(self, mission: str = "incident", loop_mode: str = "closed") -> AgentContext:
        return AgentContext(
            run_id="run-1",
            request=MissionRequest(
                mission=mission,  # type: ignore[arg-type]
                mode="local",
                loop_mode=loop_mode,  # type: ignore[arg-type]
                input=MissionInput(
                    topic="test topic",
                    audience="engineers",
                    region="us",
                    horizon="today",
                    sources="public feeds",
                ),
            ),
            artifacts={"final_markdown": "# Brief\nDone.", "runtime_ms": 1200},
            trace=[AgentEvent(agent=f"A{i}", status="done", task="t", detail="x" * 130) for i in range(9)],
        )

    def test_passes_when_final_artifact_exists(self) -> None:
        evaluation = evaluate(self._context())
        self.assertEqual(evaluation.checks["Stop condition"], "pass")
        self.assertGreaterEqual(evaluation.quality_score, 90)

    def test_human_loop_marks_policy_review(self) -> None:
        evaluation = evaluate(self._context(loop_mode="human"))
        self.assertEqual(evaluation.checks["Policy compliance"], "review")
        self.assertIn("Human approval", evaluation.decision)

    def test_provider_status_from_market_data(self) -> None:
        context = self._context(mission="research")
        context.artifacts["market_data"] = {"source_status": {"yahoo": "live", "bloomberg": "not_configured"}}
        status = extract_provider_status(context)
        self.assertEqual(status["yahoo"], "live")


class FinOpsTests(unittest.TestCase):
    def test_local_mode_is_zero_cost(self) -> None:
        cost = estimate_mission_cost("local", [], "# Brief", 1000)
        self.assertEqual(cost, 0.0)

    def test_gateway_mode_estimates_nonzero(self) -> None:
        trace = [AgentEvent(agent="A", status="done", task="t", detail="x" * 200)]
        cost = estimate_mission_cost("gateway", trace, "# " + ("word " * 400), 5000)
        self.assertGreater(cost, 0.0)


if __name__ == "__main__":
    unittest.main()
