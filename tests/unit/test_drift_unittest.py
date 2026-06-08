"""Standard-library unittest coverage for geminilens.drift."""

import os
import sys
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))

from geminilens.drift import DriftReport, compute_drift  # noqa: E402


def _trace(latency_ms=100.0, cost_usd=0.001, output_tokens=200, error=None):
    return {
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "output_tokens": output_tokens,
        "error": error,
    }


class ComputeDriftTests(unittest.TestCase):
    def test_too_few_traces_returns_empty_report(self):
        report = compute_drift([_trace() for _ in range(5)], rolling=20, baseline=80)
        self.assertIsInstance(report, DriftReport)
        self.assertEqual(report.samples_rolling, 0)
        self.assertEqual(report.samples_baseline, 0)
        self.assertEqual(report.latency_drift, 0)

    def test_no_drift_when_windows_identical(self):
        traces = [_trace(latency_ms=100, cost_usd=0.002, output_tokens=300) for _ in range(50)]
        report = compute_drift(traces, rolling=10, baseline=20)
        self.assertEqual(report.samples_rolling, 10)
        self.assertEqual(report.samples_baseline, 20)
        self.assertAlmostEqual(report.latency_drift, 1.0, places=3)
        self.assertAlmostEqual(report.cost_drift, 1.0, places=3)
        self.assertAlmostEqual(report.output_drift, 1.0, places=3)

    def test_latency_regression_is_detected(self):
        baseline = [_trace(latency_ms=100) for _ in range(20)]
        rolling = [_trace(latency_ms=400) for _ in range(10)]
        report = compute_drift(baseline + rolling, rolling=10, baseline=20)
        # Rolling p95 is ~4x the baseline p95.
        self.assertGreater(report.latency_drift, 3.0)
        self.assertEqual(report.latency_p95_rolling_ms, 400.0)
        self.assertEqual(report.latency_p95_baseline_ms, 100.0)

    def test_cost_regression_is_detected(self):
        baseline = [_trace(cost_usd=0.001) for _ in range(20)]
        rolling = [_trace(cost_usd=0.005) for _ in range(10)]
        report = compute_drift(baseline + rolling, rolling=10, baseline=20)
        self.assertAlmostEqual(report.cost_drift, 5.0, places=3)

    def test_errored_traces_are_excluded(self):
        # 10 good baseline + 10 good rolling, plus error rows that must be ignored.
        rows = []
        for _ in range(20):
            rows.append(_trace(latency_ms=100))
            rows.append(_trace(latency_ms=99999, error="boom"))
        for _ in range(10):
            rows.append(_trace(latency_ms=100))
        report = compute_drift(rows, rolling=10, baseline=20)
        # Error rows would blow up p95 if counted; they must not.
        self.assertLess(report.latency_p95_rolling_ms, 1000)
        self.assertAlmostEqual(report.latency_drift, 1.0, places=3)

    def test_missing_keys_default_to_zero(self):
        # Traces missing fields should not raise.
        rows = [{} for _ in range(40)]
        report = compute_drift(rows, rolling=10, baseline=20)
        self.assertEqual(report.cost_mean_rolling_usd, 0.0)
        self.assertEqual(report.out_tokens_mean_rolling, 0.0)

    def test_report_is_immutable(self):
        report = compute_drift([_trace() for _ in range(40)], rolling=10, baseline=20)
        with self.assertRaises(Exception):
            report.latency_drift = 9.0  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
