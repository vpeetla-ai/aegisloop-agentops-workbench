"""Mission telemetry — local spans with optional Langfuse export."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

import httpx


@dataclass
class MissionTelemetry:
    run_id: str
    mission: str
    spans: list[dict[str, object]] = field(default_factory=list)

    def record(self, name: str, **attributes: object) -> None:
        self.spans.append(
            {
                "name": name,
                "run_id": self.run_id,
                "mission": self.mission,
                "attributes": attributes,
                "ts": time.time(),
            }
        )

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
            status = "ok"
        except Exception:
            status = "error"
            raise
        finally:
            self.record(
                name,
                **attributes,
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

    async def export_langfuse(self) -> str | None:
        """Best-effort Langfuse ingest when LANGFUSE_* env vars are set."""
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        public = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret = os.getenv("LANGFUSE_SECRET_KEY")
        if not public or not secret:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{host.rstrip('/')}/api/public/ingestion",
                    auth=(public, secret),
                    json={
                        "batch": [
                            {
                                "id": f"{self.run_id}-{index}",
                                "type": "span-create",
                                "timestamp": span["ts"],
                                "body": {
                                    "id": f"{self.run_id}-{index}",
                                    "traceId": self.run_id,
                                    "name": span["name"],
                                    "metadata": span["attributes"],
                                },
                            }
                            for index, span in enumerate(self.spans)
                        ]
                    },
                )
                response.raise_for_status()
                return "exported"
        except Exception:
            return "failed"
