"""Ops/observability honesty for AegisLoop public metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_loop.main import app


def test_ops_metrics_exposes_finops_and_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("AGENTFINOPS_API_URL", "https://finops.example")
    monkeypatch.setenv("MISSION_BUDGET_USD", "1.5")
    client = TestClient(app)
    resp = client.get("/api/v1/ops/metrics")
    assert resp.status_code == 200
    extra = resp.json()["extra"]
    assert extra["finops"]["configured"] is True
    assert extra["finops"]["plane"] == "agent-finops"
    assert extra["finops"]["mission_budget_usd"] == 1.5
    assert extra["langfuse"]["configured"] is False


def test_observability_status_lists_exporters(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.delenv("AGENTFINOPS_API_URL", raising=False)
    client = TestClient(app)
    resp = client.get("/api/observability/status")
    assert resp.status_code == 200
    body = resp.json()
    names = {e["name"] for e in body["exporters"]}
    assert names == {"Langfuse", "AgentFinOps", "CollaborationScorecard"}
    assert "collaboration_scorecard" in body
    assert body["planes"]["langfuse"]["configured"] is True
    assert body["planes"]["finops"]["configured"] is False


def test_ops_scorecard_endpoint(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    client = TestClient(app)
    resp = client.get("/api/v1/ops/scorecard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "aegisloop-agentops-workbench"
    assert "honesty" in body
    assert "sample" in body
