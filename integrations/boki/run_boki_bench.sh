#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/results/raw}"
COMMON_DIR="${SCRIPT_DIR}/../common_schema"

NUM_REQUESTS="${1:-50}"
BOKI_HTTP_URL="${BOKI_HTTP_URL:-}"
HTTP_METHOD="${HTTP_METHOD:-GET}"
BODY_JSON="${BODY_JSON:-{}}"
BENCHMARK_NAME="${BENCHMARK_NAME:-gateway-smoke}"
CONSISTENCY_MODEL="${CONSISTENCY_MODEL:-normal}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-aws-ec2}"
SYSTEM_VARIANT="${SYSTEM_VARIANT:-boki-native}"
BOKI_EVENTS_JSONL="${BOKI_EVENTS_JSONL:-}"
BOKI_TELEMETRY_JSON="${BOKI_TELEMETRY_JSON:-}"
BOKI_EVENTS_JSONL_PATH="${BOKI_EVENTS_JSONL_PATH:-}"
BOKI_RUN_ID="${BOKI_RUN_ID:-}"

if [[ -z "${BOKI_HTTP_URL}" ]]; then
  echo "Set BOKI_HTTP_URL to your Boki gateway base URL (e.g. http://GATEWAY_PUBLIC_IP:8080/path)." >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}"
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="boki-${BENCHMARK_NAME}-n${NUM_REQUESTS}-${RUN_TS}"
if [[ -z "${RUN_ID}" ]]; then
  echo "ERROR: run_id is empty; aborting." >&2
  exit 1
fi
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"
RUN_EVENTS_PATH="${RUN_DIR}/events-${RUN_ID}.jsonl"
RUN_TELEMETRY_PATH="${RUN_DIR}/telemetry-${RUN_ID}.json"

# Canonical env mapping for emitter/collector contracts.
if [[ -z "${BOKI_EVENTS_JSONL_PATH}" && -n "${BOKI_EVENTS_JSONL}" ]]; then
  BOKI_EVENTS_JSONL_PATH="${BOKI_EVENTS_JSONL}"
fi
if [[ -z "${BOKI_EVENTS_JSONL}" && -n "${BOKI_EVENTS_JSONL_PATH}" ]]; then
  BOKI_EVENTS_JSONL="${BOKI_EVENTS_JSONL_PATH}"
fi
if [[ -z "${BOKI_RUN_ID}" ]]; then
  BOKI_RUN_ID="${RUN_ID}"
fi

cat > "${RUN_DIR}/metadata.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "system": "boki",
  "system_variant": "${SYSTEM_VARIANT}",
  "benchmark_name": "${BENCHMARK_NAME}",
  "num_requests": ${NUM_REQUESTS},
  "boki_http_url": "${BOKI_HTTP_URL}",
  "consistency_model": "${CONSISTENCY_MODEL}",
  "deployment_mode": "${DEPLOYMENT_MODE}",
  "started_at_utc": "${RUN_TS}"
}
EOF

echo "Boki HTTP bench: ${NUM_REQUESTS} requests to ${BOKI_HTTP_URL}"
echo "Run dir: ${RUN_DIR}"

python3 "${COMMON_DIR}/http_latency_bench.py" \
  --run-dir "${RUN_DIR}" \
  --url "${BOKI_HTTP_URL}" \
  --count "${NUM_REQUESTS}" \
  --method "${HTTP_METHOD}" \
  --body-json "${BODY_JSON}"

# Optional: ingest runtime-emitted sidecars from Boki deployment.
if [[ -n "${BOKI_EVENTS_JSONL}" && -f "${BOKI_EVENTS_JSONL}" ]]; then
  cp -f "${BOKI_EVENTS_JSONL}" "${RUN_EVENTS_PATH}"
  cp -f "${RUN_EVENTS_PATH}" "${RUN_DIR}/events.jsonl"
  echo "Copied Boki events sidecar: ${BOKI_EVENTS_JSONL}"
fi
if [[ -n "${BOKI_TELEMETRY_JSON}" && -f "${BOKI_TELEMETRY_JSON}" ]]; then
  cp -f "${BOKI_TELEMETRY_JSON}" "${RUN_TELEMETRY_PATH}"
  cp -f "${RUN_TELEMETRY_PATH}" "${RUN_DIR}/telemetry.json"
  echo "Copied Boki telemetry sidecar: ${BOKI_TELEMETRY_JSON}"
fi

# Optional strict sidecar smoke check.
if [[ -f "${RUN_DIR}/events.jsonl" ]]; then
  python3 - <<PY
import json
from pathlib import Path
path = Path(${RUN_DIR@Q}) / "events.jsonl"
run_id = ${RUN_ID@Q}
expected = {"invoke_end", "state_read", "state_write"}
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

python3 "${SCRIPT_DIR}/collect_boki_results.py" \
  --run-dir "${RUN_DIR}" \
  --out "${RUN_DIR}/collected_metrics.json"

echo "Completed Boki run: ${RUN_ID}"
echo "Collected metrics: ${RUN_DIR}/collected_metrics.json"
