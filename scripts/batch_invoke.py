#!/usr/bin/env python3
"""
Batch HTTP invocation script for pre-deployed serverless functions.

Produces SeBS-compatible JSON output that postprocess_results.py can read.
Works for Lambda (API Gateway), Boki (gateway), Restate, or any HTTP endpoint.

If the URL contains {key}, each invocation substitutes a unique key (for Restate
Virtual Object routing). Otherwise the URL is used as-is.

Usage:
    python3 scripts/batch_invoke.py <url> [options]

Examples:
    # Lambda baseline: 200 warm invocations, 64KB state, concurrency 10
    python3 scripts/batch_invoke.py https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/ \
        --reps 200 --concurrency 10 --state-size-kb 64 --output results/lambda-c10.json

    # Boki: 200 invocations at concurrency 50
    python3 scripts/batch_invoke.py http://13.63.165.110:8080/function/statefulBench \
        --reps 200 --concurrency 50 --state-size-kb 64 --output results/boki-c50.json

    # Restate: unique key per invocation (Virtual Object routing)
    python3 scripts/batch_invoke.py 'http://server:8080/statefulBench/{key}/run' \
        --reps 200 --concurrency 10 --state-size-kb 64 --output results/restate-c10.json
"""

import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO

try:
    import pycurl
except ImportError:  # pragma: no cover - exercised only when pycurl is absent
    pycurl = None
import requests


def build_payload(protocol: str, state_key: str, state_size_kb: int, ops: int, request_id: str) -> dict:
    if protocol == "gresse":
        return {
            "type": "Mutation",
            "params": {
                "Run": {
                    "state_key": state_key,
                    "state_size_kb": state_size_kb,
                    "ops": ops,
                }
            },
        }
    return {
        "state_key": state_key,
        "state_size_kb": state_size_kb,
        "ops": ops,
        "request_id": request_id,
    }


def normalize_output(protocol: str, output: dict) -> dict:
    if protocol != "gresse":
        return output

    if not isinstance(output, dict):
        return {"error": "non-dict gresse response"}

    ok = output.get("Ok")
    if isinstance(ok, dict):
        mutation = ok.get("Mutation")
        if isinstance(mutation, dict):
            return mutation
        query = ok.get("Query")
        if isinstance(query, dict):
            return query

    err = output.get("Err")
    if err is not None:
        return {"error": err}

    return output


def benchmark_duration_us(output: dict) -> int:
    begin = output.get("begin")
    end = output.get("end")
    if begin is None or end is None:
        return 0
    try:
        begin_val = float(begin)
        end_val = float(end)
    except (TypeError, ValueError):
        return 0
    delta = end_val - begin_val
    if delta <= 0:
        return 0
    if begin_val > 1e12 and end_val > 1e12:
        return int(delta)
    return int(delta * 1e6)


def invoke_once(url: str, payload: dict, protocol: str = "standard", retries: int = 2) -> dict:
    """Single HTTP invocation with timing. Retries on transient errors."""
    for attempt in range(retries + 1):
        try:
            return _invoke_once_inner(url, payload, protocol)
        except pycurl.error as e:
            if attempt < retries:
                time.sleep(0.5)
                continue
            # Final attempt failed — return error result
            return {
                "request_id": payload.get("request_id", uuid.uuid4().hex),
                "times": {"client": 0, "benchmark": 0, "http_startup": 0, "http_first_byte_return": 0},
                "output": {"error": str(e)},
                "stats": {"cold_start": False, "failure": True},
                "billing": {"_billed_time": None, "_gb_seconds": 0, "_memory": None},
                "provider_times": {"execution": 0, "initialization": 0},
            }


def _invoke_once_inner(url: str, payload: dict, protocol: str = "standard") -> dict:
    """Single HTTP invocation with timing."""
    if pycurl is None:
        return _invoke_once_requests(url, payload, protocol)

    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
    c.setopt(pycurl.POST, 1)
    c.setopt(pycurl.POSTFIELDS, json.dumps(payload))
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_1_1)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.TIMEOUT, 30)

    data = BytesIO()
    c.setopt(pycurl.WRITEFUNCTION, data.write)

    begin = datetime.now()
    c.perform()
    end = datetime.now()

    status_code = c.getinfo(pycurl.RESPONSE_CODE)
    conn_time = c.getinfo(pycurl.PRETRANSFER_TIME)
    first_byte = c.getinfo(pycurl.STARTTRANSFER_TIME)
    c.close()

    client_us = int((end - begin).total_seconds() * 1e6)

    try:
        output = json.loads(data.getvalue())
    except (json.JSONDecodeError, ValueError):
        output = {"error": data.getvalue().decode("utf-8", errors="replace")[:200]}
    output = normalize_output(protocol, output)

    request_id = output.get("request_id", payload.get("request_id", uuid.uuid4().hex))

    return {
        "request_id": request_id,
        "times": {
            "client": client_us,
            "benchmark": benchmark_duration_us(output),
            "http_startup": conn_time,
            "http_first_byte_return": first_byte,
        },
        "output": output,
        "stats": {
            "cold_start": output.get("is_cold", False),
            "failure": status_code != 200,
        },
        "billing": {
            "_billed_time": None,
            "_gb_seconds": 0,
            "_memory": None,
        },
        "provider_times": {"execution": 0, "initialization": 0},
    }


