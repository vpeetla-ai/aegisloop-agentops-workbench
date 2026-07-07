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


if __name__ == "__main__":
    unittest.main()
