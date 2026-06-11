from __future__ import annotations

from datetime import datetime, timezone

from agent_loop.agents.base import Agent, AgentResult, bullet_list, keywords
from agent_loop.data_sources import fetch_ai_trends
from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext


class TrendScoutAgent(Agent):
    name = "Trend Scout Agent"
    task = "Discover current AI topics from research and community trend feeds."

    async def run(self, context: AgentContext) -> AgentResult:
        trends = await fetch_ai_trends()
        context.artifacts["trends"] = trends
        context.artifacts["trend_keywords"] = keywords(" ".join(trends), limit=10)
        return AgentResult("Current AI trend candidates collected.", ["trends", "trend_keywords"])


class AudienceFitAgent(Agent):
    name = "Audience Fit Agent"
    task = "Map trend candidates to Principal AI Architect audience value."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        context.artifacts["audience_fit"] = [
            f"Translate research-heavy topics into architecture decisions for {mission.audience}.",
            "Prefer content that shows governance, evaluation, reliability, and operating model tradeoffs.",
            "Use executive-readable framing: risk, cost, control, measurable business impact.",
        ]
        return AgentResult("Audience-fit lens applied to trend candidates.", ["audience_fit"])


class AngleBuilderAgent(Agent):
    name = "Angle Builder Agent"
    task = "Create differentiated post angles and hooks."

    async def run(self, context: AgentContext) -> AgentResult:
        trend_keywords = context.artifacts["trend_keywords"][:5]
        context.artifacts["angles"] = [
            f"Why {trend_keywords[0] if trend_keywords else 'agentic AI'} systems need loop engineering, not just prompting.",
            "The hidden production gap: evaluation gates, memory, permissions, and human control.",
            "How principal architects should review an AI agent system before approving launch.",
            "What leaders misunderstand about autonomous agents in enterprise workflows.",
        ]
        return AgentResult("Content angles generated.", ["angles"])


class EditorialPlannerAgent(Agent):
    name = "Editorial Planner Agent"
    task = "Package a content plan with hooks, post formats, and calls to action."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        trends = context.artifacts["trends"]
        angles = context.artifacts["angles"]
        audience_fit = context.artifacts["audience_fit"]
        llm_text = await self.llm.complete(
            "You create LinkedIn content plans for principal AI architects.",
            f"Audience: {mission.audience}. Trends: {trends}. Angles: {angles}.",
        )
        context.artifacts["final_markdown"] = llm_text or f"""# Principal AI Architect Content Radar

**Audience:** {mission.audience}  
**Region:** {mission.region}  
**As of:** {datetime.now(timezone.utc).date().isoformat()}

## Current AI trend signals
{bullet_list(trends[:8])}

## Audience lens
{bullet_list(audience_fit)}

## Recommended content angles
{bullet_list(angles)}

## 5-post content sprint
1. **Point of view:** Agent loops fail when they are not bounded, observable, and governed.
2. **Architecture breakdown:** Orchestrator, specialist agents, memory, tools, eval gate, human control.
3. **Leadership post:** Why agentic AI needs operating models, not only model upgrades.
4. **Build-in-public demo:** Show a real agent runtime trace and explain each handoff.
5. **Checklist:** Questions every executive should ask before shipping AI agents.
"""
        return AgentResult("Principal AI Architect content plan generated.", ["final_markdown"])


def content_agents(llm: LLMClient) -> list[Agent]:
    return [TrendScoutAgent(llm), AudienceFitAgent(llm), AngleBuilderAgent(llm), EditorialPlannerAgent(llm)]
