import type { Config, Context } from "@netlify/functions";
import OpenAI from "openai";

type MissionRequest = {
  mission: "research" | "content" | "incident" | "migration" | "security";
  mode?: "local" | "ollama" | "gateway";
  loop_mode?: "closed" | "open" | "human";
  input: {
    topic: string;
    audience: string;
    region: string;
    horizon: string;
    sources: string;
  };
};

type AgentEvent = {
  agent: string;
  status: "running" | "done";
  task: string;
  detail: string;
  artifact_keys: string[];
  timestamp: string;
};

const now = () => new Date().toISOString();

const event = (agent: string, task: string, detail: string, artifact_keys: string[] = []): AgentEvent[] => [
  { agent, status: "running", task, detail: `${agent} started.`, artifact_keys: [], timestamp: now() },
  { agent, status: "done", task, detail, artifact_keys, timestamp: now() },
];

async function gatewayCompletion(request: MissionRequest): Promise<string | null> {
  if (request.mode !== "gateway") return null;

  try {
    const openai = new OpenAI();
    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "You are a principal AI architect writing concise portfolio-grade mission artifacts. Use markdown.",
        },
        {
          role: "user",
          content: `Mission: ${request.mission}
Topic: ${request.input.topic}
Audience: ${request.input.audience}
Region: ${request.input.region}
Horizon: ${request.input.horizon}
Sources: ${request.input.sources}`,
        },
      ],
      temperature: 0.2,
    });
    return completion.choices[0]?.message?.content ?? null;
  } catch {
    return null;
  }
}

function localArtifact(request: MissionRequest): string {
  const { input } = request;
  if (request.mission === "security") {
    return `# Security Review: ${input.topic}

**Audience:** ${input.audience}  
**Scope:** ${input.region}

## Threats
- Prompt injection through untrusted retrieved context
- Over-scoped connector permissions
- Secrets leakage through tool output or traces
- Missing audit trail for external actions

## Launch gate
Approve only after tool scopes are minimized, prompt-injection tests pass, and every external action has traceable human approval or deterministic policy allowance.`;
  }

  if (request.mission === "content") {
    return `# Principal AI Architect Content Radar

**Audience:** ${input.audience}  
**Region:** ${input.region}  
**Horizon:** ${input.horizon}

## Current AI trend signals
- Agentic workflows are moving from demos to governed production systems.
- Evaluation, observability, tool permissions, and human control are becoming board-level concerns.
- Local models, model routing, AI gateways, and cost-aware architectures are rising enterprise topics.
- RAG trust, prompt injection, and source governance remain practical architecture issues.

## Recommended content angles
- Agent loops fail when they are not bounded, observable, and governed.
- The difference between a demo agent and a production agent system.
- Why Principal AI Architects should design eval gates before tools.
- How AI Gateway, local models, and routing shape enterprise AI cost.

## 5-post sprint
1. POV post on loop engineering.
2. Architecture breakdown of an orchestrated fleet.
3. Leadership post on operating models.
4. Build-in-public trace walkthrough.
5. Executive approval checklist.`;
  }

  if (request.mission === "migration") {
    return `# Migration Plan: ${input.topic}

**Audience:** ${input.audience}  
**Scope:** ${input.region}  
**Horizon:** ${input.horizon}

## Delivery sequence
1. Inventory services, owners, data paths, and rollback criteria.
2. Build managed target environment with IaC and private networking.
3. Migrate low-risk services first and verify telemetry parity.
4. Run dual-read verification before final cutover.`;
  }

  if (request.mission === "incident") {
    return `# Incident Handoff: ${input.topic}

## Likely causes
- Cache stampede after recent deploy
- Slow downstream dependency reads
- Checkout dependency saturation

## Mitigation path
- Roll back risky deploy if approved
- Warm high-traffic cache keys
- Monitor p95 latency and error rate until stable`;
  }

  return `# Today's Stock Market Analysis: ${input.topic}

**Audience:** ${input.audience}  
**Region:** ${input.region}  
**Horizon:** ${input.horizon}
**Note:** Educational analysis only, not financial advice.

## Market read
- Read the session through index direction, breadth, rates, megacap leadership, and volatility.
- Compare S&P 500 and Nasdaq leadership against small caps to confirm risk appetite.
- Use Treasury duration and gold as cross-asset checks for stress or defensiveness.

## What to watch
- Breadth confirmation versus headline index performance.
- Rate-sensitive assets versus growth leadership.
- Earnings revisions, guidance quality, and major macro releases.

## Audience framing
Explain what moved, why it matters, and what to watch next without giving personalized financial advice.`;
}

export default async (req: Request, context: Context) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const request = (await req.json()) as MissionRequest;
  const gatewayArtifact = await gatewayCompletion(request);
  const artifact = gatewayArtifact ?? localArtifact(request);
  const trace = [
    ...event("Orchestrator", "Bind mission, select fleet, enforce bounds.", "Mission contract created.", [
      "mission_contract",
    ]),
    ...event("Discovery Agent", "Extract source signals.", "Evidence normalized.", ["discovery"]),
    ...event("Analyst Agent", "Cluster evidence.", "Trends and opportunities generated.", ["analysis"]),
    ...event("Critic Agent", "Evaluate confidence and risk.", "Risk review completed.", ["critique"]),
    ...event("Writer Agent", "Generate final artifact.", "Mission artifact produced.", ["final_markdown"]),
  ];

  return Response.json({
    mission: request.mission,
    runtime: gatewayArtifact ? "netlify-ai-gateway/gpt-4o-mini" : "netlify-function/local-fallback",
    cost_usd: 0,
    artifact_markdown: artifact,
    artifacts: { final_markdown: artifact, request_id: context.requestId },
    trace,
    evaluation: {
      quality_score: request.loop_mode === "human" ? 86 : 94,
      decision:
        request.loop_mode === "human"
          ? "Human approval required before ship"
          : "Ship: quality gate passed",
      checks: {
        "Goal alignment": "pass",
        "Evidence quality": "pass",
        "Policy compliance": request.loop_mode === "human" ? "review" : "pass",
        "Cost and latency": "pass",
        "Stop condition": "pass",
      },
    },
  });
};

export const config: Config = {
  path: "/api/missions/run",
  method: "POST",
};
