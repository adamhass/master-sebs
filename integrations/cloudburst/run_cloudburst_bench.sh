#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CB_ROOT="${CB_ROOT:-${MASTER_SEBS_ROOT}/../base_systems/cloudburst}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/results/raw}"

BENCHMARK_NAME="${1:-composition}"
NUM_REQUESTS="${2:-100}"
FUNCTION_ELB="${FUNCTION_ELB:-127.0.0.1}"
SCHEDULER_IP="${SCHEDULER_IP:-127.0.0.1}"
CONSISTENCY_MODEL="${CONSISTENCY_MODEL:-normal}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-cloudburst-local}"
CB_EVENTS_JSONL="${CB_EVENTS_JSONL:-}"
CB_TELEMETRY_JSON="${CB_TELEMETRY_JSON:-}"
CB_EXTRA_METRICS_JSON="${CB_EXTRA_METRICS_JSON:-}"
CB_EVENTS_JSONL_PATH="${CB_EVENTS_JSONL_PATH:-}"
CB_RUN_ID="${CB_RUN_ID:-}"

if [[ ! -d "${CB_ROOT}" ]]; then
  echo "Cloudburst root not found: ${CB_ROOT}" >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}"

RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="cloudburst-${BENCHMARK_NAME}-n${NUM_REQUESTS}-${RUN_TS}"
if [[ -z "${RUN_ID}" ]]; then
  echo "ERROR: run_id is empty; aborting." >&2
  exit 1
fi
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"
RUN_EVENTS_PATH="${RUN_DIR}/events-${RUN_ID}.jsonl"
RUN_TELEMETRY_PATH="${RUN_DIR}/telemetry-${RUN_ID}.json"
RUN_EXTRA_METRICS_PATH="${RUN_DIR}/extra-metrics-${RUN_ID}.json"

# Canonical env mapping for emitter/collector contracts.
if [[ -z "${CB_EVENTS_JSONL_PATH}" && -n "${CB_EVENTS_JSONL}" ]]; then
  CB_EVENTS_JSONL_PATH="${CB_EVENTS_JSONL}"
fi
if [[ -z "${CB_EVENTS_JSONL}" && -n "${CB_EVENTS_JSONL_PATH}" ]]; then
  CB_EVENTS_JSONL="${CB_EVENTS_JSONL_PATH}"
fi
if [[ -z "${CB_RUN_ID}" ]]; then
  CB_RUN_ID="${RUN_ID}"
fi

cat > "${RUN_DIR}/metadata.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "system": "cloudburst",
  "benchmark_name": "${BENCHMARK_NAME}",
  "num_requests": ${NUM_REQUESTS},
  "function_elb": "${FUNCTION_ELB}",
  "scheduler_ip": "${SCHEDULER_IP}",
  "consistency_model": "${CONSISTENCY_MODEL}",
  "deployment_mode": "${DEPLOYMENT_MODE}",
  "cloudburst_root": "${CB_ROOT}",
  "started_at_utc": "${RUN_TS}"
}
EOF

echo "Running Cloudburst benchmark '${BENCHMARK_NAME}' (${NUM_REQUESTS} requests)"
echo "Run dir: ${RUN_DIR}"

(
  cd "${CB_ROOT}"
  export PYTHONPATH="${CB_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
  python3 cloudburst/client/run_benchmark.py \
    "${BENCHMARK_NAME}" \
    "${FUNCTION_ELB}" \
    "${NUM_REQUESTS}" \
    "${SCHEDULER_IP}"
) 2>&1 | tee "${RUN_DIR}/client_stdout.log"

for f in log_benchmark.txt log_trigger.txt; do
  if [[ -f "${CB_ROOT}/${f}" ]]; then
    cp -f "${CB_ROOT}/${f}" "${RUN_DIR}/${f}"
  fi
done

# Optional: ingest runtime-emitted sidecars from Cloudburst/Anna deployment.
if [[ -n "${CB_EVENTS_JSONL}" && -f "${CB_EVENTS_JSONL}" ]]; then
  cp -f "${CB_EVENTS_JSONL}" "${RUN_EVENTS_PATH}"
  cp -f "${RUN_EVENTS_PATH}" "${RUN_DIR}/events.jsonl"
  echo "Copied Cloudburst events sidecar: ${CB_EVENTS_JSONL}"
fi
if [[ -n "${CB_TELEMETRY_JSON}" && -f "${CB_TELEMETRY_JSON}" ]]; then
  cp -f "${CB_TELEMETRY_JSON}" "${RUN_TELEMETRY_PATH}"
  cp -f "${RUN_TELEMETRY_PATH}" "${RUN_DIR}/telemetry.json"
  echo "Copied Cloudburst telemetry sidecar: ${CB_TELEMETRY_JSON}"
fi
if [[ -n "${CB_EXTRA_METRICS_JSON}" && -f "${CB_EXTRA_METRICS_JSON}" ]]; then
  cp -f "${CB_EXTRA_METRICS_JSON}" "${RUN_EXTRA_METRICS_PATH}"
  cp -f "${RUN_EXTRA_METRICS_PATH}" "${RUN_DIR}/extra_metrics.json"
  echo "Copied Cloudburst extra metrics sidecar: ${CB_EXTRA_METRICS_JSON}"
fi

# Optional strict sidecar smoke check.
if [[ -f "${RUN_DIR}/events.jsonl" ]]; then
  python3 - <<PY
import json
from pathlib import Path
path = Path(${RUN_DIR@Q}) / "events.jsonl"
run_id = ${RUN_ID@Q}
expected = {"invoke_end", "crdt_divergence_detected", "crdt_converged"}
seen = set()
bad = 0
for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        bad += 1
        continue
    rid = str(obj.get("run_id", ""))
    if rid and rid != run_id:
        bad += 1
    et = obj.get("event_type")
    if et:
        seen.add(str(et))
if bad:
    raise SystemExit(f"Invalid event sidecar lines or run_id mismatches in {path}")
if not (seen & expected):
    raise SystemExit(f"Missing expected core event types in {path}; seen={sorted(seen)}")
PY
fi

python3 "${SCRIPT_DIR}/collect_cloudburst_results.py" \
  --run-dir "${RUN_DIR}" \
  --out "${RUN_DIR}/collected_metrics.json"

echo "Completed Cloudburst run: ${RUN_ID}"
echo "Collected metrics: ${RUN_DIR}/collected_metrics.json"
