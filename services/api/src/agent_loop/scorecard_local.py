"""Local fallback copy of golden_eval_registry.scorecard — keep algorithms in sync with GER.

Used when golden-eval-registry is not installed on PYTHONPATH.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any


REQUIRED_HANDOFF_FIELDS = ("evidence", "constraints", "uncertainty")


@dataclass(frozen=True)
class ScorecardResult:
    """Five-dimensional collaboration vector + hard gates."""

    outcome: float
    coordination: float
    tool_use: float
    economics: float
    governance: float
    hard_gate_failures: tuple[str, ...] = ()
    components: dict[str, Any] = field(default_factory=dict)

    @property
    def release_ok(self) -> bool:
        return not self.hard_gate_failures

    @property
    def vector(self) -> dict[str, float]:
        return {
            "outcome": self.outcome,
            "coordination": self.coordination,
            "tool_use": self.tool_use,
            "economics": self.economics,
            "governance": self.governance,
        }

    def quality_score(self) -> int:
        """Communication scalar — never used alone for release."""
        if not self.release_ok:
            return min(40, int(round(100 * self._weighted())))
        return int(round(100 * self._weighted()))

    def _weighted(self) -> float:
        return (
            0.35 * self.outcome
            + 0.25 * self.coordination
            + 0.20 * self.tool_use
            + 0.10 * self.economics
            + 0.10 * self.governance
        )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def compute_css(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Component Synergy Score signals from structured trajectory evidence."""
    artifacts = list(trajectory.get("artifacts") or [])
    handoffs = list(trajectory.get("handoffs") or [])
    contradictions = list(trajectory.get("contradictions") or [])
    duplicates = list(trajectory.get("duplicate_work") or [])
    escalations = list(trajectory.get("escalations") or [])

    produced = 0
    consumed = 0
    orphans = 0
    for art in artifacts:
        produced += 1
        consumers = list(art.get("consumed_by") or [])
        if consumers:
            consumed += 1
        else:
            orphans += 1

    consumption_rate = 1.0 if produced == 0 else consumed / produced

    handoff_scores: list[float] = []
    for handoff in handoffs:
        preserved = set(handoff.get("preserved") or [])
        lost = set(handoff.get("lost") or [])
        required = set(handoff.get("required_fields") or REQUIRED_HANDOFF_FIELDS)
        if not required:
            required = set(REQUIRED_HANDOFF_FIELDS)
        ok = len(required & preserved) / len(required)
        if lost & required:
            ok = min(ok, 0.4)
        handoff_scores.append(ok)
    handoff_integrity = mean(handoff_scores) if handoff_scores else (0.85 if produced else 0.8)

    unresolved = [
        c for c in contradictions if not bool(c.get("resolved", False))
    ]
    contradiction_penalty = min(1.0, 0.35 * len(unresolved))
    duplicate_penalty = min(0.6, 0.2 * len(duplicates))

    escalation_ok = 1.0
    escalation_bypass = 0
    for esc in escalations:
        if bool(esc.get("required")) and not bool(esc.get("raised")):
            escalation_bypass += 1
            escalation_ok = 0.0

    synergy = _clamp(
        0.45 * consumption_rate
        + 0.35 * handoff_integrity
        + 0.20 * escalation_ok
        - contradiction_penalty
        - duplicate_penalty
    )

    return {
        "synergy_score": synergy,
        "artifact_consumption_rate": consumption_rate,
        "orphan_count": orphans,
        "duplicate_count": len(duplicates),
        "unresolved_contradiction_count": len(unresolved),
        "handoff_integrity": handoff_integrity,
        "escalation_bypass_count": escalation_bypass,
        "escalation_correctness": escalation_ok,
    }


