"""Aggregate mission metrics from persisted runs."""

from __future__ import annotations

from typing import Any


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def is_failed_run(run: dict[str, Any]) -> bool:
    if run.get("budget_exceeded"):
        return True
    trace = run.get("trace") or []
    if any(step.get("status") == "failed" for step in trace):
        return True
    checks = (run.get("evaluation") or {}).get("checks") or {}
    if any(status == "fail" for status in checks.values()):
        return True
    return False


def aggregate_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    latencies: list[float] = []
    failed = 0
    hard_gate_fails = 0
    release_ok = 0
    scored = 0
    coord_values: list[float] = []
    orphan_total = 0
    artifact_total = 0
    for run in runs:
        if is_failed_run(run):
            failed += 1
        artifacts = run.get("artifacts") or {}
        ms = artifacts.get("runtime_ms")
        if ms is not None:
            try:
                latencies.append(float(ms))
            except (TypeError, ValueError):
                pass
        scorecard = artifacts.get("scorecard") if isinstance(artifacts, dict) else None
        if isinstance(scorecard, dict):
            scored += 1
            if scorecard.get("release_ok"):
                release_ok += 1
            gates = scorecard.get("hard_gate_failures") or []
            if gates:
                hard_gate_fails += 1
            vector = scorecard.get("vector") or {}
            if "coordination" in vector:
                try:
                    coord_values.append(float(vector["coordination"]))
                except (TypeError, ValueError):
                    pass
            css = (scorecard.get("components") or {}).get("css") or {}
            orphan_total += int(css.get("orphan_count") or 0)
        traj = artifacts.get("collaboration_trajectory") if isinstance(artifacts, dict) else None
        if isinstance(traj, dict):
            artifact_total += len(traj.get("artifacts") or [])

    total = len(runs)
    return {
        "sample_size": total,
        "p50_ms": round(_percentile(latencies, 0.5), 2),
        "p95_ms": round(_percentile(latencies, 0.95), 2),
        "failure_rate_pct": round(100.0 * failed / total, 2) if total else 0.0,
        "failed": failed,
        "total": total,
        "collaboration": {
            "scored_runs": scored,
            "release_ok_rate": round(release_ok / scored, 3) if scored else None,
            "hard_gate_failure_rate": round(hard_gate_fails / scored, 3) if scored else None,
            "mean_coordination": round(sum(coord_values) / len(coord_values), 3) if coord_values else None,
            "orphan_count": orphan_total,
            "artifact_count": artifact_total,
        },
    }
