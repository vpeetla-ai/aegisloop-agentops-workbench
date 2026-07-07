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
    total = len(runs)
    return {
        "sample_size": total,
        "p50_ms": round(_percentile(latencies, 0.5), 2),
        "p95_ms": round(_percentile(latencies, 0.95), 2),
        "failure_rate_pct": round(100.0 * failed / total, 2) if total else 0.0,
        "failed": failed,
        "total": total,
    }
