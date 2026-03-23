#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BOKI_ROOT="${BOKI_ROOT:-${MASTER_SEBS_ROOT}/../base_systems/boki}"
PID_FILE="${PID_FILE:-${SCRIPT_DIR}/.boki-pids}"
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/logs}"

ZK_HOST="${ZK_HOST:-127.0.0.1:2181}"
ZK_ROOT="${ZK_ROOT:-/faas}"
LISTEN_ADDR="${LISTEN_ADDR:-0.0.0.0}"
GATEWAY_HTTP_PORT="${GATEWAY_HTTP_PORT:-8080}"
GATEWAY_GRPC_PORT="${GATEWAY_GRPC_PORT:-50051}"

SEQUENCER_IDS="${SEQUENCER_IDS:-101}"
STORAGE_IDS="${STORAGE_IDS:-201}"
ENGINE_IDS="${ENGINE_IDS:-301}"
NUM_PHYLOGS="${NUM_PHYLOGS:-1}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <build|start|stop|restart|status>

Env:
  BOKI_ROOT=<path>           Override Boki source root (default: ../base_systems/boki).
  PID_FILE=<path>            PID file for launched processes.
  LOG_DIR=<path>             Directory for role logs.

  ZK_HOST=<host:port>        ZooKeeper endpoint (default: 127.0.0.1:2181).
  ZK_ROOT=<path>             ZooKeeper root znode path (default: /faas).
  LISTEN_ADDR=<addr>         Listen address for TCP services (default: 0.0.0.0).
  GATEWAY_HTTP_PORT=<port>   Gateway HTTP port (default: 8080).
  GATEWAY_GRPC_PORT=<port>   Gateway gRPC port (default: 50051).

  SEQUENCER_IDS=<csv>        Sequencer node IDs (default: 101).
  STORAGE_IDS=<csv>          Storage node IDs (default: 201).
  ENGINE_IDS=<csv>           Engine node IDs (default: 301).
  NUM_PHYLOGS=<n>            Number of physical logs (default: 1).

  FUNC_CONFIG_FILE=<path>    Optional function config passed to engine/gateway.
  ENGINE_TCP_PORT=<port>     Optional engine TCP IPC port (default: -1).
USAGE
}

assert_boki_root() {
  if [[ ! -d "${BOKI_ROOT}" ]]; then
    echo "Boki root not found: ${BOKI_ROOT}" >&2
    exit 1
  fi
}

require_binary() {
  local name="$1"
  local path="${BOKI_ROOT}/bin/release/${name}"
  if [[ ! -x "${path}" ]]; then
    echo "Missing binary: ${path}" >&2
    echo "Run: $(basename "$0") build" >&2
    exit 1
  fi
}

split_csv_to_array() {
  local csv="$1"
  local -n out_ref="$2"
  IFS=',' read -r -a out_ref <<<"${csv}"
}

start_process() {
  local name="$1"
  shift
  mkdir -p "${LOG_DIR}"
  local log_file="${LOG_DIR}/${name}.log"
  nohup "$@" >"${log_file}" 2>&1 &
  local pid=$!
  echo "${pid}|${name}|$*" >>"${PID_FILE}"
  echo "Started ${name} (pid=${pid})"
}

build_boki() {
  echo "Building Boki in ${BOKI_ROOT}"
  (
    cd "${BOKI_ROOT}"
    ./build_deps.sh
    make -j "$(nproc)"
  )
}

