const scenarios = {
  incident: {
    title: "Production Incident Triage",
    copy: "Real agents inspect symptoms, isolate likely causes, test mitigations, and produce a handoff plan.",
    agents: [
      ["Signal", "Normalizes alerts, logs, metrics, and user impact", "S"],
      ["Diagnosis", "Builds and ranks root-cause hypotheses", "D"],
      ["Mitigation", "Creates rollback, patch, and comms options", "M"],
      ["Verifier", "Checks safety, blast radius, and recovery criteria", "V"],
    ],
    defaults: {
      topic: "Checkout latency spike",
      audience: "Engineering manager and incident commander",
      region: "Production",
      horizon: "next 60 minutes",
      sources:
        "p95 latency moved from 380ms to 1.8s after catalog deploy. Error rate is low, CPU is normal, cache miss rate increased, support tickets mention slow checkout.",
    },
  },
  research: {
    title: "Today's Stock Market Analysis",
    copy: "Market data, news catalyst, regime, and investment brief agents discover today's market tone and package an audience-friendly analysis.",
    agents: [
      ["Market Data", "Collects index, ETF, rates, and safe-haven signals", "M"],
      ["News Catalyst", "Finds current market headlines and likely catalysts", "N"],
      ["Regime", "Classifies risk tone and cross-asset confirmation", "R"],
      ["Brief Writer", "Packages an educational market brief", "B"],
    ],
    defaults: {
      topic: "US stock market daily brief",
      audience: "LinkedIn audience, builders, and working professionals",
      region: "United States",
      horizon: "today",
      sources:
        "Focus on S&P 500, Nasdaq, Dow, small caps, Treasury yields, gold, market breadth, megacap technology, earnings, Fed expectations, and risk appetite. Educational analysis only, not financial advice.",
    },
  },
  content: {
    title: "Principal AI Architect Content Radar",
    copy: "Trend scout, audience fit, angle builder, and editorial planner agents discover current AI topics and convert them into content ideas.",
    agents: [
      ["Trend Scout", "Discovers current AI research and community topics", "T"],
      ["Audience Fit", "Maps trends to Principal AI Architect audience value", "A"],
      ["Angle Builder", "Creates differentiated hooks and post angles", "G"],
      ["Planner", "Builds a practical LinkedIn content sprint", "P"],
    ],
    defaults: {
      topic: "Trending AI topics for Principal AI Architect content",
      audience: "AI leaders, architects, engineering managers, and founders",
      region: "Global",
      horizon: "this week",
      sources:
        "Focus on agentic AI, evaluation, observability, AI governance, RAG, local models, AI gateways, workflow automation, reliability, cost control, and enterprise adoption patterns.",
    },
  },
  migration: {
    title: "Cloud Migration Plan",
    copy: "Architecture, security, FinOps, and delivery agents generate a migration plan with controls and milestones.",
    agents: [
      ["Architect", "Maps services, dependencies, and target topology", "A"],
      ["Security", "Reviews identity, network, data, and compliance controls", "S"],
      ["FinOps", "Models cost, utilization, and rightsizing strategy", "F"],
      ["Delivery", "Sequences milestones, owners, and rollback points", "D"],
    ],
    defaults: {
      topic: "Migrate customer analytics platform to managed cloud services",
      audience: "CIO, platform team, and security lead",
      region: "US and EU workloads",
      horizon: "two quarters",
      sources:
        "Current stack runs on VMs with manual deployments. Database contains customer analytics events. Downtime tolerance is near zero. Team prefers managed Postgres, object storage, Terraform, private networking, and phased cutover.",
    },
  },
  security: {
    title: "Security Review Loop",
    copy: "Threat model, scanner, policy, and remediation agents create a governed security review.",
    agents: [
      ["Threat Model", "Identifies assets, actors, trust boundaries, and abuse paths", "T"],
      ["Scanner", "Finds dependency, configuration, and secret exposure risks", "S"],
      ["Policy", "Maps findings to controls, permissions, and exceptions", "P"],
      ["Remediation", "Prioritizes fixes with owners and verification evidence", "R"],
    ],
    defaults: {
      topic: "Review AI workflow automation service before launch",
      audience: "Security review board",
      region: "SaaS production",
      horizon: "pre-launch",
      sources:
        "Service calls CRM, email, and ticketing tools. It stores workflow state, uses RAG over internal docs, and supports human approval. Concerns include excessive tool permissions, prompt injection, secrets exposure, and audit gaps.",
    },
  },
};

const evalNames = ["Goal alignment", "Evidence quality", "Policy compliance", "Cost and latency", "Stop condition"];
const guardrailNames = ["Tool permission", "Rate limit", "Policy filter", "Human escape", "Idempotent action"];
const stagePlan = ["Goal", "Plan", "Execute", "Verify", "Ship"];
const API_BASE =
  window.AEGISLOOP_API_BASE ||
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "http://localhost:8000" : "/api/aegisloop");