def _invoke_once_requests(url: str, payload: dict, protocol: str = "standard") -> dict:
    begin = datetime.now()
    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    end = datetime.now()

    client_us = int((end - begin).total_seconds() * 1e6)

    try:
        output = response.json()
    except ValueError:
        output = {"error": response.text[:200]}
    output = normalize_output(protocol, output)

    request_id = output.get("request_id", payload.get("request_id", uuid.uuid4().hex))

    return {
        "request_id": request_id,
        "times": {
            "client": client_us,
            "benchmark": benchmark_duration_us(output),
            "http_startup": 0,
            "http_first_byte_return": 0,
        },
        "output": output,
        "stats": {
            "cold_start": output.get("is_cold", False),
            "failure": response.status_code != 200,
        },
        "billing": {
            "_billed_time": None,
            "_gb_seconds": 0,
            "_memory": None,
        },
        "provider_times": {"execution": 0, "initialization": 0},
    }


def run_batch(url, reps, concurrency, state_size_kb, state_key, protocol):
    """Run batch invocations and collect results."""
    results = {}
    errors = 0
    begin_time = time.time()

    print(f"Running {reps} invocations at concurrency={concurrency}, "
          f"state_size_kb={state_size_kb}")

    completed = 0
    consecutive_errors = 0
    max_consecutive_errors = 50

    has_key_template = "{key}" in url

    while completed < reps:
        batch_size = min(concurrency, reps - completed)

        with ThreadPoolExecutor(max_workers=batch_size) as pool:
            futures = []
            for _ in range(batch_size):
                req_id = uuid.uuid4().hex
                invoke_url = url.replace("{key}", req_id) if has_key_template else url
                payload = build_payload(
                    protocol,
                    f"{state_key}:{req_id[:8]}",
                    state_size_kb,
                    1,
                    req_id,
                )
                futures.append(pool.submit(invoke_once, invoke_url, payload, protocol))

            batch_errors = 0
            for future in as_completed(futures):
                result = future.result()
                rid = result["request_id"]
                if result["stats"]["failure"]:
                    errors += 1
                    batch_errors += 1
                else:
                    results[rid] = result
                    completed += 1
                    consecutive_errors = 0

            if batch_errors == batch_size:
                consecutive_errors += batch_size
                if consecutive_errors >= max_consecutive_errors:
                    print(f"  ABORT: {consecutive_errors} consecutive errors. "
                          f"Service may be throttled.")
                    break
                # Back off before retrying
                time.sleep(min(consecutive_errors * 0.5, 10))

        if completed % 50 == 0 or completed == reps:
            print(f"  {completed}/{reps} completed, {errors} errors")

    end_time = time.time()
    duration = end_time - begin_time
    print(f"\nDone in {duration:.1f}s ({completed/duration:.1f} invocations/sec)")

    return results, begin_time, end_time


def main():
    parser = argparse.ArgumentParser(description="Batch invoke serverless function")
    parser.add_argument("url", help="Function HTTP endpoint URL")
    parser.add_argument("--reps", type=int, default=200, help="Number of invocations")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent invocations")
    parser.add_argument("--state-size-kb", type=int, default=64, help="State size in KB")
    parser.add_argument("--state-key", default="bench:state", help="State key prefix")
    parser.add_argument("--output", default="batch_results.json", help="Output JSON path")
    parser.add_argument("--function-name", default="function", help="Function name for results")
    parser.add_argument(
        "--protocol",
        choices=["standard", "gresse"],
        default="standard",
        help="Request/response protocol adapter",
    )
    args = parser.parse_args()

    results, begin_time, end_time = run_batch(
        args.url, args.reps, args.concurrency,
        args.state_size_kb, args.state_key, args.protocol,
    )

    # Write SeBS-compatible output
    output = {
        "_invocations": {args.function_name: results},
        "_metrics": {},
        "begin_time": begin_time,
        "end_time": end_time,
        "config": {
            "url": args.url,
            "reps": args.reps,
            "concurrency": args.concurrency,
            "state_size_kb": args.state_size_kb,
            "protocol": args.protocol,
        },
        "result_bucket": "",
        "statistics": {},
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
