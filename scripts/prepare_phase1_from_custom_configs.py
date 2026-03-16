#!/usr/bin/env python3

import argparse
import json
import os
import pprint
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class RuntimeSpec:
    language: str
    version: str


def parse_runtime(runtime: str) -> RuntimeSpec:
    value = (runtime or "").strip().lower()
    if value.startswith("python"):
        version = value[len("python") :] or "3.10"
        return RuntimeSpec(language="python", version=version)
    if value.startswith("nodejs"):
        version = value[len("nodejs") :] or "16"
        return RuntimeSpec(language="nodejs", version=version)
    return RuntimeSpec(language="python", version="3.10")


def parse_payload_size_bytes(value) -> int:
    if isinstance(value, int):
        return max(value, 0)

    text = str(value or "").strip().lower()
    match = re.fullmatch(r"(\d+)\s*(b|kb|mb)?", text)
    if not match:
        return 1024

    base = int(match.group(1))
    unit = match.group(2) or "b"
    if unit == "mb":
        return base * 1024 * 1024
    if unit == "kb":
        return base * 1024
    return base


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2)
        handle.write("\n")


def write_text(path: Path, text: str, executable: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    if executable:
        current_mode = path.stat().st_mode
        path.chmod(current_mode | 0o111)


def build_benchmark_skeleton(
    benchmark_root: Path,
    benchmark_name: str,
    description: str,
    timeout: int,
    memory: int,
    parameters: Dict,
    experiment: Dict,
):
    bench_dir = benchmark_root / benchmark_name
    code_dir = bench_dir / "python"
    code_dir.mkdir(parents=True, exist_ok=True)

    benchmark_config = {
        "timeout": int(timeout),
        "memory": int(memory),
        "languages": ["python"],
        "modules": [],
    }
    write_json(bench_dir / "config.json", benchmark_config)

    payload_size_bytes = parse_payload_size_bytes(experiment.get("payload_size", "1kb"))
    input_py = f"""\
BENCHMARK_NAME = {benchmark_name!r}
BENCHMARK_DESCRIPTION = {description!r}
PARAMETERS = {pprint.pformat(parameters, width=100)}
EXPERIMENT = {pprint.pformat(experiment, width=100)}
PAYLOAD_SIZE_BYTES = {payload_size_bytes}


def generate_input(data_dir, size, benchmarks_bucket, input_buckets, output_buckets, upload_func, nosql_func):
    scale = {{"test": 1, "small": 4, "large": 16}}.get(size, 1)
    payload_len = min(PAYLOAD_SIZE_BYTES * scale, 64 * 1024)
    payload = "x" * payload_len

    return {{
        "system": BENCHMARK_NAME,
        "description": BENCHMARK_DESCRIPTION,
        "parameters": PARAMETERS,
        "workload": EXPERIMENT.get("workload", "default"),
        "state_size_kb": PARAMETERS.get("state_size_kb", 0),
        "ops": max(1, scale),
        "payload": payload,
    }}
"""

    function_py = """\
import hashlib
import time


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return str(value).encode("utf-8")


def handler(event):
    begin = time.perf_counter_ns()

    payload = event.get("payload", "")
    payload_hash = hashlib.sha256(_to_bytes(payload)).hexdigest()
    ops = max(1, int(event.get("ops", 1)))
    state_size_kb = max(0, int(event.get("state_size_kb", 0)))

    # Lightweight synthetic workload placeholder for custom stateful systems.
    acc = 0
    for idx in range(min(ops * 64, 20000)):
        acc = (acc + idx + state_size_kb + len(payload_hash)) % 1000003

    duration_us = int((time.perf_counter_ns() - begin) / 1000)

    return {
        "result": {
            "ok": True,
            "system": event.get("system", "unknown"),
            "workload": event.get("workload", "default"),
            "payload_sha256": payload_hash,
            "accumulator": acc,
        },
        "measurement": {
            "compute_time": duration_us,
            "workload_ops": ops,
            "state_size_kb": state_size_kb,
        },
    }
"""

    write_text(bench_dir / "input.py", input_py)
    write_text(code_dir / "function.py", function_py)


def make_perf_cost_config(
    benchmark_name: str,
    runtime: RuntimeSpec,
    region: str,
    lambda_role: str,
    memory: int,
    repetitions: int,
    concurrency: int,
    source_file: str,
    source_payload: dict,
) -> dict:
    return {
        "experiments": {
            "deployment": "aws",
            "update_code": False,
            "update_storage": False,
            "download_results": False,
            "architecture": "x64",
            "container_deployment": False,
            "runtime": {"language": runtime.language, "version": runtime.version},
            "type": "perf-cost",
            "perf-cost": {
                "benchmark": benchmark_name,
                "experiments": ["cold", "warm"],
                "input-size": "test",
                "repetitions": int(repetitions),
                "concurrent-invocations": int(concurrency),
                "memory-sizes": [int(memory)],
            },
        },
        "deployment": {
            "name": "aws",
            "aws": {
                "region": region,
                "lambda-role": lambda_role,
            },
        },
        "phase1-source": {
            "source_file": source_file,
            "benchmark": source_payload.get("benchmark", {}),
            "config": source_payload.get("config", {}),
        },
    }


def build_notes_file(path: Path):
    text = """\
# Phase1 Mapping Notes

The files in `sebs-configs/*.json` are not native SeBS config files.
This preparation step maps them to SeBS `perf-cost` experiment configs and benchmark skeletons.

## Mappings Applied

- `benchmark.name` -> SeBS benchmark directory name under `benchmarks/900.stateful/<name>`.
- `benchmark.runtime` -> SeBS `experiments.runtime`.
- `config.deployment.aws.region` -> SeBS `deployment.aws.region`.
- `config.deployment.aws.iam_role` -> SeBS `deployment.aws.lambda-role`.
- `config.deployment.aws.memory` -> SeBS `perf-cost.memory-sizes[0]` and benchmark default memory.
- `config.deployment.aws.timeout` -> benchmark default timeout.
- `config.experiment.iterations` -> SeBS `perf-cost.repetitions`.
- `config.experiment.concurrency[]` -> one SeBS config file per concurrency value.

## Not Natively Mapped by SeBS Core (Current State)

- `config.deployment.aws.vpc_config` is not applied by current SeBS AWS deployer.
- `warmup_invocations` and `burn_in_period_s` are not direct SeBS `perf-cost` options.
- System-specific `parameters` are embedded into generated benchmark inputs and passed as invocation payload.
"""
    write_text(path, text)


def collect_source_configs(source_dir: Path) -> List[Path]:
    return sorted([path for path in source_dir.glob("*.json") if path.is_file()])


def main():
    parser = argparse.ArgumentParser(
        description="Generate SeBS Phase1 benchmark skeletons and perf-cost configs from custom JSON files."
    )
    parser.add_argument(
        "--source-dir",
        default="sebs-configs",
        help="Directory with custom JSON files (default: sebs-configs).",
    )
    parser.add_argument(
        "--benchmarks-root",
        default="benchmarks/900.stateful",
        help="Output benchmark root directory.",
    )
    parser.add_argument(
        "--configs-root",
        default="config/phase1",
        help="Output SeBS experiment config directory.",
    )
    parser.add_argument(
        "--run-script",
        default="scripts/run_phase1_manual.sh",
        help="Generated manual execution script path.",
    )
    parser.add_argument(
        "--notes-file",
        default="sebs-configs/PHASE1_MAPPING_NOTES.md",
        help="Generated notes file path.",
    )
    args = parser.parse_args()

    repo_root = Path(os.getcwd())
    source_dir = repo_root / args.source_dir
    benchmarks_root = repo_root / args.benchmarks_root
    configs_root = repo_root / args.configs_root
    run_script_path = repo_root / args.run_script
    notes_path = repo_root / args.notes_file

    configs = collect_source_configs(source_dir)
    if not configs:
        raise RuntimeError(f"No JSON files found in {source_dir}")

    run_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Run from repository root: master-sebs/",
        "",
    ]

    for cfg_path in configs:
        with open(cfg_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        benchmark_info = payload.get("benchmark", {})
        cfg = payload.get("config", {})
        deploy = cfg.get("deployment", {}).get("aws", {})
        experiment = cfg.get("experiment", {})
        parameters = cfg.get("parameters", {})

        benchmark_name = benchmark_info.get("name", cfg_path.stem)
        description = benchmark_info.get("description", "")

        runtime = parse_runtime(benchmark_info.get("runtime", "python3.10"))
        memory = int(deploy.get("memory", 1024))
        timeout = int(deploy.get("timeout", 30))
        iterations = int(experiment.get("iterations", 10))
        region = deploy.get("region", "us-east-1")
        lambda_role = deploy.get("iam_role", "")

        concurrencies = experiment.get("concurrency", [1])
        if not isinstance(concurrencies, list):
            concurrencies = [concurrencies]
        concurrencies = [int(val) for val in concurrencies]

        build_benchmark_skeleton(
            benchmark_root=benchmarks_root,
            benchmark_name=benchmark_name,
            description=description,
            timeout=timeout,
            memory=memory,
            parameters=parameters,
            experiment=experiment,
        )

        for concurrency in concurrencies:
            output_cfg = make_perf_cost_config(
                benchmark_name=benchmark_name,
                runtime=runtime,
                region=region,
                lambda_role=lambda_role,
                memory=memory,
                repetitions=iterations,
                concurrency=concurrency,
                source_file=str(cfg_path.relative_to(repo_root)),
                source_payload=payload,
            )

            cfg_output_path = (
                configs_root / benchmark_name / f"perf-cost-c{concurrency}.json"
            )
            write_json(cfg_output_path, output_cfg)

            rel_cfg_path = cfg_output_path.relative_to(repo_root)
            out_dir = Path("phase1-results") / benchmark_name / f"c{concurrency}"
            run_lines.append(
                f"./sebs.py experiment invoke perf-cost --config {rel_cfg_path} --deployment aws --output-dir {out_dir}"
            )
            run_lines.append(
                f"./sebs.py experiment process perf-cost --config {rel_cfg_path} --deployment aws --output-dir {out_dir}"
            )
            run_lines.append("")

    write_text(run_script_path, "\n".join(run_lines).rstrip() + "\n", executable=True)
    build_notes_file(notes_path)

    print(f"Prepared {len(configs)} source configs from {source_dir}")
    print(f"Benchmarks: {benchmarks_root}")
    print(f"Experiment configs: {configs_root}")
    print(f"Manual run script: {run_script_path}")
    print(f"Notes: {notes_path}")


if __name__ == "__main__":
    main()