const state = {
  scenarioKey: "research",
  loopMode: "closed",
  running: false,
  step: 0,
  loopCount: 0,
  tools: 0,
  latency: 0,
  quality: 0,
  activeAgent: -1,
  artifacts: {},
  traces: [],
  providerStatus: {},
  activeArtifactTab: "brief",
  timer: null,
  apiAvailable: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const elements = {
  scenario: $("#scenario"),
  missionTitle: $("#missionTitle"),
  missionCopy: $("#missionCopy"),
  runStatus: $("#runStatus"),
  qualityScore: $("#qualityScore"),
  orchestratorState: $("#orchestratorState"),
  orchestratorDetail: $("#orchestratorDetail"),
  handoffStrip: $("#handoffStrip"),
  agentList: $("#agentList"),
  evalChecks: $("#evalChecks"),
  decision: $("#decision"),
  meterFill: $("#meterFill"),
  memoryList: $("#memoryList"),
  guardrails: $("#guardrails"),
  traceLog: $("#traceLog"),
  loopCount: $("#loopCount"),
  toolCalls: $("#toolCalls"),
  cost: $("#cost"),
  latency: $("#latency"),
  budget: $("#budget"),
  budgetValue: $("#budgetValue"),
  risk: $("#risk"),
  riskValue: $("#riskValue"),
  ragToggle: $("#ragToggle"),
  startRun: $("#startRun"),
  stepRun: $("#stepRun"),
  resetRun: $("#resetRun"),
  llmMode: $("#llmMode"),
  stackCopy: $("#stackCopy"),
  missionTopic: $("#missionTopic"),
  missionAudience: $("#missionAudience"),
  missionRegion: $("#missionRegion"),
  missionHorizon: $("#missionHorizon"),
  missionSources: $("#missionSources"),
  artifactTitle: $("#artifactTitle"),
  artifactSubtitle: $("#artifactSubtitle"),
  artifactOutput: $("#artifactOutput"),
  artifactData: $("#artifactData"),
  artifactTrace: $("#artifactTrace"),
  artifactSources: $("#artifactSources"),
  artifactTabs: $$(".artifact-tabs button"),
  artifactPanes: $$(".artifact-pane"),
  copyArtifact: $("#copyArtifact"),
  liveAgentName: $("#liveAgentName"),
  liveAgentTask: $("#liveAgentTask"),
  architectureFlow: $("#architectureFlow"),
  agentScratchpad: $("#agentScratchpad"),
};

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

function missionInput() {
  return {
    topic: elements.missionTopic.value.trim() || scenarios[state.scenarioKey].defaults.topic,
    audience: elements.missionAudience.value.trim() || scenarios[state.scenarioKey].defaults.audience,
    region: elements.missionRegion.value.trim() || scenarios[state.scenarioKey].defaults.region,
    horizon: elements.missionHorizon.value.trim() || scenarios[state.scenarioKey].defaults.horizon,
    sources: elements.missionSources.value.trim() || scenarios[state.scenarioKey].defaults.sources,
  };
}

function keywordize(text) {
  const stop = new Set([
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "want",
    "include",
    "common",
    "strong",
    "next",
    "month",
    "months",
    "service",
    "platform",
  ]);
  return text
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 3 && !stop.has(word))
    .reduce((counts, word) => {
      counts[word] = (counts[word] || 0) + 1;
      return counts;
    }, {});
}

function topKeywords(text, count = 6) {
  return Object.entries(keywordize(text))
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, count)
    .map(([word]) => word);
}

function sentenceSplit(text) {
  return text
    .split(/[.!?]\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 8);
}

function renderScenario() {
  const scenario = scenarios[state.scenarioKey];
  elements.missionTitle.textContent = scenario.title;
  elements.missionCopy.textContent = scenario.copy;
  elements.missionTopic.value = scenario.defaults.topic;
  elements.missionAudience.value = scenario.defaults.audience;
  elements.missionRegion.value = scenario.defaults.region;
  elements.missionHorizon.value = scenario.defaults.horizon;
  elements.missionSources.value = scenario.defaults.sources;

  elements.agentList.innerHTML = "";
  const template = $("#agentTemplate");
  scenario.agents.forEach(([name, role, initials]) => {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".agent-avatar").textContent = initials;
    node.querySelector("strong").textContent = name;
    node.querySelector("span").textContent = role;
    node.querySelector("small").textContent = "Idle";
    elements.agentList.append(node);
  });

  renderArchitectureFlow();
  renderMemory();
  renderHandoffs();
  renderStaticPanels();
  renderRun();
}

function renderMemory() {
  const input = missionInput();
  const memories = [
    ["Mission contract", `${input.topic} for ${input.audience}.`],
    ["Execution bounds", `${input.region}; horizon: ${input.horizon}.`],
    ["Context store", `${sentenceSplit(input.sources)[0] || "No seed evidence supplied yet."}`],
  ];
  elements.memoryList.innerHTML = memories
    .map(([title, body]) => `<div class="memory-item"><strong>${title}</strong>${escapeHtml(body)}</div>`)
    .join("");
}

function renderHandoffs() {
  const agents = scenarios[state.scenarioKey].agents;
  elements.handoffStrip.innerHTML = agents
    .slice(0, 3)
    .map(([name], index) => {
      const status = state.activeAgent > index ? "Complete" : state.activeAgent === index ? "Running" : "Pending";
      return `<div class="handoff-chip">${name}<br><strong>${status}</strong></div>`;
    })
    .join("");
}

function renderArchitectureFlow() {
  const agents = scenarios[state.scenarioKey].agents;
  elements.architectureFlow.innerHTML = agents
    .map(([name, role, initials], index) => {
      const cls = state.activeAgent === index ? "is-running" : state.activeAgent > index ? "is-done" : "";
      const status = state.activeAgent === index ? "Running" : state.activeAgent > index ? "Done" : "Waiting";
      return `
        <div class="flow-node ${cls}">
          <span>${initials}</span>
          <div><strong>${name}</strong><small>${role}</small></div>
          <em>${status}</em>
        </div>
      `;
    })
    .join("");
}