def compute_tue(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Tool Utilization Efficacy — Sel / Arg / Exec / Out / Eff."""
    calls = list(trajectory.get("tool_calls") or [])
    if not calls:
        # Abstention when no tools needed is treated as perfect TUE (N/A → 1.0).
        return {
            "sel": 1.0,
            "arg": 1.0,
            "exec": 1.0,
            "out": 1.0,
            "eff": 1.0,
            "tue": 1.0,
            "call_count": 0,
            "unnecessary_count": 0,
        }

    sel = mean(1.0 if c.get("selected_correct", True) else 0.0 for c in calls)
    arg = mean(1.0 if c.get("args_valid", True) else 0.0 for c in calls)
    exe = mean(1.0 if c.get("executed", True) else 0.0 for c in calls)
    out = mean(1.0 if c.get("outcome_correct", True) else 0.0 for c in calls)
    unnecessary = sum(1 for c in calls if c.get("necessary") is False)
    eff = _clamp(1.0 - (unnecessary / len(calls)))

    # Geometric mean keeps a zeroed component visible.
    tue = (sel * arg * exe * out * eff) ** (1 / 5)

    expected_max = trajectory.get("economics", {}).get("expected_max_tool_calls")
    if expected_max is not None and len(calls) > int(expected_max):
        over = (len(calls) - int(expected_max)) / max(int(expected_max), 1)
        tue = _clamp(tue * (1.0 - min(0.5, 0.25 * over)))
        eff = _clamp(eff * (1.0 - min(0.5, 0.25 * over)))

    return {
        "sel": sel,
        "arg": arg,
        "exec": exe,
        "out": out,
        "eff": eff,
        "tue": tue,
        "call_count": len(calls),
        "unnecessary_count": unnecessary,
    }


def score_trajectory(trajectory: dict[str, Any]) -> ScorecardResult:
    """Score a multi-agent trajectory into a collaboration vector + hard gates."""
    outcome_block = dict(trajectory.get("outcome") or {})
    task_success = bool(outcome_block.get("task_success", False))
    state_verified = bool(outcome_block.get("state_verified", task_success))
    outcome = 1.0 if (task_success and state_verified) else (0.5 if task_success else 0.0)

    css = compute_css(trajectory)
    tue = compute_tue(trajectory)

    economics = dict(trajectory.get("economics") or {})
    cost_ok = economics.get("cost_ok")
    if cost_ok is None:
        max_cost = economics.get("max_cost_usd")
        cost = economics.get("cost_usd")
        if max_cost is not None and cost is not None:
            cost_ok = float(cost) <= float(max_cost)
        else:
            cost_ok = True
    latency_ok = economics.get("latency_ok", True)
    economics_score = 1.0 if (cost_ok and latency_ok) else 0.45

    gov = dict(trajectory.get("governance") or {})
    policy_ok = bool(gov.get("policy_ok", True))
    approval_ok = bool(gov.get("approval_ok", True))
    governance_score = 1.0 if (policy_ok and approval_ok) else 0.35
    if gov.get("requires_human_review"):
        governance_score = min(governance_score, 0.75)

    hard: list[str] = []
    if css["unresolved_contradiction_count"] > 0:
        hard.append("unresolved_contradiction")
    if css["escalation_bypass_count"] > 0:
        hard.append("escalation_bypass")
    if gov.get("policy_violation"):
        hard.append("policy_violation")
    if any(
        c.get("critical") and not c.get("outcome_correct", True)
        for c in (trajectory.get("tool_calls") or [])
    ):
        hard.append("critical_tool_outcome")

    return ScorecardResult(
        outcome=_clamp(outcome),
        coordination=_clamp(float(css["synergy_score"])),
        tool_use=_clamp(float(tue["tue"])),
        economics=_clamp(economics_score),
        governance=_clamp(governance_score),
        hard_gate_failures=tuple(hard),
        components={"css": css, "tue": tue, "outcome": outcome_block, "governance": gov},
    )


def aggregate_trials(results: list[ScorecardResult]) -> dict[str, Any]:
    """Multi-trial reporting — distributions, not only averages."""
    if not results:
        return {
            "n": 0,
            "pass_at_least_one": 0.0,
            "pass_every_trial": 0.0,
            "mean_vector": {},
            "hard_gate_failure_rate": 0.0,
        }

    releases = [r.release_ok and r.outcome >= 1.0 for r in results]
    n = len(results)
    pass_at_least_one = 1.0 if any(releases) else 0.0
    pass_every = 1.0 if all(releases) else 0.0
    hard_rate = sum(1 for r in results if r.hard_gate_failures) / n

    mean_vector = {
        key: mean(r.vector[key] for r in results)
        for key in ("outcome", "coordination", "tool_use", "economics", "governance")
    }
    return {
        "n": n,
        "pass_at_least_one": pass_at_least_one,
        "pass_every_trial": pass_every,
        "mean_vector": mean_vector,
        "hard_gate_failure_rate": hard_rate,
        "quality_scores": [r.quality_score() for r in results],
    }
