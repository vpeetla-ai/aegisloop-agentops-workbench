from __future__ import annotations

from datetime import datetime, timezone

from agent_loop.agents.base import Agent, AgentResult, bullet_list
from agent_loop.data_sources import fetch_market_headlines, fetch_market_snapshot
from agent_loop.llm import LLMClient
from agent_loop.models import AgentContext


class MarketDataAgent(Agent):
    name = "Market Data Agent"
    task = "Discover today's major index, ETF, rates, and safe-haven signals."

    async def run(self, context: AgentContext) -> AgentResult:
        snapshot = await fetch_market_snapshot()
        context.artifacts["market_data"] = {
            "as_of": snapshot.as_of,
            "source_status": snapshot.source_status,
            "quotes": [quote.__dict__ for quote in snapshot.quotes],
            "top_gainers": [mover.__dict__ for mover in snapshot.top_gainers],
            "top_losers": [mover.__dict__ for mover in snapshot.top_losers],
            "most_active": [mover.__dict__ for mover in snapshot.most_active],
        }
        return AgentResult("Market snapshot, movers, and source status collected.", ["market_data"])


class NewsCatalystAgent(Agent):
    name = "News Catalyst Agent"
    task = "Discover current market headlines and likely catalysts."

    async def run(self, context: AgentContext) -> AgentResult:
        headlines = await fetch_market_headlines()
        context.artifacts["headlines"] = headlines
        return AgentResult("Market headline catalysts collected.", ["headlines"])


class MarketRegimeAgent(Agent):
    name = "Market Regime Agent"
    task = "Classify risk-on/risk-off tone and summarize sector implications."

    async def run(self, context: AgentContext) -> AgentResult:
        quotes = context.artifacts["market_data"]["quotes"]
        positive = sum(1 for quote in quotes if str(quote["change_pct"]).startswith("+"))
        negative = sum(1 for quote in quotes if str(quote["change_pct"]).startswith("-"))
        unchanged = max(0, len(quotes) - positive - negative)
        tone = "risk-on" if positive > negative else "risk-off / selective" if negative > positive else "mixed"
        gainers = len(context.artifacts["market_data"].get("top_gainers", []))
        losers = len(context.artifacts["market_data"].get("top_losers", []))
        context.artifacts["regime"] = {
            "tone": tone,
            "up_down_summary": {
                "tracked_positive": positive,
                "tracked_negative": negative,
                "tracked_unchanged_or_unknown": unchanged,
                "top_gainers_count": gainers,
                "top_losers_count": losers,
            },
            "implications": [
                "Watch whether technology leadership is confirmed by breadth.",
                "Compare small caps against mega-cap indexes for risk appetite.",
                "Use Treasury duration and gold as cross-asset confirmation signals.",
            ],
        }
        return AgentResult(f"Market tone classified as {tone}.", ["regime"])


class InvestmentBriefAgent(Agent):
    name = "Investment Brief Agent"
    task = "Package a clear market analysis brief for a broad audience."

    async def run(self, context: AgentContext) -> AgentResult:
        mission = context.request.input
        market_data = context.artifacts["market_data"]
        quotes = market_data["quotes"]
        headlines = context.artifacts["headlines"]
        regime = context.artifacts["regime"]
        completion = await self.llm.complete(
            "You write educational market analysis. Do not provide personalized financial advice.",
            f"Create a concise stock market analysis for {mission.audience}. Quotes: {quotes}. Movers: {market_data}. Headlines: {headlines}.",
        )
        self.meter_llm(context, completion)
        context.artifacts["final_markdown"] = completion.text or f"""# Today's Stock Market Analysis: {mission.topic}

**Audience:** {mission.audience}  
**Region:** {mission.region}  
**As of:** {market_data["as_of"]}  
**Note:** Educational analysis only, not financial advice.

## Source status
{bullet_list([f"{source}: {status}" for source, status in market_data["source_status"].items()])}

## Major indexes and market proxies
{quote_table(quotes)}

## Total-market ups and downs
- Tracked positive: {regime["up_down_summary"]["tracked_positive"]}
- Tracked negative: {regime["up_down_summary"]["tracked_negative"]}
- Unknown / flat from available feed: {regime["up_down_summary"]["tracked_unchanged_or_unknown"]}
- Top gainers found: {regime["up_down_summary"]["top_gainers_count"]}
- Top losers found: {regime["up_down_summary"]["top_losers_count"]}

## Top gainers today
{mover_table(market_data["top_gainers"])}

## Top losers today
{mover_table(market_data["top_losers"])}

## Most active names
{mover_table(market_data["most_active"])}

## Current catalysts
{bullet_list(headlines[:6])}

## Regime read
**Tone:** {regime["tone"]}

{bullet_list(regime["implications"])}

## What to watch next
1. Breadth confirmation versus headline index performance.
2. Rate-sensitive assets versus growth leadership.
3. Earnings revisions, guidance quality, and volatility around major macro releases.
"""
        return AgentResult("Stock market analysis brief generated.", ["final_markdown"])


def research_agents(llm: LLMClient) -> list[Agent]:
    return [MarketDataAgent(llm), NewsCatalystAgent(llm), MarketRegimeAgent(llm), InvestmentBriefAgent(llm)]


def quote_table(quotes: list[dict]) -> str:
    if not quotes:
        return "_No quote data returned._"
    rows = ["| Symbol | Name | Last | Change % | Volume | Source |", "|---|---:|---:|---:|---:|---|"]
    rows.extend(
        f"| {quote.get('symbol', '')} | {quote.get('name', '')} | {quote.get('last', '')} | {quote.get('change_pct', '')} | {quote.get('volume', '')} | {quote.get('source', '')} |"
        for quote in quotes
    )
    return "\n".join(rows)


def mover_table(movers: list[dict]) -> str:
    if not movers:
        return "_No mover data returned from configured free sources._"
    rows = ["| Symbol | Company | Price | Change % | Volume | Source |", "|---|---|---:|---:|---:|---|"]
    rows.extend(
        f"| {mover.get('symbol', '')} | {mover.get('name', '')} | {mover.get('price', '')} | {mover.get('change_pct', '')} | {mover.get('volume', '')} | {mover.get('source', '')} |"
        for mover in movers[:10]
    )
    return "\n".join(rows)
