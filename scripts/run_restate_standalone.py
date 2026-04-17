#!/usr/bin/env python3
"""Run all Restate standalone benchmarks and write results."""
import subprocess
import sys
import os

SEBS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SEBS_DIR, "scripts", "batch_invoke.py")
PYTHON = sys.executable
URL = "http://13.60.219.99:8080/statefulBench/{key}/run"
OUT = os.path.join(SEBS_DIR, "results", "run6", "restate")

experiments = [
    ("throughput-c1", 200, 1, 64),
    ("throughput-c10", 200, 10, 64),
    ("throughput-c50", 200, 50, 64),
    ("throughput-c100", 200, 100, 64),
    ("latency-dist", 1000, 10, 64),
    ("statesize-1kb", 200, 10, 1),
    ("statesize-64kb", 200, 10, 64),
    ("statesize-512kb", 200, 10, 512),
]

log = open("/tmp/restate-bench-log.txt", "w")

for name, reps, conc, size in experiments:
    outfile = os.path.join(OUT, f"{name}.json")
    cmd = [PYTHON, SCRIPT, URL, "--reps", str(reps), "--concurrency", str(conc),
           "--state-size-kb", str(size), "--output", outfile, "--function-name", "statefulBench"]
    log.write(f"=== {name} ===\n")
    log.flush()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.write(result.stdout)
    log.write(result.stderr)
    log.write(f"\nExit: {result.returncode}\n\n")
    log.flush()

log.write("=== ALL DONE ===\n")
log.close()
print("Done. Log: /tmp/restate-bench-log.txt")
