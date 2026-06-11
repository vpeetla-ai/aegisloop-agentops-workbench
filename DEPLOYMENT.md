# AegisLoop Deployment Runbook

Target production shape:

```text
https://venkat-ai.com/projects/aegisloop
  -> portfolio-hosted AegisLoop UI

https://venkat-ai.com/api/aegisloop/*
  -> Vercel rewrite to separately deployed FastAPI backend

Supabase Postgres
  -> durable agent run history
```

## 1. Supabase Postgres

Create a Supabase project, then run:

```sql
-- infra/supabase/schema.sql
create table if not exists public.agent_runs (
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
```

Use the Supabase pooled Postgres connection string as `DATABASE_URL`.

## 2. Backend Service

The backend is deployable as a Docker web service from `services/api`.

Required environment variables:

```bash
DATABASE_URL=postgresql://...
ALLOWED_ORIGINS=https://venkat-ai.com,https://www.venkat-ai.com
```

Render setup:

- Service type: Web Service
- Runtime: Docker
- Root directory: `services/api`
- Health check path: `/health`
- Port: `8000`

The API exposes:

```text
GET  /health
GET  /api/missions
GET  /api/runs
POST /api/missions/run
POST /api/missions/stream
```

## 3. Vercel Portfolio Rewrite

In the portfolio repo, add a rewrite from your public domain to the backend:

```ts
async rewrites() {
  return [
    {
      source: "/api/aegisloop/:path*",
      destination: `${process.env.AEGISLOOP_API_ORIGIN}/:path*`,
    },
  ];
}
```

Set this Vercel environment variable:

```bash
AEGISLOOP_API_ORIGIN=https://YOUR-AEGISLOOP-BACKEND.example.com
```

The deployed AegisLoop frontend uses `/api/aegisloop` automatically outside localhost.

## 4. Portfolio URL

Recommended route:

```text
https://venkat-ai.com/projects/aegisloop
```

Embed or serve the static AegisLoop app from the portfolio route, and add a visible project card/link from `/projects`.

## 5. Smoke Tests

After deploy:

```bash
curl https://YOUR-AEGISLOOP-BACKEND.example.com/health
curl https://venkat-ai.com/api/aegisloop/health
```

Expected:

```json
{"status":"ok","runtime":"uv-fastapi","storage":"supabase-postgres","cost_usd":0}
```

Then run the stock-market mission from:

```text
https://venkat-ai.com/projects/aegisloop
```
