from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel

try:
    import asyncpg
except ImportError:  # pragma: no cover - local fallback when dependency is unavailable
    asyncpg = None  # type: ignore[assignment]


RUN_DIR = Path(__file__).resolve().parents[2] / "runs"
RUN_LOG = RUN_DIR / "runs.jsonl"
DATABASE_URL = os.getenv("DATABASE_URL")

_pool: Any = None
_pool_error: str | None = None


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return str(value)


def _loads_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        return json.loads(value)
    return value


async def _get_pool() -> Any:
    global _pool, _pool_error
    if not DATABASE_URL or asyncpg is None:
        return None
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4, ssl="require")
            async with _pool.acquire() as connection:
                await connection.execute(
                    """
                    create table if not exists agent_runs (
                        run_id text primary key,
                        mission text not null,
                        runtime text not null,
                        quality_score integer not null,
                        decision text not null,
                        provider_status jsonb not null default '{}'::jsonb,
                        artifact_markdown text not null default '',
                        artifacts jsonb not null default '{}'::jsonb,
                        trace jsonb not null default '[]'::jsonb,
                        evaluation jsonb not null default '{}'::jsonb,
                        cost_usd numeric not null default 0,
                        created_at timestamptz not null default now()
                    );
                    """
                )
            _pool_error = None
        except Exception as exc:
            _pool = None
            _pool_error = f"{exc.__class__.__name__}: {exc}"
            return None
    return _pool


def _persist_run_file(record: dict[str, Any]) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=_json_default, ensure_ascii=False) + "\n")


async def persist_run(record: dict[str, Any]) -> None:
    pool = await _get_pool()
    if pool is None:
        _persist_run_file(record)
        return
    evaluation = record.get("evaluation") or {}
    async with pool.acquire() as connection:
        await connection.execute(
            """
            insert into agent_runs (
                run_id, mission, runtime, quality_score, decision, provider_status,
                artifact_markdown, artifacts, trace, evaluation, cost_usd
            )
            values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb, $9::jsonb, $10::jsonb, $11)
            on conflict (run_id) do update set
                mission = excluded.mission,
                runtime = excluded.runtime,
                quality_score = excluded.quality_score,
                decision = excluded.decision,
                provider_status = excluded.provider_status,
                artifact_markdown = excluded.artifact_markdown,
                artifacts = excluded.artifacts,
                trace = excluded.trace,
                evaluation = excluded.evaluation,
                cost_usd = excluded.cost_usd;
            """,
            record["run_id"],
            record["mission"],
            record["runtime"],
            int(evaluation.get("quality_score") or 0),
            str(evaluation.get("decision") or ""),
            json.dumps(record.get("provider_status") or {}),
            record.get("artifact_markdown") or "",
            json.dumps(record.get("artifacts") or {}, default=_json_default),
            json.dumps(record.get("trace") or [], default=_json_default),
            json.dumps(evaluation, default=_json_default),
            float(record.get("cost_usd") or 0),
        )


def _list_runs_file(limit: int = 20) -> list[dict[str, Any]]:
    if not RUN_LOG.exists():
        return []
    lines = RUN_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in reversed(lines) if line.strip()]


async def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    pool = await _get_pool()
    if pool is None:
        return _list_runs_file(limit)
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            select run_id, mission, runtime, cost_usd, artifact_markdown, artifacts,
                   provider_status, trace, evaluation, created_at
            from agent_runs
            order by created_at desc
            limit $1;
            """,
            limit,
        )
    return [
        {
            "run_id": row["run_id"],
            "mission": row["mission"],
            "runtime": row["runtime"],
            "cost_usd": float(row["cost_usd"]),
            "artifact_markdown": row["artifact_markdown"],
            "artifacts": _loads_json(row["artifacts"], {}),
            "provider_status": _loads_json(row["provider_status"], {}),
            "trace": _loads_json(row["trace"], []),
            "evaluation": _loads_json(row["evaluation"], {}),
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


async def storage_status() -> str:
    pool = await _get_pool()
    if pool is not None:
        return "supabase-postgres"
    if DATABASE_URL and _pool_error:
        return f"postgres-unavailable: {_pool_error}"
    if DATABASE_URL:
        return "postgres-unavailable"
    return "jsonl-local"
