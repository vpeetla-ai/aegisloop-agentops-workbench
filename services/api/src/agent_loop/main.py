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


@app.get("/health")
async def health():
    return {"status": "ok", "runtime": "uv-fastapi", "storage": await storage_status(), "cost_usd": 0}


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
    return {
        "service": "aegisloop-agentops-workbench",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": raw.get("total", 0),
        "success_rate_pct": success,
        "p95_latency_ms": int(raw.get("p95_ms", 0)) or None,
        "active_entities": raw.get("sample_size", 0),
        "slo": {"target_uptime_pct": 99.5, "success_target_pct": 95.0},
        "extra": raw,
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
