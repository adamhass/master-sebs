#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/results/raw}"
COMMON_DIR="${SCRIPT_DIR}/../common_schema"

NUM_REQUESTS="${1:-50}"
GRESSE_HTTP_URL="${GRESSE_HTTP_URL:-http://127.0.0.1:9090/}"
HTTP_METHOD="${HTTP_METHOD:-POST}"
BODY_JSON="${BODY_JSON:-{\"type\":\"Mutation\",\"params\":{\"Run\":{\"state_size_kb\":64,\"state_key\":\"bench:state\",\"ops\":1}}}}"
BENCHMARK_NAME="${BENCHMARK_NAME:-bench-function}"
CONSISTENCY_MODEL="${CONSISTENCY_MODEL:-eventual}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-gresse-local}"
SYSTEM_VARIANT="${SYSTEM_VARIANT:-gresse-native}"
STATE_SIZE_KB="${STATE_SIZE_KB:-64}"
KEY_ID="${KEY_ID:-bench:state}"
KEYS_COUNT="${KEYS_COUNT:-1}"

mkdir -p "${OUT_ROOT}"
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="gresse-${BENCHMARK_NAME}-n${NUM_REQUESTS}-${RUN_TS}"
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

cat > "${RUN_DIR}/metadata.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "system": "gresse",
  "system_variant": "${SYSTEM_VARIANT}",
  "benchmark_name": "${BENCHMARK_NAME}",
  "num_requests": ${NUM_REQUESTS},
  "gresse_http_url": "${GRESSE_HTTP_URL}",
  "consistency_model": "${CONSISTENCY_MODEL}",
  "deployment_mode": "${DEPLOYMENT_MODE}",
  "state_size_kb": ${STATE_SIZE_KB},
  "key_id": "${KEY_ID}",
  "keys_count": ${KEYS_COUNT},
  "started_at_utc": "${RUN_TS}"
}
EOF

echo "Gresse HTTP bench: ${NUM_REQUESTS} requests to ${GRESSE_HTTP_URL}"
echo "Run dir: ${RUN_DIR}"

python3 "${COMMON_DIR}/http_latency_bench.py" \
  --run-dir "${RUN_DIR}" \
  --url "${GRESSE_HTTP_URL}" \
  --count "${NUM_REQUESTS}" \
  --method "${HTTP_METHOD}" \
  --body-json "${BODY_JSON}"

python3 "${SCRIPT_DIR}/collect_gresse_results.py" \
  --run-dir "${RUN_DIR}" \
  --out "${RUN_DIR}/collected_metrics.json"

echo "Completed Gresse run: ${RUN_ID}"
echo "Collected metrics: ${RUN_DIR}/collected_metrics.json"
