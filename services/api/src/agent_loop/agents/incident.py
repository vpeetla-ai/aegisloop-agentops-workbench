from __future__ import annotations

from agent_loop.agents.base import Agent, AgentResult, bullet_list, sentences
from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext


class SignalAgent(Agent):
    name = "Signal Agent"
    task = "Normalize alerts, logs, metrics, and customer impact."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["signals"] = sentences(context.request.input.sources)[:8]
        return AgentResult("Incident signals normalized.", ["signals"])


class DiagnosisAgent(Agent):
    name = "Diagnosis Agent"
    task = "Build and rank root-cause hypotheses."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["hypotheses"] = [
            "Cache stampede after a recent deploy",
            "Slow catalog dependency reads",
            "Checkout dependency saturation",
        ]
        return AgentResult("Root-cause hypotheses ranked.", ["hypotheses"])


class MitigationAgent(Agent):
    name = "Mitigation Agent"
    task = "Create rollback, patch, and communication options."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["mitigations"] = [
            "Rollback the catalog deploy if approval is granted",
            "Warm high-traffic cache keys",
            "Temporarily rate-limit heavy catalog calls",
        ]
        return AgentResult("Mitigation plan generated.", ["mitigations"])


class IncidentVerifierAgent(Agent):
    name = "Incident Verifier Agent"
    task = "Check blast radius, recovery criteria, and handoff readiness."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        context.artifacts["final_markdown"] = f"""# Incident Handoff: {mission.topic}

**Audience:** {mission.audience}  
**Scope:** {mission.region}  
**Timebox:** {mission.horizon}

## Signals
{bullet_list(context.artifacts["signals"])}

## Likely causes
{bullet_list(context.artifacts["hypotheses"])}

## Mitigation path
{bullet_list(context.artifacts["mitigations"])}

## Stop condition
Stop when the key latency metric returns near baseline, new errors remain flat, and rollback risk is accepted by the incident commander.
"""
        return AgentResult("Incident handoff verified.", ["final_markdown"])


def incident_agents(llm: LLMClient) -> list[Agent]:
    return [SignalAgent(llm), DiagnosisAgent(llm), MitigationAgent(llm), IncidentVerifierAgent(llm)]

