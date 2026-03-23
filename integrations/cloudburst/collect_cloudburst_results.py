#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Optional


LATENCY_BLOCK_RE = re.compile(
    r"(?P<ident>[A-Z0-9_]+)\s+LATENCY:\n"
    r"\tsample size:\s+(?P<sample_size>\d+)\n"
    r"\tTHROUGHPUT:\s+(?P<throughput>[0-9.]+)\n"
    r"\tmean:\s+(?P<mean>[0-9.]+),\s+median:\s+(?P<median>[0-9.]+)\n"
    r"\tmin/max:\s+\((?P<min>[0-9.]+),\s+(?P<max>[0-9.]+)\)\n"
    r"\tp25/p75:\s+\((?P<p25>[0-9.]+),\s+(?P<p75>[0-9.]+)\)\n"
    r"\tp5/p95:\s+\((?P<p5>[0-9.]+),\s+(?P<p95>[0-9.]+)\)\n"
    r"\tp1/p99:\s+\((?P<p1>[0-9.]+),\s+(?P<p99>[0-9.]+)\)",
    re.MULTILINE,
)

TOTAL_TIME_RE = re.compile(r"Total computation time:\s*(?P<total>[0-9.]+)")


def parse_total_computation_time(text: str) -> Optional[float]:
    match = TOTAL_TIME_RE.search(text)
    if not match:
        return None
    return float(match.group("total"))


def parse_latency_blocks(text: str) -> Dict[str, dict]:
    metrics: Dict[str, dict] = {}
    for match in LATENCY_BLOCK_RE.finditer(text):
        ident = match.group("ident")
        metrics[ident] = {
            "sample_size": int(match.group("sample_size")),
            "throughput_ops_per_sec": float(match.group("throughput")),
            "mean": float(match.group("mean")),
            "p50": float(match.group("median")),
            "p95": float(match.group("p95")),
            "p99": float(match.group("p99")),
            "min": float(match.group("min")),
            "max": float(match.group("max")),
            "p25": float(match.group("p25")),
            "p75": float(match.group("p75")),
            "p5": float(match.group("p5")),
            "p1": float(match.group("p1")),
        }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Collect Cloudburst benchmark metrics from run logs.")
    parser.add_argument("--run-dir", required=True, help="Run directory containing metadata.json and client_stdout.log")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    metadata_file = run_dir / "metadata.json"
    stdout_file = run_dir / "client_stdout.log"

    if not metadata_file.exists():
        raise RuntimeError(f"Missing metadata file: {metadata_file}")
    if not stdout_file.exists():
        raise RuntimeError(f"Missing client log file: {stdout_file}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    stdout_text = stdout_file.read_text(encoding="utf-8", errors="replace")

    parsed = {
        "system": "cloudburst",
        "metadata": metadata,
        "source": {
            "run_dir": str(run_dir.resolve()),
            "client_stdout_log": str(stdout_file.resolve()),
        },
        "unit_assumptions": {
            "latency_time_unit": "seconds",
            "throughput_unit": "operations/second",
        },
        "total_computation_time_sec": parse_total_computation_time(stdout_text),
        "metrics": parse_latency_blocks(stdout_text),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote collected metrics to {out_path}")


if __name__ == "__main__":
    main()
