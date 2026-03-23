#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CB_ROOT="${CB_ROOT:-${MASTER_SEBS_ROOT}/../base_systems/cloudburst}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <start|stop|restart|status>

Env:
  CB_ROOT=<path>            Override Cloudburst repo root.
  BUILD_CLOUDBURST=<y|n>    Build before start (default: n).
  REMOVE_LOGS=<y|n>         Remove logs on stop (default: n).
USAGE
}

assert_cb_root() {
  if [[ ! -d "${CB_ROOT}" ]]; then
    echo "Cloudburst root not found: ${CB_ROOT}" >&2
    exit 1
  fi
}

start_cloudburst() {
  local build_flag="${BUILD_CLOUDBURST:-n}"
  echo "Starting Cloudburst from ${CB_ROOT} (build=${build_flag})"
  (cd "${CB_ROOT}" && ./scripts/start-cloudburst-local.sh "${build_flag}")
}

stop_cloudburst() {
  local remove_logs="${REMOVE_LOGS:-n}"
  echo "Stopping Cloudburst from ${CB_ROOT} (remove_logs=${remove_logs})"
  (cd "${CB_ROOT}" && ./scripts/stop-cloudburst-local.sh "${remove_logs}")
}

status_cloudburst() {
  local pid_file="${CB_ROOT}/pids"
  if [[ ! -f "${pid_file}" ]]; then
    echo "Cloudburst status: stopped (no pids file)"
    return 1
  fi

  local alive=0
  local total=0
  while IFS='' read -r line || [[ -n "$line" ]]; do
    [[ -z "${line}" ]] && continue
    total=$((total + 1))
    if kill -0 "${line}" 2>/dev/null; then
      alive=$((alive + 1))
      echo "PID ${line}: alive"
    else
      echo "PID ${line}: not running"
    fi
  done < "${pid_file}"

  echo "Cloudburst status: ${alive}/${total} processes alive"
  [[ "${alive}" -gt 0 ]]
}

main() {
  local cmd="${1:-}"
  if [[ -z "${cmd}" ]]; then
    usage
    exit 1
  fi

  assert_cb_root

  case "${cmd}" in
    start)
      start_cloudburst
      ;;
    stop)
      stop_cloudburst
      ;;
    restart)
      stop_cloudburst || true
      start_cloudburst
      ;;
    status)
      status_cloudburst
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
