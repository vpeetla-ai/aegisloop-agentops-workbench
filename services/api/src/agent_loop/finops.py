"""FinOps helpers — token/cost estimates without requiring provider billing APIs."""

from __future__ import annotations

from agent_loop.models import AgentEvent

# Blended gpt-4o-mini style rate for portfolio demos (USD per token).
_GATEWAY_BLENDED_PER_TOKEN = 0.00000035


def estimate_mission_cost(
    mode: str,
    trace: list[AgentEvent],
    final_markdown: str,
    runtime_ms: int,
) -> float:
    if mode == "local":
        return 0.0
    if mode == "ollama":
        return 0.0
    if mode != "gateway":
        return 0.0

    output_chars = len(final_markdown)
    # Heuristic: gateway missions with long traces likely invoked the LLM several times.
    llm_heavy_agents = sum(1 for event in trace if event.status == "done" and len(event.detail) > 120)
    est_tokens = (output_chars // 4) + llm_heavy_agents * 650 + len(trace) * 80
    cost = est_tokens * _GATEWAY_BLENDED_PER_TOKEN
    # Penalize very slow runs in eval narrative only — cost stays token-based.
    _ = runtime_ms
    return round(cost, 6)
