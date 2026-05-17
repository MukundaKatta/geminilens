"""Lightweight drift signals computed over recent traces. Three signals:
- latency drift: rolling p95 vs baseline p95
- cost drift: rolling mean cost vs baseline mean
- response-length drift: rolling mean output_tokens vs baseline mean

Each returns a score in [0, +inf) — values >1 indicate the rolling window is
worse than the baseline by that factor."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DriftReport:
    samples_rolling: int
    samples_baseline: int
    latency_p95_rolling_ms: float
    latency_p95_baseline_ms: float
    cost_mean_rolling_usd: float
    cost_mean_baseline_usd: float
    out_tokens_mean_rolling: float
    out_tokens_mean_baseline: float
    latency_drift: float
    cost_drift: float
    output_drift: float


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, int(round(0.95 * (len(xs) - 1))))
    return xs[k]


def _ratio(numer: float, denom: float) -> float:
    if denom <= 0:
        return 0.0 if numer <= 0 else float("inf")
    return numer / denom


def compute_drift(
    traces: Iterable[dict],
    rolling: int = 20,
    baseline: int = 80,
) -> DriftReport:
    """Compute drift on the most recent `rolling` traces vs the `baseline`
    traces immediately preceding them."""
    rows = [t for t in traces if not t.get("error")]
    if len(rows) < rolling + 1:
        return DriftReport(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    roll = rows[-rolling:]
    base_start = max(0, len(rows) - rolling - baseline)
    base = rows[base_start : len(rows) - rolling]
    if not base:
        return DriftReport(len(roll), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    lat_roll = _p95([float(r.get("latency_ms", 0)) for r in roll])
    lat_base = _p95([float(r.get("latency_ms", 0)) for r in base])
    cost_roll = statistics.fmean([float(r.get("cost_usd", 0)) for r in roll]) if roll else 0.0
    cost_base = statistics.fmean([float(r.get("cost_usd", 0)) for r in base]) if base else 0.0
    out_roll = statistics.fmean([float(r.get("output_tokens", 0)) for r in roll]) if roll else 0.0
    out_base = statistics.fmean([float(r.get("output_tokens", 0)) for r in base]) if base else 0.0

    return DriftReport(
        samples_rolling=len(roll),
        samples_baseline=len(base),
        latency_p95_rolling_ms=round(lat_roll, 2),
        latency_p95_baseline_ms=round(lat_base, 2),
        cost_mean_rolling_usd=round(cost_roll, 6),
        cost_mean_baseline_usd=round(cost_base, 6),
        out_tokens_mean_rolling=round(out_roll, 2),
        out_tokens_mean_baseline=round(out_base, 2),
        latency_drift=round(_ratio(lat_roll, lat_base), 3),
        cost_drift=round(_ratio(cost_roll, cost_base), 3),
        output_drift=round(_ratio(out_roll, out_base), 3),
    )