function renderStaticPanels() {
  const stackText =
    elements.llmMode.value === "api"
      ? state.apiAvailable
        ? "Real data mode: calls uv FastAPI agents at localhost:8000. Stock mission uses Yahoo/MarketBeat/Stooq provider adapters with visible source status."
        : "Real data mode needs the uv FastAPI backend running at localhost:8000."
      : elements.llmMode.value === "gateway"
        ? "Calls /api/missions/run, deployed as a Netlify Function using AI Gateway when enabled."
        : elements.llmMode.value === "ollama"
          ? "Attempts a free localhost Ollama call when available; falls back to browser-local agents if not."
          : state.scenarioKey === "research"
            ? "Demo fallback only: this mode does not call market data providers. Select uv FastAPI agents (real data)."
            : "Runs fully in this browser with deterministic local reasoning. No paid API key required.";
  elements.stackCopy.textContent = stackText;

  const toggles = [$("#policyToggle").checked, true, $("#ragToggle").checked, state.loopMode === "human", true];
  elements.guardrails.innerHTML = guardrailNames
    .map((name, index) => `<div class="guardrail"><span>${name}</span><span>${toggles[index] ? "On" : "Off"}</span></div>`)
    .join("");
}

async function checkApiAvailability() {
  try {
    const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    state.apiAvailable = response.ok;
  } catch {
    state.apiAvailable = false;
  }
  if (state.scenarioKey === "research" && state.apiAvailable && elements.llmMode.value === "local") {
    elements.llmMode.value = "api";
  }
  renderStaticPanels();
}

function renderRun() {
  document.body.classList.toggle("is-running", state.running);
  const approvalPending = state.loopMode === "human" && state.quality >= 82;
  elements.runStatus.textContent = state.running
    ? "Running"
    : approvalPending
      ? "Approval"
      : state.quality >= 90
        ? "Complete"
        : state.quality > 0
          ? "In Progress"
          : "Ready";
  elements.qualityScore.textContent = `${state.quality}%`;
  elements.meterFill.style.width = `${state.quality}%`;
  elements.loopCount.textContent = state.loopCount;
  elements.toolCalls.textContent = state.tools;
  elements.cost.textContent = "$0.00";
  elements.latency.textContent = `${state.latency.toFixed(1)}s`;
  elements.budgetValue.textContent = `${elements.budget.value}k`;
  elements.riskValue.textContent = `${elements.risk.value}%`;

  const stageIndex = Math.min(Math.floor((state.quality / 100) * stagePlan.length), stagePlan.length - 1);
  $$(".stage").forEach((stage, index) => {
    stage.classList.toggle("is-current", index === stageIndex && state.quality < 90);
    stage.classList.toggle("is-done", index < stageIndex || state.quality >= 90);
  });

  $$(".agent").forEach((agent, index) => {
    const isActive = state.activeAgent === index && state.running;
    const isDone = state.activeAgent > index || state.quality >= 90;
    const isQueued = state.running && !isActive && !isDone;
    const progress = isDone ? 100 : isActive ? Math.min(92, state.quality + 14) : isQueued ? 12 : 0;
    agent.classList.toggle("is-active", isActive);
    agent.classList.toggle("is-done", isDone);
    agent.classList.toggle("is-risk", state.activeAgent === 2 && state.loopMode !== "closed");
    agent.querySelector("small").textContent = isActive ? "Running" : isDone ? "Done" : isQueued ? "Queued" : "Idle";
    agent.querySelector(".agent-progress div").style.width = `${progress}%`;
  });

  renderArchitectureFlow();
  renderHandoffs();
  renderChecks();

  const active = scenarios[state.scenarioKey].agents[state.activeAgent];
  elements.liveAgentName.textContent = active ? active[0] : "Orchestrator";
  elements.liveAgentTask.textContent = active
    ? active[1]
    : state.quality >= 90
      ? "Mission complete. Artifact ready."
      : "Waiting for mission input";
  elements.orchestratorState.textContent = state.running
    ? "Orchestrating live mission"
    : state.quality >= 90
      ? "Mission complete"
      : "Waiting for mission";
  elements.orchestratorDetail.textContent = state.running
    ? "Routing context, enforcing bounds, and evaluating handoffs"
    : "Goal owner, planner, budget governor";
}

function renderChecks() {
  const checks = evalNames.map((name, index) => {
    const threshold = 22 + index * 14;
    const passed = state.quality >= threshold;
    const cls = passed ? "pass" : state.quality > 55 ? "warn" : "";
    const label = passed ? "Pass" : state.quality > 55 ? "Review" : "Waiting";
    return `<div class="check-item ${cls}"><span>${name}</span><strong>${label}</strong></div>`;
  });
  elements.evalChecks.innerHTML = checks.join("");
}

function addTrace(title, body) {
  const item = { title, body, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) };
  state.traces.unshift(item);
  elements.traceLog.innerHTML = state.traces
    .slice(0, 18)
    .map((trace) => `<li><strong>${escapeHtml(trace.title)}</strong><br>${escapeHtml(trace.body)} <small>${trace.time}</small></li>`)
    .join("");
  renderLocalArtifactPanels();
}

