FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# git is required by `uv sync` to resolve pyproject.toml's git-sourced
# dependency (agent-finops @ git+https://github.com/vpeetla-ai/agent-finops.git)
# -- the astral-sh/uv:*-bookworm-slim base image doesn't include it, and a
# manual Render deploy failed with "Git executable not found" as a result.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn agent_loop.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
