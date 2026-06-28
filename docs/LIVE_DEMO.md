# Live Demo — AegisLoop AgentOps Workbench

| Surface | URL |
|---------|-----|
| **UI (Vercel)** | https://aegisloop-agentops-workbench.vercel.app |
| **API (Render)** | https://aegisloop-api.onrender.com |

## Deploy UI to Vercel (free)

```bash
npx vercel --prod
```

Root `vercel.json` serves the `app/` static mission console and proxies:

- `/api/aegisloop/*` → Render FastAPI runtime
- `/api/missions/run` → Render (fallback when not streaming)

In the UI, select **uv FastAPI agents (real data)** for live market/content missions.

## Deploy API to Render

Apply `render.yaml` in Render Blueprint. Set `ALLOWED_ORIGINS` to include your Vercel URL.

## Local

```bash
cd services/api && uv run agent-loop-api
cd app && python3 -m http.server 4173
```
