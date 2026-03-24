"""Aggregate raw latency samples (seconds) into Cloudburst-compatible metric dicts."""

from __future__ import annotations

from typing import List, Optional, Tuple


def _percentile_nearest_rank(sorted_vals: List[float], p: float) -> float:
    """Linear interpolation percentile, p in [0, 100]."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = min(f + 1, n - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def aggregate_latencies_seconds(
    latencies: List[float],
    wall_time_sec: Optional[float],
    scope: str = "HTTP_INVOKE",
) -> Tuple[dict, dict]:
    """
    Returns (metrics_dict_for_scope, primary_block).
    Inner values match collect_cloudburst_results / *_to_common_schema expectations (seconds).
    """
    if not latencies:
        return {}, {}

    s = sorted(latencies)
    n = len(s)
    mean = sum(s) / n

    def rf(x: float) -> float:
        return round(float(x), 9)

    tput = (n / float(wall_time_sec)) if wall_time_sec and wall_time_sec > 0 else None
    block = {
        "sample_size": n,
        "throughput_ops_per_sec": rf(tput) if tput is not None else None,
        "mean": rf(mean),
        "p50": rf(_percentile_nearest_rank(s, 50)),
        "p95": rf(_percentile_nearest_rank(s, 95)),
        "p99": rf(_percentile_nearest_rank(s, 99)),
        "min": rf(s[0]),
        "max": rf(s[-1]),
        "p25": rf(_percentile_nearest_rank(s, 25)),
        "p75": rf(_percentile_nearest_rank(s, 75)),
        "p5": rf(_percentile_nearest_rank(s, 5)),
        "p1": rf(_percentile_nearest_rank(s, 1)),
    }
    return {scope: block}, block