function writeScratch(title, lines) {
  elements.agentScratchpad.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    ${lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
  `;
}

async function maybeOllama(prompt) {
  if (elements.llmMode.value !== "ollama") return null;
  try {
    const response = await fetch("http://localhost:11434/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "llama3.2:3b",
        prompt,
        stream: false,
        options: { temperature: 0.2, num_predict: 350 },
      }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    return data.response || null;
  } catch {
    return null;
  }
}

const missionAgents = {
  research: [
    async (input) => {
      const signals = [
        "S&P 500 / SPY: live quote available in uv API mode; local mode uses seed context.",
        "Nasdaq / QQQ: watch growth leadership and megacap concentration.",
        "Small caps / IWM: useful risk-appetite confirmation.",
        "Treasury duration / TLT and gold / GLD: cross-asset stress signals.",
      ];
      const keywords = topKeywords(`${input.topic} ${input.sources}`, 8);
      state.artifacts.discovery = { signals, keywords };
      return {
        title: "Market data scan complete",
        scratch: [
          "Local mode prepared market proxy watchlist.",
          `Priority watch words: ${keywords.join(", ")}.`,
          "Use uv FastAPI agents for live quote and headline discovery.",
        ],
      };
    },
    async (input) => {
      const keywords = state.artifacts.discovery.keywords;
      state.artifacts.analysis = {
        trends: [
          `${keywords[0] || "Market"} tone should be read through breadth, rates, and leadership quality.`,
          `${keywords[1] || "Nasdaq"} performance needs confirmation from small caps and equal-weight indexes.`,
          `For ${input.audience}, the useful story is what moved, why it moved, and what to watch next.`,
        ],
        opportunities: [
          "Explain market action without jargon.",
          "Separate current catalysts from durable trend signals.",
          "Close with watchlist items instead of personal financial advice.",
        ],
      };
      return {
        title: "Regime analysis complete",
        scratch: ["Clustered market signals into tone, catalysts, and watch items.", "Tool used: local market regime rubric."],
      };
    },
    async (input) => {
      const weakClaims = ["Avoid price predictions without live data and confidence intervals.", "Keep the brief educational, not personalized financial advice."];
      state.artifacts.critique = {
        confidence: elements.llmMode.value === "api" ? "Live-data dependent" : "Medium local fallback",
        weakClaims,
        risks: ["Headline index strength can hide weak breadth.", "Rate moves can quickly change equity factor leadership."],
      };
      return {
        title: "Risk review complete",
        scratch: [`Confidence: ${state.artifacts.critique.confidence}.`, ...weakClaims, "Tool used: evaluator rubric + policy check."],
      };
    },
    async (input) => {
      const prompt = `Write an educational stock market brief for ${input.audience} about ${input.topic}. Use these notes: ${input.sources}`;
      const ollama = await maybeOllama(prompt);
      state.artifacts.final = ollama || buildStockMarketBrief(input);
      return {
        title: "Market brief ready",
        scratch: [
          ollama ? "Used local Ollama model response." : "Used browser-local deterministic writer.",
          "Artifact packaged for broad audience readability.",
        ],
      };
    },
  ],
  content: [
    async (input) => {
      const trends = [
        "Agentic workflows moving from demos to governed production systems",
        "Evaluation gates and observability for AI agents",
        "Local models, routing, and cost-aware AI architecture",
        "RAG quality, source trust, and prompt-injection defense",
      ];
      state.artifacts.trends = trends;
      state.artifacts.trendKeywords = topKeywords(`${input.sources} ${trends.join(" ")}`, 8);
      return { title: "AI trend scan complete", scratch: trends };
    },
    async (input) => {
      state.artifacts.audienceFit = [
        `Translate technical trends into decisions for ${input.audience}.`,
        "Prioritize topics that show governance, reliability, measurable impact, and tradeoffs.",
        "Avoid generic AI hype; use architect-level operating model language.",
      ];
      return { title: "Audience fit complete", scratch: state.artifacts.audienceFit };
    },
    async () => {
      state.artifacts.angles = [
        "Agent loops fail when they are not bounded, observable, and governed.",
        "Why Principal AI Architects should design eval gates before tools.",
        "The difference between a demo agent and a production agent system.",
        "How AI Gateway, local models, and routing shape enterprise AI cost.",
      ];
      return { title: "Content angles complete", scratch: state.artifacts.angles };
    },
    async (input) => {
      const prompt = `Create a content plan for ${input.audience} about ${input.topic}. Trends: ${state.artifacts.trends.join("; ")}`;
      const ollama = await maybeOllama(prompt);
      state.artifacts.final = ollama || buildContentPlan(input);
      return { title: "Content radar ready", scratch: ["Generated hooks, post formats, and weekly sprint plan."] };
    },
  ],
  incident: [
    async (input) => {
      const signals = sentenceSplit(input.sources);
      state.artifacts.signals = signals;
      return { title: "Signals normalized", scratch: [`Normalized ${signals.length} operational signals.`, "Tool used: log/metric summarizer."] };
    },
    async () => {
      state.artifacts.hypotheses = ["Cache stampede after deploy", "Slow downstream catalog reads", "Checkout dependency saturation"];
      return { title: "Hypotheses ranked", scratch: state.artifacts.hypotheses };
    },
    async () => {
      state.artifacts.mitigation = ["Rollback catalog deploy", "Warm cache keys", "Temporarily rate-limit heavy catalog calls"];
      return { title: "Mitigation plan built", scratch: state.artifacts.mitigation };
    },
    async (input) => {
      state.artifacts.final = buildIncidentBrief(input);
      return { title: "Incident handoff ready", scratch: ["Recovery criteria and owner handoff generated.", "Human approval required for rollback if enabled."] };
    },
  ],
  migration: [
    async (input) => {
      state.artifacts.architecture = ["Managed database", "Private network", "Object storage", "IaC pipeline"];
      return { title: "Target architecture mapped", scratch: state.artifacts.architecture };
    },
    async () => {
      state.artifacts.security = ["Encrypt backups", "Private connectivity", "Least-privilege IAM", "Audit migration jobs"];
      return { title: "Security controls mapped", scratch: state.artifacts.security };
    },
    async () => {
      state.artifacts.cost = ["Rightsize compute", "Reserve steady workloads", "Track migration duplicate-run cost"];
      return { title: "FinOps model complete", scratch: state.artifacts.cost };
    },
    async (input) => {
      state.artifacts.final = buildMigrationPlan(input);
      return { title: "Migration plan ready", scratch: ["Phased plan, rollback points, and owner model generated."] };
    },
  ],
  security: [
    async () => {
      state.artifacts.threats = ["Prompt injection", "Over-scoped tool permissions", "Secrets leakage", "Missing audit trail"];
      return { title: "Threat model complete", scratch: state.artifacts.threats };
    },
    async () => {
      state.artifacts.scan = ["No secret should be placed in prompt context", "Connector scopes need review", "RAG sources need trust labels"];
      return { title: "Scan findings complete", scratch: state.artifacts.scan };
    },
    async () => {
      state.artifacts.policy = ["Block destructive actions", "Require approvals for external writes", "Persist trace for every tool call"];
      return { title: "Policy mapping complete", scratch: state.artifacts.policy };
    },
    async (input) => {
      state.artifacts.final = buildSecurityReview(input);
      return { title: "Security review ready", scratch: ["Prioritized remediation and verification evidence generated."] };
    },
  ],
};

function buildStockMarketBrief(input) {
  const analysis = state.artifacts.analysis;
  const critique = state.artifacts.critique;
  return `
    <h3>Today's Stock Market Analysis: ${escapeHtml(input.topic)}</h3>
    <p><strong>Audience:</strong> ${escapeHtml(input.audience)} | <strong>Region:</strong> ${escapeHtml(input.region)} | <strong>Horizon:</strong> ${escapeHtml(input.horizon)}</p>
    <p><strong>Note:</strong> Educational analysis only, not financial advice. Select uv FastAPI agents for live quote/headline discovery.</p>
    <h3>Market read</h3>
    <ul>${analysis.trends.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>What to watch</h3>
    <ul>${analysis.opportunities.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Risks and confidence</h3>
    <p><strong>Confidence:</strong> ${critique.confidence}</p>
    <ul>${critique.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Suggested audience framing</h3>
    <ol>
      <li>Start with what moved and why it matters.</li>
      <li>Separate index performance from breadth and cross-asset confirmation.</li>
      <li>End with watch items, not personalized recommendations.</li>
    </ol>
  `;
}

function buildContentPlan(input) {
  return `
    <h3>Principal AI Architect Content Radar</h3>
    <p><strong>Audience:</strong> ${escapeHtml(input.audience)} | <strong>Region:</strong> ${escapeHtml(input.region)} | <strong>Horizon:</strong> ${escapeHtml(input.horizon)}</p>
    <h3>Trend signals</h3>
    <ul>${state.artifacts.trends.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Audience lens</h3>
    <ul>${state.artifacts.audienceFit.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Recommended angles</h3>
    <ul>${state.artifacts.angles.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>5-post sprint</h3>
    <ol>
      <li>Point of view: Agent loops need governance, not just better prompts.</li>
      <li>Architecture breakdown: Orchestrator, memory, tools, eval gate, human control.</li>
      <li>Leadership post: The operating model for production AI agents.</li>
      <li>Build-in-public demo: Show a trace and explain each handoff.</li>
      <li>Checklist: Questions executives should ask before approving AI agents.</li>
    </ol>
  `;
}

function buildIncidentBrief(input) {
  return `
    <h3>Incident Handoff: ${escapeHtml(input.topic)}</h3>
    <p><strong>Audience:</strong> ${escapeHtml(input.audience)} | <strong>Window:</strong> ${escapeHtml(input.horizon)}</p>
    <h3>Likely causes</h3>
    <ol>${state.artifacts.hypotheses.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>
    <h3>Mitigation path</h3>
    <ul>${state.artifacts.mitigation.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Stop condition</h3>
    <p>Stop when checkout p95 returns near baseline, new errors stay flat, and rollback risk is accepted by the incident commander.</p>
  `;
}

function buildMigrationPlan(input) {
  return `
    <h3>Migration Plan: ${escapeHtml(input.topic)}</h3>
    <p><strong>Audience:</strong> ${escapeHtml(input.audience)} | <strong>Scope:</strong> ${escapeHtml(input.region)} | <strong>Horizon:</strong> ${escapeHtml(input.horizon)}</p>
    <h3>Architecture</h3>
    <ul>${state.artifacts.architecture.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Controls</h3>
    <ul>${state.artifacts.security.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Delivery plan</h3>
    <ol><li>Inventory dependencies and define cutover gates.</li><li>Build parallel managed target environment.</li><li>Migrate low-risk services first, then data paths.</li><li>Run dual-read verification before final cutover.</li></ol>
  `;
}

function buildSecurityReview(input) {
  return `
    <h3>Security Review: ${escapeHtml(input.topic)}</h3>
    <p><strong>Audience:</strong> ${escapeHtml(input.audience)} | <strong>Scope:</strong> ${escapeHtml(input.region)}</p>
    <h3>Threats</h3>
    <ul>${state.artifacts.threats.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Policy controls</h3>
    <ul>${state.artifacts.policy.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h3>Launch gate</h3>
    <p>Approve only after tool scopes are minimized, prompt-injection tests pass, and every external action has traceable human approval or deterministic policy allowance.</p>
  `;
}

async function runOneAgent(index) {
  const scenario = scenarios[state.scenarioKey];
  const agent = scenario.agents[index];
  const task = missionAgents[state.scenarioKey][index];
  if (!agent || !task) return;

  state.activeAgent = index;
  state.step = index + 1;
  state.tools += 1 + index;
  state.latency += 0.8 + index * 0.45;
  state.quality = Math.max(state.quality, 16 + index * 21);
  renderRun();
  addTrace(agent[0], `Started: ${agent[1]}`);
  writeScratch(agent[0], ["Reading mission contract.", "Loading memory and source context.", "Preparing handoff payload."]);

  await wait(800);
  let result;
  try {
    result = await task(missionInput());
  } catch (error) {
    state.quality = Math.max(38, state.quality - 8);
    result = {
      title: `${agent[0]} failed safely`,
      scratch: [
        "The agent hit an execution error and preserved the current state.",
        `Error: ${error.message}`,
        "A production fleet would route this to retry, fallback, or human review.",
      ],
    };
    addTrace(result.title, error.message);
    writeScratch(result.title, result.scratch);
    renderRun();
    throw error;
  }
  state.quality = Math.min(94, state.quality + 12);
  state.latency += 0.6;
  addTrace(result.title, `${agent[0]} produced an artifact and passed state to the next agent.`);
  writeScratch(result.title, result.scratch);
  updateArtifact();
  renderRun();
}

async function runMission() {
  if (state.running) {
    stopRun();
    return;
  }
  if (state.scenarioKey === "research" && elements.llmMode.value === "local") {
    await checkApiAvailability();
  }
  if (elements.llmMode.value === "api" || elements.llmMode.value === "gateway") {
    await runBackendMission();
    return;
  }
  resetRun(false);
  state.running = true;
  elements.startRun.textContent = "Pause";
  elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} in progress`;
  addTrace("Orchestrator", "Bound mission, selected agent fleet, created evaluation rubric, and started execution.");
  renderMemory();
  renderRun();

  const agents = scenarios[state.scenarioKey].agents;
  try {
    for (let index = 0; index < agents.length; index += 1) {
      if (!state.running) return;
      await runOneAgent(index);
    }
  } catch {
    state.running = false;
    elements.startRun.textContent = "Run mission";
    elements.decision.textContent = "Fallback: agent failure captured, inspect trace before retry";
    renderRun();
    return;
  }

  state.running = false;
  state.activeAgent = agents.length;
  state.loopCount += 1;
  state.quality = state.loopMode === "human" ? 86 : 94;
  elements.startRun.textContent = "Run mission";
  elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} artifact`;
  elements.decision.textContent =
    state.loopMode === "human" ? "Human approval required before ship" : "Ship: quality gate passed with replayable trace";
  addTrace("Evaluation gate", elements.decision.textContent);
  renderRun();
}

async function runBackendMission() {
  resetRun(false);
  state.running = true;
  state.activeAgent = 0;
  elements.startRun.textContent = "Pause";
  elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} running on backend`;
  elements.artifactSubtitle.textContent = "Streaming agent trace, source coverage, and final artifact from the runtime.";
  addTrace("Backend runtime", "Calling production agent API.");
  writeScratch("Backend runtime", ["Submitting mission contract to real orchestrator.", "Waiting for agent trace and final artifact."]);
  renderRun();

  const endpoint = elements.llmMode.value === "api" ? `${API_BASE}/api/missions/stream` : "/api/missions/run";
  const mode = elements.llmMode.value === "gateway" ? "gateway" : "local";
  const backendApiKey = document.getElementById("backendApiKey")?.value?.trim();
  const requestHeaders = { "Content-Type": "application/json" };
  if (backendApiKey) requestHeaders["X-API-Key"] = backendApiKey;
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: requestHeaders,
      body: JSON.stringify({
        mission: state.scenarioKey,
        mode,
        loop_mode: state.loopMode,
        input: missionInput(),
      }),
    });
    if (!response.ok) throw new Error(`Backend returned ${response.status}`);
    if (elements.llmMode.value === "api" && response.body) {
      await consumeMissionStream(response);
    } else {
      const payload = await response.json();
      renderBackendResult(payload);
    }
  } catch (error) {
    addTrace("Backend unavailable", `${error.message}. Falling back to browser-local runtime.`);
    writeScratch("Backend unavailable", [
      "Start the uv API with: cd services/api && uv run agent-loop-api",
      "For deployed Gateway mode, enable Netlify AI and deploy the site.",
      "Running local fallback now so the demo remains usable.",
    ]);
    elements.llmMode.value = "local";
    renderStaticPanels();
    state.running = false;
    await runMission();
  }
}

async function consumeMissionStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "run_started") {
        elements.artifactSubtitle.textContent = `Run ${event.run_id} started. Waiting for specialist agents.`;
      }
      if (event.type === "agent_event") {
        const item = event.event;
        addTrace(item.agent, `${item.status}: ${item.detail}`);
        state.tools = Math.max(state.tools, state.traces.length);
        state.quality = Math.min(82, Math.max(state.quality, 24 + state.tools * 5));
        const runningIndex = scenarios[state.scenarioKey].agents.findIndex(([name]) => name === item.agent || item.agent.includes(name));
        if (runningIndex >= 0) state.activeAgent = runningIndex;
        writeScratch(item.agent, [item.task, item.detail, `Artifacts: ${(item.artifact_keys || []).join(", ") || "none yet"}`]);
        renderRun();
      }
      if (event.type === "artifact_delta") {
        state.providerStatus = event.provider_status || state.providerStatus;
        renderLocalArtifactPanels();
      }
      if (event.type === "run_completed") {
        renderBackendResult(event.response);
        completed = true;
      }
    }
  }
  if (!completed) throw new Error("Backend stream ended before completion");
}

function renderBackendResult(payload) {
  state.running = false;
  state.activeAgent = scenarios[state.scenarioKey].agents.length;
  state.loopCount += 1;
  state.quality = payload.evaluation?.quality_score || 90;
  state.tools = payload.trace?.length || 0;
  state.latency += (payload.artifacts?.runtime_ms || 1200) / 1000;
  state.artifacts = payload.artifacts || {};
  state.artifacts.final = markdownToHtml(payload.artifact_markdown || "# No artifact returned");
  state.providerStatus = payload.provider_status || payload.evaluation?.source_coverage || {};
  elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} artifact`;
  elements.artifactSubtitle.textContent = `Run ${payload.run_id || "complete"} | ${payload.runtime || "backend runtime"} | ${Object.keys(state.providerStatus).length || 0} provider checks`;
  elements.decision.textContent = payload.evaluation?.decision || "Ship: backend completed";
  elements.startRun.textContent = "Run mission";
  elements.cost.textContent = `$${Number(payload.cost_usd || 0).toFixed(2)}`;
  state.traces = [];
  elements.traceLog.innerHTML = "";
  (payload.trace || []).forEach((item) => {
    addTrace(item.agent, `${item.status}: ${item.detail}`);
  });
  writeScratch(payload.runtime || "Backend runtime", [
    `Runtime: ${payload.runtime || "unknown"}`,
    `Artifact keys: ${Object.keys(payload.artifacts || {}).join(", ") || "none"}`,
    `Decision: ${elements.decision.textContent}`,
  ]);
  renderArtifactPanels(payload);
  renderRun();
}

async function stepRun() {
  if (state.running) return;
  const max = scenarios[state.scenarioKey].agents.length;
  if (state.activeAgent >= max) return;
  state.running = true;
  const next = Math.max(0, state.activeAgent + 1);
  await runOneAgent(next);
  state.running = false;
  state.activeAgent = next;
  if (next === max - 1) {
    state.activeAgent = max;
    state.loopCount += 1;
    state.quality = state.loopMode === "human" ? 86 : 94;
    elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} artifact`;
    elements.decision.textContent =
      state.loopMode === "human" ? "Human approval required before ship" : "Ship: quality gate passed with replayable trace";
  }
  renderRun();
}

function stopRun() {
  state.running = false;
  elements.startRun.textContent = "Run mission";
  window.clearInterval(state.timer);
}

function resetRun(clearArtifact = true) {
  stopRun();
  state.step = 0;
  state.loopCount = 0;
  state.tools = 0;
  state.latency = 0;
  state.quality = 0;
  state.activeAgent = -1;
  state.artifacts = {};
  state.traces = [];
  state.providerStatus = {};
  elements.traceLog.innerHTML = "";
  if (clearArtifact) {
    elements.artifactTitle.textContent = `${scenarios[state.scenarioKey].title} will appear here`;
    elements.artifactSubtitle.textContent = "Brief, source data, trace, and provider status are separated for review.";
    elements.artifactOutput.textContent = "Configure the mission, then run the agent fleet. The deliverable is generated by chained agents and updated as each agent completes.";
    elements.artifactData.innerHTML = emptyPanel("No data artifacts yet.");
    elements.artifactTrace.innerHTML = emptyPanel("No trace events yet.");
    elements.artifactSources.innerHTML = emptyPanel("No provider checks yet.");
    setArtifactTab("brief");
    writeScratch("Scratchpad", ["Agent thoughts, tool outputs, and handoff payloads stream here during the run."]);
  }
  addTrace("Ready", "Mission loaded. Run the full fleet or step through each agent manually.");
  renderMemory();
  renderRun();
}

function updateArtifact() {
  if (state.artifacts.final) {
    elements.artifactOutput.innerHTML = state.artifacts.final;
    renderLocalArtifactPanels();
    return;
  }
  const parts = [];
  if (state.artifacts.trends) {
    parts.push(`<h3>Trend Scan</h3><ul>${state.artifacts.trends.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (state.artifacts.audienceFit) {
    parts.push(`<h3>Audience Fit</h3><ul>${state.artifacts.audienceFit.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (state.artifacts.angles) {
    parts.push(`<h3>Content Angles</h3><ul>${state.artifacts.angles.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (state.artifacts.discovery) {
    const title = state.scenarioKey === "research" ? "Market Data Scan" : "Discovery";
    parts.push(`<h3>${title}</h3><ul>${state.artifacts.discovery.signals.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (state.artifacts.analysis) {
    const title = state.scenarioKey === "research" ? "Market Regime Read" : "Analysis";
    parts.push(`<h3>${title}</h3><ul>${state.artifacts.analysis.trends.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (state.artifacts.critique) {
    parts.push(`<h3>Critique</h3><p>Confidence: ${escapeHtml(state.artifacts.critique.confidence)}</p>`);
  }
  elements.artifactOutput.innerHTML = parts.join("") || "Agents are preparing the first artifact.";
  renderLocalArtifactPanels();
}

function setArtifactTab(tab) {
  state.activeArtifactTab = tab;
  elements.artifactTabs.forEach((button) => {
    const active = button.dataset.artifactTab === tab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  elements.artifactPanes.forEach((pane) => {
    pane.classList.toggle("is-active", pane.dataset.artifactPane === tab);
  });
}

function renderArtifactPanels(payload) {
  elements.artifactOutput.innerHTML = markdownToHtml(payload.artifact_markdown || "# No artifact returned");
  elements.artifactData.innerHTML = renderDataArtifacts(payload.artifacts || {});
  elements.artifactTrace.innerHTML = renderTraceArtifact(payload.trace || []);
  elements.artifactSources.innerHTML = renderSourcesArtifact(payload.provider_status || payload.evaluation?.source_coverage || {});
}

function renderLocalArtifactPanels() {
  elements.artifactData.innerHTML = Object.keys(state.artifacts || {}).length
    ? renderDataArtifacts(state.artifacts)
    : emptyPanel("No data artifacts yet.");
  elements.artifactTrace.innerHTML = state.traces.length ? renderTraceArtifact(state.traces) : emptyPanel("No trace events yet.");
  elements.artifactSources.innerHTML = Object.keys(state.providerStatus || {}).length
    ? renderSourcesArtifact(state.providerStatus)
    : emptyPanel(elements.llmMode.value === "api" ? "Provider checks will appear as the backend runs." : "Provider checks are only available in uv FastAPI real-data mode.");
}

function renderDataArtifacts(artifacts) {
  const entries = Object.entries(artifacts).filter(([key]) => !["final_markdown", "runtime_ms", "final"].includes(key));
  if (!entries.length) return emptyPanel("No structured artifacts returned yet.");
  return `
    <div class="data-grid">
      ${entries
        .map(
          ([key, value]) => `
            <section class="data-card">
              <strong>${escapeHtml(titleCase(key))}</strong>
              <pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>
            </section>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTraceArtifact(trace) {
  if (!trace.length) return emptyPanel("No trace events yet.");
  return `
    <div class="trace-table">
      <table>
        <thead><tr><th>Agent</th><th>Status</th><th>Task</th><th>Detail</th></tr></thead>
        <tbody>
          ${trace
            .map((item) => {
              const agent = item.agent || item.title || "Runtime";
              const status = item.status || "done";
              const task = item.task || item.body || "";
              const detail = item.detail || item.body || item.time || "";
              return `<tr><td>${escapeHtml(agent)}</td><td><span class="status-dot ${escapeHtml(status)}">${escapeHtml(status)}</span></td><td>${escapeHtml(task)}</td><td>${escapeHtml(detail)}</td></tr>`;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderSourcesArtifact(providerStatus) {
  const entries = Object.entries(providerStatus || {});
  if (!entries.length) return emptyPanel("No provider checks yet.");
  return `
    <div class="source-grid">
      ${entries
        .map(([provider, status]) => {
          const normalized = String(status);
          const live = normalized.startsWith("live");
          const limited = normalized.includes("rate_limited") || normalized.includes("blocked");
          const cls = live ? "live" : limited ? "limited" : "offline";
          return `<div class="source-card ${cls}"><strong>${escapeHtml(titleCase(provider))}</strong><span>${escapeHtml(normalized)}</span></div>`;
        })
        .join("")}
    </div>
    <p class="source-note">Real market data comes from free/public provider paths when reachable. Some commercial sources do not expose free unauthenticated APIs, so their status is shown instead of silently fabricating data.</p>
  `;
}

function emptyPanel(message) {
  return `<div class="empty-panel">${escapeHtml(message)}</div>`;
}

function titleCase(value) {
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function markdownToHtml(markdown) {
  const lines = escapeHtml(markdown).split("\n");
  let html = "";
  let listOpen = false;
  let orderedOpen = false;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) continue;
    if (line.startsWith("|") && lines[index + 1]?.startsWith("|---")) {
      if (listOpen) html += "</ul>";
      if (orderedOpen) html += "</ol>";
      listOpen = false;
      orderedOpen = false;
      const headers = line
        .split("|")
        .slice(1, -1)
        .map((cell) => cell.trim());
      index += 1;
      const rows = [];
      while (lines[index + 1]?.startsWith("|")) {
        index += 1;
        rows.push(
          lines[index]
            .split("|")
            .slice(1, -1)
            .map((cell) => cell.trim()),
        );
      }
      html += `<div class="table-wrap"><table><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead><tbody>${rows
        .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
        .join("")}</tbody></table></div>`;
      continue;
    }
    if (line.startsWith("# ")) {
      if (listOpen) html += "</ul>";
      if (orderedOpen) html += "</ol>";
      listOpen = false;
      orderedOpen = false;
      html += `<h3>${line.slice(2)}</h3>`;
    } else if (line.startsWith("## ")) {
      if (listOpen) html += "</ul>";
      if (orderedOpen) html += "</ol>";
      listOpen = false;
      orderedOpen = false;
      html += `<h3>${line.slice(3)}</h3>`;
    } else if (line.startsWith("- ")) {
      if (!listOpen) {
        html += "<ul>";
        listOpen = true;
      }
      html += `<li>${line.slice(2)}</li>`;
    } else if (/^\d+\. /.test(line)) {
      if (!orderedOpen) {
        html += "<ol>";
        orderedOpen = true;
      }
      html += `<li>${line.replace(/^\d+\. /, "")}</li>`;
    } else {
      if (listOpen) html += "</ul>";
      if (orderedOpen) html += "</ol>";
      listOpen = false;
      orderedOpen = false;
      html += `<p>${line.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</p>`;
    }
  }
  if (listOpen) html += "</ul>";
  if (orderedOpen) html += "</ol>";
  return html;
}

elements.scenario.value = state.scenarioKey;
elements.scenario.addEventListener("change", (event) => {
  state.scenarioKey = event.target.value;
  if (state.scenarioKey === "research" && state.apiAvailable) {
    elements.llmMode.value = "api";
  }
  renderScenario();
  resetRun();
});

$$(".segmented button").forEach((button) => {
  button.addEventListener("click", () => {
    $$(".segmented button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    state.loopMode = button.dataset.loop;
    renderStaticPanels();
    renderRun();
  });
});

[elements.budget, elements.risk, $("#policyToggle"), $("#memoryToggle"), $("#ragToggle"), elements.llmMode].forEach((control) => {
  control.addEventListener("input", () => {
    renderMemory();
    renderStaticPanels();
    renderRun();
  });
  control.addEventListener("change", () => {
    renderMemory();
    renderStaticPanels();
    renderRun();
  });
});

["input", "change"].forEach((eventName) => {
  [elements.missionTopic, elements.missionAudience, elements.missionRegion, elements.missionHorizon, elements.missionSources].forEach((input) => {
    input.addEventListener(eventName, () => {
      renderMemory();
      if (!state.running && state.quality === 0) updateArtifact();
    });
  });
});

elements.startRun.addEventListener("click", runMission);
elements.stepRun.addEventListener("click", stepRun);
elements.resetRun.addEventListener("click", () => resetRun());
elements.artifactTabs.forEach((button) => {
  button.addEventListener("click", () => setArtifactTab(button.dataset.artifactTab));
});
elements.copyArtifact.addEventListener("click", async () => {
  const activePane = elements.artifactPanes.find((pane) => pane.classList.contains("is-active")) || elements.artifactOutput;
  const text = activePane.innerText;
  await navigator.clipboard.writeText(text);
  elements.copyArtifact.textContent = "Copied";
  window.setTimeout(() => {
    elements.copyArtifact.textContent = "Copy";
  }, 1200);
});

renderScenario();
resetRun();
checkApiAvailability();