start_boki() {
  stop_boki || true
  : >"${PID_FILE}"

  local func_config_file="${FUNC_CONFIG_FILE:-}"
  local engine_tcp_port="${ENGINE_TCP_PORT:--1}"

  split_csv_to_array "${SEQUENCER_IDS}" seq_ids
  split_csv_to_array "${STORAGE_IDS}" st_ids
  split_csv_to_array "${ENGINE_IDS}" eng_ids

  local seq_count="${#seq_ids[@]}"
  local st_count="${#st_ids[@]}"
  local eng_count="${#eng_ids[@]}"

  local controller_bin="${BOKI_ROOT}/bin/release/controller"
  local sequencer_bin="${BOKI_ROOT}/bin/release/sequencer"
  local storage_bin="${BOKI_ROOT}/bin/release/storage"
  local engine_bin="${BOKI_ROOT}/bin/release/engine"
  local gateway_bin="${BOKI_ROOT}/bin/release/gateway"

  for bin in controller sequencer storage engine gateway; do
    require_binary "${bin}"
  done

  start_process controller "${controller_bin}" \
    --zookeeper_host="${ZK_HOST}" \
    --zookeeper_root_path="${ZK_ROOT}" \
    --metalog_replicas="${seq_count}" \
    --userlog_replicas="${st_count}" \
    --index_replicas="${eng_count}" \
    --num_phylogs="${NUM_PHYLOGS}"

  for id in "${seq_ids[@]}"; do
    start_process "sequencer-${id}" "${sequencer_bin}" \
      --node_id="${id}" \
      --zookeeper_host="${ZK_HOST}" \
      --zookeeper_root_path="${ZK_ROOT}" \
      --listen_addr="${LISTEN_ADDR}"
  done

  for id in "${st_ids[@]}"; do
    mkdir -p "${BOKI_ROOT}/data/storage-${id}"
    start_process "storage-${id}" "${storage_bin}" \
      --node_id="${id}" \
      --db_path="${BOKI_ROOT}/data/storage-${id}" \
      --zookeeper_host="${ZK_HOST}" \
      --zookeeper_root_path="${ZK_ROOT}" \
      --listen_addr="${LISTEN_ADDR}"
  done

  for id in "${eng_ids[@]}"; do
    local engine_args=(
      "${engine_bin}"
      "--node_id=${id}"
      "--enable_shared_log=true"
      "--engine_tcp_port=${engine_tcp_port}"
      "--zookeeper_host=${ZK_HOST}"
      "--zookeeper_root_path=${ZK_ROOT}"
      "--listen_addr=${LISTEN_ADDR}"
    )
    if [[ -n "${func_config_file}" ]]; then
      engine_args+=("--func_config_file=${func_config_file}")
    fi
    start_process "engine-${id}" "${engine_args[@]}"
  done

  local gateway_args=(
    "${gateway_bin}"
    "--http_port=${GATEWAY_HTTP_PORT}"
    "--grpc_port=${GATEWAY_GRPC_PORT}"
    "--zookeeper_host=${ZK_HOST}"
    "--zookeeper_root_path=${ZK_ROOT}"
    "--listen_addr=${LISTEN_ADDR}"
  )
  if [[ -n "${func_config_file}" ]]; then
    gateway_args+=("--func_config_file=${func_config_file}")
  fi
  start_process gateway "${gateway_args[@]}"

  echo "Boki cluster start sequence completed"
  echo "PID file: ${PID_FILE}"
  echo "Logs: ${LOG_DIR}"
}

stop_boki() {
  if [[ ! -f "${PID_FILE}" ]]; then
    echo "No PID file: ${PID_FILE}"
    return 0
  fi

  local had_entries=0
  while IFS='|' read -r pid name cmd || [[ -n "${pid:-}" ]]; do
    [[ -z "${pid:-}" ]] && continue
    had_entries=1
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      echo "Stopped ${name} (pid=${pid})"
    else
      echo "Already stopped ${name} (pid=${pid})"
    fi
  done <"${PID_FILE}"

  rm -f "${PID_FILE}"
  [[ "${had_entries}" -eq 1 ]] || echo "PID file existed but had no entries"
}

status_boki() {
  if [[ ! -f "${PID_FILE}" ]]; then
    echo "Boki status: stopped (no pid file)"
    return 1
  fi

  local alive=0
  local total=0
  while IFS='|' read -r pid name cmd || [[ -n "${pid:-}" ]]; do
    [[ -z "${pid:-}" ]] && continue
    total=$((total + 1))
    if kill -0 "${pid}" 2>/dev/null; then
      alive=$((alive + 1))
      echo "${name}: alive (pid=${pid})"
    else
      echo "${name}: not running (pid=${pid})"
    fi
  done <"${PID_FILE}"

  echo "Boki status: ${alive}/${total} processes alive"
  [[ "${alive}" -gt 0 ]]
}

main() {
  local cmd="${1:-}"
  [[ -n "${cmd}" ]] || {
    usage
    exit 1
  }

  assert_boki_root

  case "${cmd}" in
    build)
      build_boki
      ;;
    start)
      start_boki
      ;;
    stop)
      stop_boki
      ;;
    restart)
      stop_boki || true
      start_boki
      ;;
    status)
      status_boki
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
