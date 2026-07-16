/**
 * AegisLoop glass-box center column — honest agent span replay.
 *
 * Live/API path: uses artifacts.telemetry_spans[].attributes.duration_ms
 * and artifacts.runtime_ms from MissionResponse (no invented timings).
 *
 * Local demo path: labeled demo_fallback — phase order from scenario agents,
 * no fake ms numbers claimed as live.
 */
(function () {
  const els = {
    pipeline: () => document.getElementById("gbPipeline"),
    gate: () => document.getElementById("gbGate"),
    log: () => document.getElementById("gbEventLog"),
    ops: () => document.getElementById("gbOpsStrip"),
    badge: () => document.getElementById("gbSourceBadge"),
  };

  let timer = null;
  let activeId = null;
  let done = new Set();

  function setBadge(source) {
    const b = els.badge();
    if (!b) return;
    b.className = "gb-source-badge";
    if (source === "live") {
      b.classList.add("live");
      b.textContent = "live spans";
    } else if (source === "fallback") {
      b.classList.add("fallback");
      b.textContent = "demo_fallback";
    } else if (source === "streaming") {
      b.classList.add("live");
      b.textContent = "streaming";
    } else {
      b.textContent = "awaiting run";
    }
  }

  function setGate(text) {
    const g = els.gate();
    if (g) g.textContent = text;
  }

  function clearLog() {
    const log = els.log();
    if (log) log.innerHTML = "";
  }

  function appendLog(line, live) {
    const log = els.log();
    if (!log) return;
    if (log.querySelector(".muted")) log.innerHTML = "";
    const row = document.createElement("div");
    if (live) row.className = "ev-live";
    row.textContent = line;
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  function setOps({ agents, runtime, decision, cost }) {
    const ops = els.ops();
    if (!ops) return;
    ops.innerHTML =
      "<span><strong>agents</strong> " +
      (agents ?? "—") +
      "</span><span><strong>runtime</strong> " +
      (runtime ?? "n/a") +
      "</span><span><strong>decision</strong> " +
      (decision ?? "awaiting") +
      "</span><span><strong>cost</strong> " +
      (cost ?? "$0.00") +
      "</span>";
  }

  function shortName(name) {
    if (!name) return "?";
    return String(name)
      .replace(/\s+Agent$/i, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 18);
  }

  function renderNodes(phases) {
    const root = els.pipeline();
    if (!root) return;
    root.innerHTML = phases
      .map((p, i) => {
        const cls =
          activeId === p.id ? " gb-active" : done.has(p.id) ? " gb-done" : "";
        const ms =
          p.duration_ms != null && p.duration_ms >= 0
            ? `<em>${Number(p.duration_ms).toFixed(0)}ms</em>`
            : "<em>—</em>";
        return (
          '<div class="gb-agent-node' +
          cls +
          '" data-phase-id="' +
          p.id +
          '">' +
          '<span class="gb-agent-idx">' +
          String(i + 1).padStart(2, "0") +
          "</span>" +
          "<div><strong>" +
          shortName(p.label) +
          "</strong><small>" +
          (p.detail || "agent.execute") +
          "</small></div>" +
          ms +
          "</div>"
        );
      })
      .join('<span class="gb-agent-arrow" aria-hidden="true">→</span>');
  }

  function highlight(id) {
    activeId = id;
    document.querySelectorAll(".gb-agent-node").forEach((n) => {
      const pid = n.getAttribute("data-phase-id");
      n.classList.toggle("gb-active", pid === activeId);
      n.classList.toggle("gb-done", done.has(pid) && pid !== activeId);
    });
  }

  function spansFromPayload(payload) {
    const spans = (payload.artifacts && payload.artifacts.telemetry_spans) || [];
    const agentSpans = spans.filter(
      (s) => s.name === "agent.execute" || (s.attributes && s.attributes.agent)
    );
    if (agentSpans.length) {
      return agentSpans.map((s, i) => {
        const attrs = s.attributes || {};
        return {
          id: "span-" + i,
          label: attrs.agent || s.name || "agent",
          detail: "status=" + (attrs.status || "ok"),
          duration_ms: attrs.duration_ms != null ? Number(attrs.duration_ms) : null,
        };
      });
    }
    // Fallback: unique agents from trace (done events), no invented ms
    const seen = new Map();
    (payload.trace || []).forEach((ev) => {
      if (!ev.agent) return;
      if (!seen.has(ev.agent)) {
        seen.set(ev.agent, {
          id: "trace-" + seen.size,
          label: ev.agent,
          detail: ev.task || ev.status || "trace",
          duration_ms: null,
        });
      }
    });
    return Array.from(seen.values());
  }

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function replayPhases(phases, opts) {
    clearTimer();
    done = new Set();
    activeId = null;
    clearLog();
    renderNodes(phases);
    setBadge(opts.source);
    setOps({
      agents: phases.length,
      runtime: opts.runtime,
      decision: opts.decision,
      cost: opts.cost,
    });

    if (!phases.length) {
      setGate("No agent spans in this response.");
      return;
    }

    let i = 0;
    let prev = null;
    const step = () => {
      if (i >= phases.length) {
        if (prev) done.add(prev);
        activeId = null;
        highlight(null);
        setGate(
          opts.source === "live"
            ? "Mission complete — replayed " +
                phases.length +
                " real agent.execute span(s)" +
                (opts.runtime ? " · " + opts.runtime : "") +
                "."
            : "Local demo complete — phase order only (no live duration_ms)."
        );
        if (typeof window.AegisLoopRefreshMetrics === "function") {
          window.AegisLoopRefreshMetrics();
        }
        return;
      }
      const p = phases[i];
      if (prev) done.add(prev);
      highlight(p.id);
      prev = p.id;
      const ms =
        p.duration_ms != null ? " " + Number(p.duration_ms).toFixed(0) + "ms" : "";
      setGate(p.label + " — " + (p.detail || "running") + ms);
      appendLog("▸ " + p.label + ms + (opts.source === "live" ? " · live" : " · fallback"), true);
      i += 1;
      timer = setTimeout(step, opts.source === "fallback" ? 280 : 360);
    };
    step();
  }

  window.GlassBox = {
    reset() {
      clearTimer();
      done = new Set();
      activeId = null;
      const root = els.pipeline();
      if (root) root.innerHTML = "";
      clearLog();
      const log = els.log();
      if (log) {
        log.innerHTML =
          '<div class="muted" style="font-style: italic">No spans yet — run a mission to replay the fleet.</div>';
      }
      setBadge("idle");
      setGate(
        "Pick a mission → Run → watch real agent.execute spans (duration_ms from the API)."
      );
      setOps({});
    },

    /** Live / API path — honest telemetry_spans */
    onMissionComplete(payload) {
      const phases = spansFromPayload(payload || {});
      const runtimeMs = payload.artifacts && payload.artifacts.runtime_ms;
      replayPhases(phases, {
        source: phases.some((p) => p.duration_ms != null) ? "live" : "fallback",
        runtime: runtimeMs != null ? runtimeMs + " ms" : "n/a",
        decision: (payload.evaluation && payload.evaluation.decision) || "—",
        cost: "$" + Number(payload.cost_usd || 0).toFixed(2),
      });
    },

    /** Streaming path — highlight agent as events arrive */
    onAgentEvent(item, agentNames) {
      setBadge("streaming");
      const names = agentNames || [];
      const phases = names.map((n, i) => ({
        id: "live-" + i,
        label: Array.isArray(n) ? n[0] : n,
        detail: Array.isArray(n) ? n[1] : "agent",
        duration_ms: null,
      }));
      if (!els.pipeline().children.length && phases.length) {
        renderNodes(phases);
      }
      const idx = names.findIndex((n) => {
        const label = Array.isArray(n) ? n[0] : n;
        return item.agent === label || (item.agent && item.agent.includes(label));
      });
      if (idx >= 0) {
        const id = "live-" + idx;
        if (item.status === "done" || item.status === "failed") done.add(id);
        highlight(id);
        appendLog(
          "▸ " + item.agent + " · " + item.status + (item.detail ? " — " + item.detail.slice(0, 80) : ""),
          true
        );
        setGate(item.agent + " — " + item.status + ": " + (item.task || item.detail || ""));
      }
    },

    /** Local browser demo — labeled fallback, no fake ms */
    onLocalAgents(agents) {
      const phases = (agents || []).map((a, i) => ({
        id: "local-" + i,
        label: a[0],
        detail: a[1] || "local demo",
        duration_ms: null,
      }));
      replayPhases(phases, {
        source: "fallback",
        runtime: "browser-local",
        decision: "demo",
        cost: "$0.00",
      });
    },
  };
})();
