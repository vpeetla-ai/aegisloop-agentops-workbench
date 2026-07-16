# Live Demo — AegisLoop AgentOps Workbench

| Surface | URL |
|---------|-----|
| **UI (Vercel)** | https://aegisloop-agentops-workbench.vercel.app |
| **API (Render)** | https://aegisloop-api.onrender.com |

The UI is a three-column **glass-box workbench**: architecture + live SLOs (left),
honest per-agent `telemetry_spans` / `agent.execute` duration replay (center), and
the mission product console (right). Local browser mode is labeled `demo_fallback`
and does not invent live `duration_ms`.

## Deploy UI to Vercel (free)

```bash
npx vercel link --project aegisloop-agentops-workbench --yes
npx vercel --prod
```

Root `vercel.json` serves the `app/` static mission console and proxies:

- `/api/aegisloop/*` → Render FastAPI runtime
- `/api/missions/run` → Render (fallback when not streaming)

In the UI, select **uv FastAPI agents (real data)** for live market/content missions
and real span replay.

`.github/workflows/deploy.yml` auto-deploys `app/**` on push to `main` when
`VERCEL_TOKEN` / `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID` secrets are set.

## Deploy API to Render

Apply `render.yaml` in Render Blueprint. Set `ALLOWED_ORIGINS` to include your Vercel URL.

## Local

```bash
cd services/api && uv run agent-loop-api
cd app && python3 -m http.server 4173
```
