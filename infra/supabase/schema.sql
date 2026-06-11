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

create index if not exists agent_runs_created_at_idx
  on public.agent_runs (created_at desc);

create index if not exists agent_runs_mission_idx
  on public.agent_runs (mission);
