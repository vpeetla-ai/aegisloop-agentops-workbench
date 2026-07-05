"""Real merge gate: runs the shared `aegisloop_mission_gates_v1` suite from
vpeetla-ai/golden-eval-registry against this repo's real `evaluate()` gate
function (runtime.py) — closes that registry's own backlog item that
fixtures existed but nothing executed them as a CI gate.

Skips locally when the sibling registry repo isn't checked out; CI always
checks it out first (see .github/workflows/ci.yml / tests.yml).
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from agent_loop.models import AgentContext, AgentEvent, MissionInput, MissionRequest
from agent_loop.runtime import evaluate

try:
    from golden_eval_registry.runner import score_suite
    from golden_eval_registry.schema import parse_manifest
    from golden_eval_registry.validate import load_jsonl

    GOLDEN_EVAL_REGISTRY_AVAILABLE = True
except ImportError:
    GOLDEN_EVAL_REGISTRY_AVAILABLE = False

REGISTRY_PATH = Path(os.getenv("GOLDEN_EVAL_REGISTRY_PATH", "../../../golden-eval-registry")).resolve()
SUITE_DIR = REGISTRY_PATH / "suites" / "aegisloop_mission_gates_v1"


def _context_from_case(payload: dict) -> AgentContext:
    artifacts = dict(payload.get("artifacts") or {})
    trace_min_events = int(payload.get("trace_min_events", 8))
    return AgentContext(
        run_id="golden-eval-runner",
        request=MissionRequest(
            mission=payload["mission"],
            mode=payload.get("mode", "local"),
            loop_mode=payload.get("loop_mode", "closed"),
            input=MissionInput(
                topic="golden eval topic",
                audience="engineers",
                region="us",
                horizon="today",
                sources="public feeds",
            ),
        ),
        artifacts=artifacts,
        trace=[
            AgentEvent(agent=f"agent-{i}", status="done", task="task", detail="synthetic trace event")
            for i in range(trace_min_events)
        ],
    )


@unittest.skipUnless(
    GOLDEN_EVAL_REGISTRY_AVAILABLE and SUITE_DIR.exists(),
    "golden-eval-registry not available — set GOLDEN_EVAL_REGISTRY_PATH or run in CI",
)
class GoldenEvalGateTests(unittest.TestCase):
    def test_aegisloop_mission_gates_v1_suite_passes(self) -> None:
        manifest = parse_manifest(SUITE_DIR / "manifest.json")
        cases = load_jsonl(manifest.cases_path)

        actual_by_id: dict[str, dict] = {}
        for case in cases:
            context = _context_from_case(case["input"])
            evaluation = evaluate(context)
            actual_by_id[str(case["id"])] = {
                "checks": evaluation.checks,
                "quality_score": evaluation.quality_score,
                "decision": evaluation.decision,
            }

        result = score_suite(manifest, cases, actual_by_id)
        failures = "\n".join(f"{failure.case_id}: {failure.detail}" for failure in result.failures)
        self.assertTrue(result.passed, f"golden eval regressions:\n{failures}")


if __name__ == "__main__":
    unittest.main()
