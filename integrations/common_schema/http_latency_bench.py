#!/usr/bin/env python3
"""
Sequential HTTP requests; write latency_samples.jsonl + timing.json for collect_*_results.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repeated HTTP calls and record per-request latency.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Run directory (must exist)")
    parser.add_argument("--url", required=True, help="Full URL (e.g. API Gateway invoke URL)")
    parser.add_argument("--count", type=int, default=100, help="Number of requests")
    parser.add_argument("--method", default="POST", help="HTTP method")
    parser.add_argument("--body-json", default="{}", help="JSON request body for POST/PATCH/PUT")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    args = parser.parse_args()

    run_dir = args.run_dir
    if not run_dir.is_dir():
        print(f"run-dir does not exist: {run_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        body_obj: Dict[str, Any] = json.loads(args.body_json) if args.body_json.strip() else {}
    except json.JSONDecodeError as e:
        print(f"Invalid --body-json: {e}", file=sys.stderr)
        sys.exit(1)

    samples_path = run_dir / "latency_samples.jsonl"
    method = args.method.upper()
    wall_start = time.perf_counter()
    statuses: List[int] = []

    with open(samples_path, "w", encoding="utf-8") as out:
        for _ in range(args.count):
            t0 = time.perf_counter()
            try:
                if method == "GET":
                    r = requests.get(
                        args.url, timeout=args.timeout, verify=not args.insecure
                    )
                elif method in ("POST", "PUT", "PATCH"):
                    r = requests.request(
                        method,
                        args.url,
                        json=body_obj,
                        headers={"Content-Type": "application/json"},
                        timeout=args.timeout,
                        verify=not args.insecure,
                    )
                else:
                    r = requests.request(
                        method,
                        args.url,
                        timeout=args.timeout,
                        verify=not args.insecure,
                    )
                dt = time.perf_counter() - t0
                statuses.append(r.status_code)
                rec = {"latency_sec": dt, "http_status": r.status_code, "ok": r.ok}
            except requests.RequestException as e:
                dt = time.perf_counter() - t0
                rec = {"latency_sec": dt, "http_status": None, "ok": False, "error": str(e)}
            out.write(json.dumps(rec) + "\n")

    wall_sec = time.perf_counter() - wall_start
    timing = {
        "wall_time_sec": wall_sec,
        "successful_requests": sum(1 for s in statuses if 200 <= s < 300),
        "total_requests": args.count,
    }
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")

    # Human-readable summary for logs
    log_path = run_dir / "client_stdout.log"
    ok_n = timing["successful_requests"]
    log_path.write_text(
        f"HTTP {method} {args.url}\n"
        f"requests={args.count} success_2xx={ok_n} wall_time_sec={wall_sec:.6f}\n"
        f"latency_samples: {samples_path.name}\n",
        encoding="utf-8",
    )
    print(f"Wrote {samples_path} and {run_dir / 'timing.json'}")


if __name__ == "__main__":
    main()
