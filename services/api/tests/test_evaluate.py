from __future__ import annotations

import unittest

from agent_loop.models import AgentContext, AgentEvent, MissionInput, MissionRequest
from agent_loop.runtime import evaluate, extract_provider_status


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
            trace=[
                AgentEvent(
                    agent=f"A{i}",
                    status="done",
                    task="t",
                    detail="x" * 130,
                    artifact_keys=["notes"] if i == 0 else (["final_markdown"] if i == 8 else ["notes"]),
                )
                for i in range(9)
            ],
        )

    def test_passes_when_final_artifact_exists(self) -> None:
        evaluation = evaluate(self._context())
        self.assertEqual(evaluation.checks["Stop condition"], "pass")
        self.assertEqual(evaluation.checks["Coordination"], "pass")
        self.assertGreaterEqual(evaluation.quality_score, 85)
        self.assertIn("Ship", evaluation.decision)

    def test_human_loop_marks_policy_review(self) -> None:
        evaluation = evaluate(self._context(loop_mode="human"))
        self.assertEqual(evaluation.checks["Policy compliance"], "review")
        self.assertIn("Human approval", evaluation.decision)

    def test_unresolved_contradiction_blocks_ship(self) -> None:
        context = self._context()
        context.artifacts["contradictions"] = [
            {"agents": ["A0", "A1"], "topic": "eligibility", "resolved": False}
        ]
        evaluation = evaluate(context)
        self.assertEqual(evaluation.checks["Coordination"], "fail")
        self.assertIn("Block", evaluation.decision)
        self.assertLessEqual(evaluation.quality_score, 40)

    def test_escalation_bypass_blocks_ship(self) -> None:
        context = self._context()
        context.artifacts["escalations"] = [{"required": True, "raised": False, "signal": "low_confidence"}]
        evaluation = evaluate(context)
        self.assertIn("escalation", evaluation.decision.lower())
        self.assertLessEqual(evaluation.quality_score, 40)

    def test_provider_status_from_market_data(self) -> None:
        context = self._context(mission="research")
        context.artifacts["market_data"] = {"source_status": {"yahoo": "live", "bloomberg": "not_configured"}}
        status = extract_provider_status(context)
        self.assertEqual(status["yahoo"], "live")


if __name__ == "__main__":
    unittest.main()
