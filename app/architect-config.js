window.ARCHITECT_CONFIG = {
  tagline:
    "Glass-box AgentOps: mission loops with policy bounds, fleet metrics, and honest per-agent telemetry spans — operate agent fleets like you operate services.",
  metricsUrl: (window.AEGISLOOP_API || "https://aegisloop-api.onrender.com") + "/api/v1/ops/metrics",
  metricsPath: "/api/v1/ops/metrics",
  metricLabels: { runs: "Mission runs", entities: "Sample window", latency: "P95 runtime" },
  layers: [
    { tier: "L1", name: "Mission console", role: "Operator UX", components: ["Scenario picker", "Loop modes", "Live trace"] },
    { tier: "L2", name: "Agent loop", role: "Closed / open / HITL", components: ["Policy bounds", "RAG + memory", "Eval checks"] },
    { tier: "L3", name: "Persistence", role: "Fleet history", components: ["Postgres runs", "JSONL fallback", "Cost + runtime"] },
    { tier: "L4", name: "Ops", role: "SLO proof", components: ["P50/P95", "Failure rate", "Golden eval gate"] },
  ],
  tradeoffs: [
    { decision: "Persist every mission run", gain: "Fleet-level P95 and failure analytics", trade: "Storage growth vs ephemeral demos" },
    { decision: "Human gate loop mode", gain: "Safe escalation on high-risk missions", trade: "Operator latency vs full autonomy" },
    { decision: "Token budget slider", gain: "FinOps-aware mission bounds", trade: "May truncate long research paths" },
    { decision: "Render + Vercel split", gain: "Cheap static UI + API wake", trade: "Cold-start delay on first mission" },
  ],
  adrLinks: [
    { title: "ADR-012 — AegisLoop FinOps metering", href: "https://github.com/vpeetla-ai/ai-architecture-portfolio/blob/main/adr/ADR-012-aegisloop-finops-metering.md" },
    { title: "Case study — AegisLoop", href: "https://github.com/vpeetla-ai/ai-architecture-portfolio/blob/main/case-studies/aegisloop-agentops-workbench.md" },
  ],
  docsLinks: [
    { title: "Architecture", href: "https://github.com/vpeetla-ai/aegisloop-agentops-workbench/blob/main/docs/ARCHITECTURE.md" },
    { title: "SLO targets", href: "https://github.com/vpeetla-ai/aegisloop-agentops-workbench/blob/main/docs/SLO.md" },
  ],
};
