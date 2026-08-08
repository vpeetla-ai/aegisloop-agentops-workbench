"""Multi-trial collaboration consistency helpers for CI gates."""

from __future__ import annotations

from typing import Any, Callable

from agent_loop.collab_eval import score_context
from agent_loop.models import AgentContext

try:
    from golden_eval_registry.scorecard import aggregate_trials
except ImportError:  # pragma: no cover
    from agent_loop.scorecard_local import aggregate_trials


def run_multi_trial(
    build_context: Callable[[int], AgentContext],
    *,
    n: int = 5,
) -> dict[str, Any]:
    """Score n contexts and aggregate pass_every_trial / hard-gate rate."""
    results = []
    for i in range(n):
        context = build_context(i)
        results.append(score_context(context))
    summary = aggregate_trials(results)
    summary["trials"] = [
        {
            "release_ok": r.release_ok,
            "quality_score": r.quality_score(),
            "vector": r.vector,
            "hard_gate_failures": list(r.hard_gate_failures),
        }
        for r in results
    ]
    return summary
