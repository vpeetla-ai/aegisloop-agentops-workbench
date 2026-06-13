FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn agent_loop.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
