"""CI: multi-trial consistency gate for collaboration scorecard (Stage-4)."""

from __future__ import annotations

import unittest

from agent_loop.models import AgentContext, AgentEvent, MissionInput, MissionRequest
from agent_loop.multi_trial import run_multi_trial


def _healthy_context(trial: int) -> AgentContext:
    return AgentContext(
        run_id=f"trial-{trial}",
        request=MissionRequest(
            mission="incident",
            mode="local",
            loop_mode="closed",
            input=MissionInput(
                topic="checkout latency",
                audience="engineers",
                region="us",
                horizon="today",
                sources="public feeds and metrics",
            ),
        ),
        artifacts={
            "final_markdown": f"# Brief trial {trial}\nDone.",
            "runtime_ms": 1000 + trial,
            "tool_calls": [
                {
                    "tool": "metrics_lookup",
                    "selected_correct": True,
                    "args_valid": True,
                    "executed": True,
                    "outcome_correct": True,
                    "necessary": True,
                }
            ],
        },
        trace=[
            AgentEvent(
                agent="Signal",
                status="done",
                task="normalize",
                detail="signals",
                artifact_keys=["signals"],
            ),
            AgentEvent(
                agent="Diagnosis",
                status="done",
                task="diagnose",
                detail="root cause",
                artifact_keys=["signals", "diagnosis"],
            ),
            AgentEvent(
                agent="Verifier",
                status="done",
                task="verify",
                detail="ok",
                artifact_keys=["diagnosis", "final_markdown"],
            ),
        ],
    )


def _flaky_context(trial: int) -> AgentContext:
    context = _healthy_context(trial)
    if trial % 2 == 1:
        context.artifacts["contradictions"] = [
            {"agents": ["Signal", "Diagnosis"], "topic": "root_cause", "resolved": False}
        ]
    return context


class MultiTrialGateTests(unittest.TestCase):
    def test_incident_pass_every_trial_on_healthy_fleet(self) -> None:
        summary = run_multi_trial(_healthy_context, n=5)
        self.assertEqual(summary["n"], 5)
        self.assertEqual(summary["pass_every_trial"], 1.0)
        self.assertEqual(summary["hard_gate_failure_rate"], 0.0)

    def test_flaky_contradiction_fails_pass_every_trial(self) -> None:
        summary = run_multi_trial(_flaky_context, n=4)
        self.assertEqual(summary["pass_at_least_one"], 1.0)
        self.assertEqual(summary["pass_every_trial"], 0.0)
        self.assertGreater(summary["hard_gate_failure_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
