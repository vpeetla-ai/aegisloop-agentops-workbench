"""Record structured tool-call evidence for TUE scoring."""

from __future__ import annotations

from typing import Any

from agent_loop.models import AgentContext


def record_tool_call(
    context: AgentContext,
    *,
    tool: str,
    selected_correct: bool = True,
    args_valid: bool = True,
    executed: bool = True,
    outcome_correct: bool = True,
    necessary: bool = True,
    critical: bool = False,
    detail: str | None = None,
) -> None:
    """Append a TUE-shaped tool call onto context.artifacts['tool_calls']."""
    calls = context.artifacts.get("tool_calls")
    if not isinstance(calls, list):
        calls = []
        context.artifacts["tool_calls"] = calls
    entry: dict[str, Any] = {
        "tool": tool,
        "selected_correct": selected_correct,
        "args_valid": args_valid,
        "executed": executed,
        "outcome_correct": outcome_correct,
        "necessary": necessary,
        "critical": critical,
    }
    if detail:
        entry["detail"] = detail
    calls.append(entry)
