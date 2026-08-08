"""CI gate: multi_agent.collaboration_v1 suite from golden-eval-registry."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

try:
    from golden_eval_registry.runner import score_suite
    from golden_eval_registry.schema import parse_manifest
    from golden_eval_registry.validate import load_jsonl

    GOLDEN_EVAL_REGISTRY_AVAILABLE = True
except ImportError:
    GOLDEN_EVAL_REGISTRY_AVAILABLE = False

REGISTRY_PATH = Path(os.getenv("GOLDEN_EVAL_REGISTRY_PATH", "../../../golden-eval-registry")).resolve()
SUITE_DIR = REGISTRY_PATH / "suites" / "multi_agent_collaboration_v1"


@unittest.skipUnless(
    GOLDEN_EVAL_REGISTRY_AVAILABLE and SUITE_DIR.exists(),
    "golden-eval-registry not available — set GOLDEN_EVAL_REGISTRY_PATH or run in CI",
)
class CollaborationScorecardGateTests(unittest.TestCase):
    def test_multi_agent_collaboration_v1_suite_passes(self) -> None:
        manifest = parse_manifest(SUITE_DIR / "manifest.json")
        cases = load_jsonl(manifest.cases_path)
        actual_by_id = {str(c["id"]): {"trajectory": c["trajectory"]} for c in cases}
        result = score_suite(manifest, cases, actual_by_id)
        failures = "\n".join(f"{f.case_id}: {f.detail}" for f in result.failures)
        self.assertTrue(result.passed, f"collaboration scorecard regressions:\n{failures}")


if __name__ == "__main__":
    unittest.main()
