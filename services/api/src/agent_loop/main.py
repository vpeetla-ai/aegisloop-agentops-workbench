from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent_loop.models import MissionRequest
from agent_loop.runtime import encode_stream_event, run_mission, stream_mission
from agent_loop.storage import aggregate_run_metrics, list_runs, storage_status

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8888",
    "http://127.0.0.1:8888",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://venkat-ai.com",
    "https://www.venkat-ai.com",
]


def allowed_origins() -> list[str]:
    configured = os.getenv("ALLOWED_ORIGINS")
    if not configured:
        return DEFAULT_ALLOWED_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(
    title="AegisLoop Runtime",
    version="0.1.0",
    description="Production-grade orchestrated agent fleet runtime.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Gate /api/missions/run and /api/missions/stream — these call a real LLM and
    incur real cost per hit. Only enforced when AEGISLOOP_API_KEY is set (dev/demo
    default stays open)."""
    expected = os.getenv("AEGISLOOP_API_KEY")
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def _obs_planes() -> dict[str, object]:
    langfuse = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    finops_url = (os.getenv("AGENTFINOPS_API_URL") or "").strip()
    return {
        "langfuse": {
            "configured": langfuse,
            "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com") if langfuse else None,
        },
        "finops": {
            "configured": bool(finops_url),
            "url_configured": bool(finops_url),
            "mission_budget_usd": float(os.getenv("MISSION_BUDGET_USD", "2.0")),
            "enforcement": "halt_dispatch_on_breach",
            "plane": "agent-finops",
        },
        "api_key_gated": bool(os.getenv("AEGISLOOP_API_KEY")),
    }


@app.get("/health")
async def health():
    planes = _obs_planes()
    return {
        "status": "ok",
        "runtime": "uv-fastapi",
        "storage": await storage_status(),
        "cost_usd": 0,
        "langfuse_configured": planes["langfuse"]["configured"],
        "finops_configured": planes["finops"]["configured"],
        "api_key_gated": planes["api_key_gated"],
    }


@app.get("/api/missions")
async def missions():
    return {
        "missions": ["research", "content", "incident", "migration", "security"],
        "runtime_modes": ["local", "ollama", "gateway"],
        "default": "research",
    }


@app.get("/api/runs")
async def runs(limit: int = 20):
    return {"runs": await list_runs(limit)}


@app.get("/api/v1/ops/metrics")
async def ops_metrics(limit: int = 100, mission: str | None = None):
    raw = await aggregate_run_metrics(limit=limit, mission=mission)
    success = round(100.0 - raw.get("failure_rate_pct", 0.0), 1)
    planes = _obs_planes()
    return {
        "service": "aegisloop-agentops-workbench",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": raw.get("total", 0),
        "success_rate_pct": success,
        "p95_latency_ms": int(raw.get("p95_ms", 0)) or None,
        "active_entities": raw.get("sample_size", 0),
        "slo": {"target_uptime_pct": 99.5, "success_target_pct": 95.0},
        "extra": {**raw, **planes},
    }


@app.get("/api/v1/ops/scorecard")
async def ops_scorecard(limit: int = 20, mission: str | None = None):
    """Panel-facing collaboration vector summary (Stage-4 honesty surface)."""
    runs = await list_runs(limit)
    if mission:
        runs = [run for run in runs if run.get("mission") == mission]
    latest = None
    hard_gate_fails = 0
    scored = 0
    for run in runs:
        artifacts = run.get("artifacts") or {}
        scorecard = artifacts.get("scorecard")
        if not isinstance(scorecard, dict):
            continue
        scored += 1
        if scorecard.get("hard_gate_failures"):
            hard_gate_fails += 1
        if latest is None:
            latest = {
                "run_id": run.get("run_id"),
                "mission": run.get("mission"),
                "decision": (run.get("evaluation") or {}).get("decision"),
                "quality_score": (run.get("evaluation") or {}).get("quality_score"),
                "release_ok": scorecard.get("release_ok"),
                "hard_gate_failures": scorecard.get("hard_gate_failures") or [],
                "vector": scorecard.get("vector") or {},
            }
    metrics = await aggregate_run_metrics(limit=max(limit, 50), mission=mission)
    return {
        "service": "aegisloop-agentops-workbench",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "latest": latest,
        "sample": {
            "runs": len(runs),
            "scored": scored,
            "hard_gate_failure_rate": round(hard_gate_fails / scored, 3) if scored else None,
        },
        "collaboration": metrics.get("collaboration"),
        "honesty": (
            "release_ok false or hard_gate_failures non-empty means ship is blocked — "
            "task success alone is not enough."
        ),
    }


@app.get("/api/observability/status")
async def observability_status():
    planes = _obs_planes()
    scorecard = await ops_scorecard(limit=10)
    return {
        "source_of_truth": "AegisLoop mission run store (Postgres/SQLite) + in-response traces",
        "exporters": [
            {
                "name": "Langfuse",
                "state": "configured" if planes["langfuse"]["configured"] else "unset",
                "detail": "Optional LANGFUSE_* mission span export",
            },
            {
                "name": "AgentFinOps",
                "state": "configured" if planes["finops"]["configured"] else "local_fallback",
                "detail": "Real token metering; breach halts further agent dispatch",
            },
            {
                "name": "CollaborationScorecard",
                "state": "active",
                "detail": "CSS/TUE vector + hard gates on every mission evaluate()",
            },
        ],
        "planes": planes,
        "collaboration_scorecard": {
            "latest": scorecard.get("latest"),
            "sample": scorecard.get("sample"),
        },
        "recommendation": (
            "Use FinOps for cost truth; Langfuse for durable panel receipts; "
            "collaboration hard gates block ship even when the final answer looks correct."
        ),
    }


@app.get("/api/metrics")
async def metrics(limit: int = 100, mission: str | None = None):
    return await aggregate_run_metrics(limit=limit, mission=mission)


@app.post("/api/missions/run", dependencies=[Depends(_require_api_key)])
async def run_mission_endpoint(request: MissionRequest):
    return await run_mission(request)


@app.post("/api/missions/stream", dependencies=[Depends(_require_api_key)])
async def stream_mission_endpoint(request: MissionRequest):
    async def event_stream():
        async for payload in stream_mission(request):
            yield encode_stream_event(payload)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def serve() -> None:
    uvicorn.run("agent_loop.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    serve()
