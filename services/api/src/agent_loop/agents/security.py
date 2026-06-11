from __future__ import annotations

from agent_loop.agents.base import Agent, AgentResult, bullet_list
from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext


class ThreatModelAgent(Agent):
    name = "Threat Model Agent"
    task = "Identify assets, actors, trust boundaries, and abuse paths."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["threats"] = [
            "Prompt injection through untrusted retrieved content",
            "Over-scoped connector permissions",
            "Secrets leakage through tool output or trace logs",
            "Missing audit trail for external actions",
        ]
        return AgentResult("Threat model generated.", ["threats"])


class ScannerAgent(Agent):
    name = "Scanner Agent"
    task = "Find dependency, configuration, and secret exposure risks."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["scan_findings"] = [
            "Separate trusted and untrusted RAG sources",
            "Block secrets from prompt context",
            "Review write-capable connector scopes",
        ]
        return AgentResult("Security scan findings produced.", ["scan_findings"])


class PolicyAgent(Agent):
    name = "Policy Agent"
    task = "Map findings to controls, permissions, exceptions, and approval gates."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["policy_controls"] = [
            "Block destructive actions by default",
            "Require approval for external writes",
            "Persist trace for every tool call",
            "Use idempotency keys for repeated actions",
        ]
        return AgentResult("Policy controls mapped.", ["policy_controls"])


class RemediationAgent(Agent):
    name = "Remediation Agent"
    task = "Prioritize fixes with owners and verification evidence."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        context.artifacts["final_markdown"] = f"""# Security Review: {mission.topic}

**Audience:** {mission.audience}  
**Scope:** {mission.region}  
**Horizon:** {mission.horizon}

## Threats
{bullet_list(context.artifacts["threats"])}

## Scan findings
{bullet_list(context.artifacts["scan_findings"])}

## Policy controls
{bullet_list(context.artifacts["policy_controls"])}

## Launch gate
Approve only after tool scopes are minimized, prompt-injection tests pass, and every external action has traceable human approval or deterministic policy allowance.
"""
        return AgentResult("Security review generated.", ["final_markdown"])


def security_agents(llm: LLMClient) -> list[Agent]:
    return [ThreatModelAgent(llm), ScannerAgent(llm), PolicyAgent(llm), RemediationAgent(llm)]

