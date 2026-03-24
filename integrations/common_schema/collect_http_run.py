"""Build collected_metrics.json from http_latency_bench.py run directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .latency_stats import aggregate_latencies_seconds


def _load_latency_samples(run_dir: Path) -> List[float]:
    path = run_dir / "latency_samples.jsonl"
    if not path.exists():
        return []
    out: List[float] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not obj.get("ok"):
            continue
        lat = obj.get("latency_sec")
        if lat is not None:
            out.append(float(lat))
    return out


def build_collected_metrics_from_run_dir(
    run_dir: Path,
    *,
    system: str,
    metric_scope: str = "HTTP_INVOKE",
) -> Dict[str, Any]:
    metadata_file = run_dir / "metadata.json"
    if not metadata_file.exists():
        raise RuntimeError(f"Missing metadata file: {metadata_file}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    samples = _load_latency_samples(run_dir)

    timing_file = run_dir / "timing.json"
    wall_sec: Optional[float] = None
    if timing_file.exists():
        timing = json.loads(timing_file.read_text(encoding="utf-8"))
        wall_sec = timing.get("wall_time_sec")
        if wall_sec is not None:
            wall_sec = float(wall_sec)

    metrics, _ = aggregate_latencies_seconds(samples, wall_sec, scope=metric_scope)

    return {
        "system": system,
        "metadata": metadata,
        "source": {
            "run_dir": str(run_dir.resolve()),
            "latency_samples": str((run_dir / "latency_samples.jsonl").resolve()),
            "timing": str(timing_file.resolve()) if timing_file.exists() else None,
        },
        "unit_assumptions": {
            "latency_time_unit": "seconds",
            "throughput_unit": "operations/second",
        },
        "total_computation_time_sec": wall_sec,
        "metrics": metrics,
    }
