#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GRESSE_ROOT="${GRESSE_ROOT:-${MASTER_SEBS_ROOT}/../Gresse}"
STATE_DIR="${SCRIPT_DIR}/.state"
LOG_DIR="${SCRIPT_DIR}/results/runtime"
PID_FILE="${STATE_DIR}/gresse.pid"
LOG_FILE="${LOG_DIR}/gresse.log"

GRESSE_ADDR="${GRESSE_ADDR:-127.0.0.1}"
GRESSE_HTTP_PORT="${GRESSE_HTTP_PORT:-9090}"
GRESSE_INTERNAL_PORT="${GRESSE_INTERNAL_PORT:-8080}"
GRESSE_RESULT_DIR_PATH="${GRESSE_RESULT_DIR_PATH:-${LOG_DIR}}"
GRESSE_OBJECT_STORAGE_URL="${GRESSE_OBJECT_STORAGE_URL:-http://127.0.0.1:9000}"
GRESSE_OBJECT_STORAGE_REGION="${GRESSE_OBJECT_STORAGE_REGION:-us-east-1}"
GRESSE_OBJECT_STORAGE_BUCKET="${GRESSE_OBJECT_STORAGE_BUCKET:-gresse-integration}"
GRESSE_OBJECT_STORAGE_ACCESS_KEY="${GRESSE_OBJECT_STORAGE_ACCESS_KEY:-minioadmin}"
GRESSE_OBJECT_STORAGE_SECRET_KEY="${GRESSE_OBJECT_STORAGE_SECRET_KEY:-minioadmin}"
GRESSE_PERSISTENT_REPLICA_PATH="${GRESSE_PERSISTENT_REPLICA_PATH:-replicas/bench-function.json}"
GRESSE_MEMBERSHIP_DIRECTORY_PATH="${GRESSE_MEMBERSHIP_DIRECTORY_PATH:-membership/bench-function}"
GRESSE_SYNC_INTERVAL_MS="${GRESSE_SYNC_INTERVAL_MS:-1000}"
GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS="${GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS:-1000}"
GRESSE_LOG="${GRESSE_LOG:-info}"

usage() {
  echo "Usage: $0 {build|start|stop|status|logs}" >&2
}

ensure_root() {
  if [[ ! -d "${GRESSE_ROOT}" ]]; then
    echo "Gresse root not found: ${GRESSE_ROOT}" >&2
    exit 1
  fi
}

is_running() {
  if [[ ! -f "${PID_FILE}" ]]; then
    return 1
  fi
  local pid
  pid="$(<"${PID_FILE}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

start_minio() {
  docker compose -f "${GRESSE_ROOT}/docker-compose.minio.yml" up -d
}

stop_minio() {
  docker compose -f "${GRESSE_ROOT}/docker-compose.minio.yml" stop
}

build_replica() {
  (cd "${GRESSE_ROOT}" && cargo build --example bench_function)
}

start_replica() {
  mkdir -p "${STATE_DIR}" "${LOG_DIR}" "${GRESSE_RESULT_DIR_PATH}"
  if is_running; then
    echo "Gresse replica already running (pid $(<"${PID_FILE}"))"
    return 0
  fi

  (
    cd "${GRESSE_ROOT}"
    env \
      GRESSE_ADDR="${GRESSE_ADDR}" \
      GRESSE_HTTP_PORT="${GRESSE_HTTP_PORT}" \
      GRESSE_INTERNAL_PORT="${GRESSE_INTERNAL_PORT}" \
      GRESSE_RESULT_DIR_PATH="${GRESSE_RESULT_DIR_PATH}" \
      GRESSE_OBJECT_STORAGE_URL="${GRESSE_OBJECT_STORAGE_URL}" \
      GRESSE_OBJECT_STORAGE_REGION="${GRESSE_OBJECT_STORAGE_REGION}" \
      GRESSE_OBJECT_STORAGE_BUCKET="${GRESSE_OBJECT_STORAGE_BUCKET}" \
      GRESSE_OBJECT_STORAGE_ACCESS_KEY="${GRESSE_OBJECT_STORAGE_ACCESS_KEY}" \
      GRESSE_OBJECT_STORAGE_SECRET_KEY="${GRESSE_OBJECT_STORAGE_SECRET_KEY}" \
      GRESSE_PERSISTENT_REPLICA_PATH="${GRESSE_PERSISTENT_REPLICA_PATH}" \
      GRESSE_MEMBERSHIP_DIRECTORY_PATH="${GRESSE_MEMBERSHIP_DIRECTORY_PATH}" \
      GRESSE_SYNC_INTERVAL_MS="${GRESSE_SYNC_INTERVAL_MS}" \
      GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS="${GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS}" \
      GRESSE_LOG="${GRESSE_LOG}" \
      cargo run --example bench_function
  ) >"${LOG_FILE}" 2>&1 &

  echo "$!" > "${PID_FILE}"
  echo "Started Gresse replica pid $(<"${PID_FILE}")"
  echo "HTTP endpoint: http://${GRESSE_ADDR}:${GRESSE_HTTP_PORT}/"
  echo "Log: ${LOG_FILE}"
}

stop_replica() {
  if ! is_running; then
    rm -f "${PID_FILE}"
    echo "Gresse replica is not running"
    return 0
  fi
  local pid
  pid="$(<"${PID_FILE}")"
  kill "${pid}"
  rm -f "${PID_FILE}"
  echo "Stopped Gresse replica pid ${pid}"
}

status_replica() {
  if is_running; then
    echo "Gresse replica running (pid $(<"${PID_FILE}"))"
    echo "HTTP endpoint: http://${GRESSE_ADDR}:${GRESSE_HTTP_PORT}/"
  else
    echo "Gresse replica not running"
  fi
}

show_logs() {
  if [[ -f "${LOG_FILE}" ]]; then
    tail -n 50 "${LOG_FILE}"
  else
    echo "No log file yet: ${LOG_FILE}"
  fi
}

main() {
  ensure_root

  case "${1:-}" in
    build)
      build_replica
      ;;
    start)
      start_minio
      build_replica
      start_replica
      ;;
    stop)
      stop_replica
      stop_minio
      ;;
    status)
      status_replica
      ;;
    logs)
      show_logs
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
