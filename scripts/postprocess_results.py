#!/usr/bin/env python3
"""
Post-processing script for stateful benchmark results.

Reads SeBS experiment JSON output and extracts:
- Latency stats (P50/P95/P99) for client, state write, state read
- Throughput (invocations / wall-clock duration)
- Cost estimates (Lambda billing or EC2 hourly rate / throughput)
- CSV export for plotting

Usage:
    python3 scripts/postprocess_results.py <results_json> [--csv output.csv] [--ec2-hourly-rate 0.34]
    python3 scripts/postprocess_results.py /tmp/sebs-boki-test/perf-cost/warm_results.json
    python3 scripts/postprocess_results.py results/ --csv all_results.csv  # process directory
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


def percentile(values: List[float], p: float) -> float:
    s = sorted(values)
    idx = int(p / 100.0 * len(s))
    return s[min(idx, len(s) - 1)]


def load_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_invocations(data: dict) -> Dict[str, list]:
    """Extract invocation data from SeBS result JSON."""
    inv_key = "_invocations" if "_invocations" in data else "invocations"
    invocations = data.get(inv_key, {})

    results = {}
    for func_name, func_invocations in invocations.items():
        entries = []
        for req_id, result in func_invocations.items():
            times = result.get("times", {})
            output = result.get("output", {})
            measurement = output.get("measurement", {})
            stats = result.get("stats", {})
            billing = result.get("billing", {})

            entries.append({
                "request_id": req_id,
                "client_us": times.get("client", 0),
                "benchmark_us": times.get("benchmark", 0),
                "http_startup_s": times.get("http_startup", 0),
                "state_write_us": measurement.get("state_write_lat_us", 0),
                "state_read_us": measurement.get("state_read_lat_us", 0),
                "compute_us": measurement.get("compute_time_us", 0),
                "state_size_kb": measurement.get("state_size_kb", 0),
                "state_ops": measurement.get("state_ops", 0),
                "is_cold": stats.get("cold_start", False),
                "gb_seconds": billing.get("_gb_seconds", 0),
            })
        results[func_name] = entries
    return results


def compute_stats(entries: list) -> dict:
    """Compute summary statistics for a list of invocation entries."""
    if not entries:
        return {}

    client = [e["client_us"] for e in entries]
    write = [e["state_write_us"] for e in entries]
    read = [e["state_read_us"] for e in entries]
    cold_count = sum(1 for e in entries if e["is_cold"])

    def stats_block(values, unit="us"):
        s = sorted(values)
        return {
            "mean": np.mean(s),
            "median": np.median(s),
            "std": np.std(s),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
            "p99": percentile(values, 99),
            "min": min(s),
            "max": max(s),
            "unit": unit,
        }

    return {
        "count": len(entries),
        "cold_starts": cold_count,
        "client_latency": stats_block(client),
        "state_write": stats_block(write),
        "state_read": stats_block(read),
    }


def compute_throughput(data: dict) -> Optional[float]:
    """Compute throughput as invocations / wall-clock seconds."""
    begin = data.get("begin_time")
    end = data.get("end_time")
    if begin is None or end is None:
        return None

    duration_s = end - begin
    if duration_s <= 0:
        return None

    inv_key = "_invocations" if "_invocations" in data else "invocations"
    total_invocations = sum(
        len(func_inv) for func_inv in data.get(inv_key, {}).values()
    )
    return total_invocations / duration_s


def compute_cost(entries: list, ec2_hourly_rate: Optional[float] = None,
                 throughput: Optional[float] = None) -> dict:
    """Compute cost metrics."""
    cost = {}

    # Lambda cost from billing
    gb_seconds = [e["gb_seconds"] for e in entries if e["gb_seconds"] > 0]
    if gb_seconds:
        total_gb_s = sum(gb_seconds)
        # AWS Lambda pricing: $0.0000166667 per GB-second
        lambda_cost = total_gb_s * 0.0000166667
        cost["lambda_gb_seconds"] = total_gb_s
        cost["lambda_cost_usd"] = lambda_cost
        cost["lambda_cost_per_invocation_usd"] = lambda_cost / len(entries)

    # EC2 cost (Boki/Cloudburst)
    if ec2_hourly_rate and throughput and throughput > 0:
        cost_per_second = ec2_hourly_rate / 3600
        cost["ec2_cost_per_invocation_usd"] = cost_per_second / throughput
        cost["ec2_hourly_rate_usd"] = ec2_hourly_rate

    return cost


def format_report(func_name: str, stats: dict, throughput: Optional[float],
                  cost: dict, source_file: str) -> str:
    """Format a human-readable report."""
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"Results: {func_name}")
    lines.append(f"Source:  {source_file}")
    lines.append(f"{'=' * 60}")
    lines.append(f"Invocations: {stats['count']}  |  Cold starts: {stats['cold_starts']}")

    if throughput:
        lines.append(f"Throughput:   {throughput:.2f} invocations/sec")

    for label, key in [
        ("Client latency", "client_latency"),
        ("State write", "state_write"),
        ("State read", "state_read"),
    ]:
        s = stats[key]
        scale = 1000 if s["median"] > 10000 else 1  # show in ms if > 10ms
        unit = "ms" if scale == 1000 else "us"
        lines.append(f"\n{label} ({unit}):")
        lines.append(
            f"  P50={s['p50']/scale:.1f}  P95={s['p95']/scale:.1f}  "
            f"P99={s['p99']/scale:.1f}  mean={s['mean']/scale:.1f}  "
            f"std={s['std']/scale:.1f}"
        )

    if cost:
        lines.append("\nCost:")
        if "lambda_cost_per_invocation_usd" in cost:
            lines.append(
                f"  Lambda: ${cost['lambda_cost_per_invocation_usd']:.8f}/invocation "
                f"({cost['lambda_gb_seconds']:.4f} GB-s total)"
            )
        if "ec2_cost_per_invocation_usd" in cost:
            lines.append(
                f"  EC2: ${cost['ec2_cost_per_invocation_usd']:.8f}/invocation "
                f"(at ${cost['ec2_hourly_rate_usd']:.2f}/hr)"
            )

    return "\n".join(lines)


def write_csv(all_entries: List[dict], output_path: str):
    """Write all invocation data to CSV for plotting."""
    if not all_entries:
        return

    fieldnames = [
        "source", "function", "request_id", "client_us", "benchmark_us",
        "http_startup_s", "state_write_us", "state_read_us", "compute_us",
        "state_size_kb", "state_ops", "is_cold", "gb_seconds",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_entries)

    print(f"\nCSV written to {output_path} ({len(all_entries)} rows)")


def process_file(path: str, ec2_hourly_rate: Optional[float] = None) -> List[dict]:
    """Process a single results JSON file. Returns entries for CSV."""
    data = load_results(path)
    invocations = extract_invocations(data)
    throughput = compute_throughput(data)
    all_csv_entries = []

    for func_name, entries in invocations.items():
        stats = compute_stats(entries)
        cost = compute_cost(entries, ec2_hourly_rate, throughput)
        report = format_report(func_name, stats, throughput, cost, path)
        print(report)
        print()

        for e in entries:
            all_csv_entries.append({
                "source": os.path.basename(path),
                "function": func_name,
                **{k: v for k, v in e.items()},
            })

    return all_csv_entries


def main():
    parser = argparse.ArgumentParser(description="Post-process SeBS stateful benchmark results")
    parser.add_argument("path", help="Results JSON file or directory of JSON files")
    parser.add_argument("--csv", help="Output CSV path for plotting")
    parser.add_argument(
        "--ec2-hourly-rate", type=float, default=None,
        help="EC2 instance hourly rate in USD (for Boki/Cloudburst cost calculation)"
    )
    args = parser.parse_args()

    path = Path(args.path)
    all_csv_entries = []

    if path.is_file():
        all_csv_entries = process_file(str(path), args.ec2_hourly_rate)
    elif path.is_dir():
        for json_file in sorted(path.glob("**/*_results.json")):
            all_csv_entries.extend(process_file(str(json_file), args.ec2_hourly_rate))
    else:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    if args.csv and all_csv_entries:
        write_csv(all_csv_entries, args.csv)


if __name__ == "__main__":
    main()
