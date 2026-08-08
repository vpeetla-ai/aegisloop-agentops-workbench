import unittest

from agent_loop.metrics import aggregate_metrics, is_failed_run


class MetricsTests(unittest.TestCase):
    def test_is_failed_run_detects_trace_failure(self) -> None:
        run = {
            "budget_exceeded": False,
            "trace": [{"status": "failed"}],
            "evaluation": {"checks": {"goal": "pass"}},
        }
        self.assertTrue(is_failed_run(run))

    def test_aggregate_metrics_p50_p95_and_failure_rate(self) -> None:
        runs = [
            {"artifacts": {"runtime_ms": 100}, "trace": [], "evaluation": {"checks": {}}},
            {"artifacts": {"runtime_ms": 200}, "trace": [], "evaluation": {"checks": {}}},
            {"artifacts": {"runtime_ms": 300}, "trace": [{"status": "failed"}], "evaluation": {"checks": {}}},
            {"artifacts": {"runtime_ms": 400}, "trace": [], "evaluation": {"checks": {"x": "fail"}}},
        ]
        metrics = aggregate_metrics(runs)
        self.assertEqual(metrics["sample_size"], 4)
        self.assertEqual(metrics["failed"], 2)
        self.assertEqual(metrics["failure_rate_pct"], 50.0)
        self.assertGreater(metrics["p50_ms"], 0)
        self.assertGreaterEqual(metrics["p95_ms"], metrics["p50_ms"])

    def test_aggregate_metrics_includes_collaboration_scorecard(self) -> None:
        runs = [
            {
                "artifacts": {
                    "runtime_ms": 100,
                    "scorecard": {
                        "release_ok": True,
                        "hard_gate_failures": [],
                        "vector": {"coordination": 0.9},
                        "components": {"css": {"orphan_count": 0}},
                    },
                    "collaboration_trajectory": {"artifacts": [{"id": "a"}]},
                },
                "trace": [],
                "evaluation": {"checks": {}},
            },
            {
                "artifacts": {
                    "runtime_ms": 200,
                    "scorecard": {
                        "release_ok": False,
                        "hard_gate_failures": ["escalation_bypass"],
                        "vector": {"coordination": 0.4},
                        "components": {"css": {"orphan_count": 2}},
                    },
                    "collaboration_trajectory": {"artifacts": [{"id": "a"}, {"id": "b"}]},
                },
                "trace": [],
                "evaluation": {"checks": {"Coordination": "fail"}},
            },
        ]
        metrics = aggregate_metrics(runs)
        collab = metrics["collaboration"]
        self.assertEqual(collab["scored_runs"], 2)
        self.assertEqual(collab["hard_gate_failure_rate"], 0.5)
        self.assertEqual(collab["orphan_count"], 2)


if __name__ == "__main__":
    unittest.main()
