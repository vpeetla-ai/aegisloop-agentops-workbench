from __future__ import annotations

from agent_loop.agents.base import Agent, AgentResult, bullet_list
from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext


class ArchitectAgent(Agent):
    name = "Architect Agent"
    task = "Map services, dependencies, target topology, and cutover boundaries."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["architecture"] = ["Managed database", "Private networking", "Object storage", "Terraform pipeline"]
        return AgentResult("Target architecture mapped.", ["architecture"])


class SecurityAgent(Agent):
    name = "Security Agent"
    task = "Review identity, network, data, and compliance controls."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["security_controls"] = [
            "Encrypt backups and migration snapshots",
            "Use private connectivity for data paths",
            "Apply least-privilege IAM to migration jobs",
            "Preserve audit evidence for cutover decisions",
        ]
        return AgentResult("Security controls mapped.", ["security_controls"])


class FinOpsAgent(Agent):
    name = "FinOps Agent"
    task = "Model cost, utilization, and duplicate-run exposure."

    async def run(self, context: AgentContext) -> AgentResult:
        context.artifacts["cost_controls"] = [
            "Rightsize steady-state compute",
            "Track parallel-run migration cost",
            "Reserve predictable workloads after stabilization",
        ]
        return AgentResult("Cost controls generated.", ["cost_controls"])


class DeliveryAgent(Agent):
    name = "Delivery Agent"
    task = "Sequence milestones, owners, rollback points, and verification gates."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        context.artifacts["final_markdown"] = f"""# Migration Plan: {mission.topic}

**Audience:** {mission.audience}  
**Scope:** {mission.region}  
**Horizon:** {mission.horizon}

## Target architecture
{bullet_list(context.artifacts["architecture"])}

## Security controls
{bullet_list(context.artifacts["security_controls"])}

## FinOps controls
{bullet_list(context.artifacts["cost_controls"])}

## Delivery sequence
1. Inventory services, data paths, owners, and rollback criteria.
2. Build the managed target environment with IaC and private networking.
3. Migrate low-risk workloads first and verify telemetry parity.
4. Run dual-read verification before final cutover.
"""
        return AgentResult("Migration plan generated.", ["final_markdown"])


def migration_agents(llm: LLMClient) -> list[Agent]:
    return [ArchitectAgent(llm), SecurityAgent(llm), FinOpsAgent(llm), DeliveryAgent(llm)]

