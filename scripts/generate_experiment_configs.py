#!/usr/bin/env python3
"""
Generate SeBS experiment config files for the full experiment matrix.

Creates configs for Boki (SeBS provider) and batch invoke configs for Lambda/Cloudburst.
"""

import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "experiments")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# System endpoints
BOKI_GATEWAY = "http://16.170.141.184:8080"
LAMBDA_API = "https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/"
CLOUDBURST_SCHEDULER = "10.30.1.117"

# Input-size mapping: SeBS input-size -> state_size_kb
# test=1KB, small=64KB, large=512KB
SIZE_MAP = {"test": 1, "small": 64, "large": 512}


def boki_config(experiment_name, input_size, repetitions, concurrency):
    return {
        "experiments": {
            "deployment": "boki",
            "update_code": False,
            "update_storage": False,
            "download_results": False,
            "architecture": "x64",
            "container_deployment": False,
            "runtime": {"language": "python", "version": "3.9"},
            "perf-cost": {
                "benchmark": "boki-shared-log",
                "experiments": ["warm"],
                "input-size": input_size,
                "repetitions": repetitions,
                "concurrent-invocations": concurrency,
                "memory-sizes": [],
            },
        },
        "deployment": {
            "name": "boki",
            "boki": {
                "gateway_url": BOKI_GATEWAY,
                "function_name": "statefulBench",
            },
        },
    }


def write_config(name, config):
    path = os.path.join(OUTPUT_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  {path}")


# ── Experiment Matrix ──

print("Generating experiment configs...")

# 1. Steady-state throughput: concurrency=[1, 10, 50, 100], size=64KB, reps=200
for c in [1, 10, 50, 100]:
    write_config(f"boki-throughput-c{c}", boki_config("throughput", "small", 200, c))

# 2. Latency distribution: concurrency=50, size=64KB, reps=1000
write_config("boki-latency-dist", boki_config("latency", "small", 1000, 50))

# 3. State size impact: concurrency=50, sizes=[1, 64, 512]KB, reps=200
for size_name, size_kb in SIZE_MAP.items():
    write_config(f"boki-statesize-{size_kb}kb", boki_config("statesize", size_name, 200, 50))

print(f"\nGenerated {len(os.listdir(OUTPUT_DIR))} config files in {OUTPUT_DIR}")
print("\nRun with:")
print("  SEBS_WITH_BOKI=true uv run python3 sebs.py experiment invoke perf-cost \\")
print("    --config config/experiments/boki-throughput-c1.json \\")
print("    --output-dir results/boki-throughput-c1")
