#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KIND_CONFIG="${MASTER_SEBS_ROOT}/integrations/gresse/knative/kind-cluster.yaml"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-gresse-knative}"
K8S_NAMESPACE="${K8S_NAMESPACE:-restate-local}"
KSERVICE_NAME="${KSERVICE_NAME:-restate-handler}"
HANDLER_IMAGE="${HANDLER_IMAGE:-dev.local/restate-handler:knative-dev}"
HANDLER_PORT="${HANDLER_PORT:-9080}"
HANDLER_CONCURRENCY="${HANDLER_CONCURRENCY:-100}"
HANDLER_MIN_SCALE="${HANDLER_MIN_SCALE:-1}"
HANDLER_MAX_SCALE="${HANDLER_MAX_SCALE:-1}"

RESTATE_DEPLOYMENT_NAME="${RESTATE_DEPLOYMENT_NAME:-restate}"
RESTATE_IMAGE="${RESTATE_IMAGE:-docker.io/restatedev/restate:latest}"
RESTATE_ADMIN_SERVICE_NAME="${RESTATE_ADMIN_SERVICE_NAME:-restate-admin}"
RESTATE_INGRESS_SERVICE_NAME="${RESTATE_INGRESS_SERVICE_NAME:-restate-ingress}"
RESTATE_DATA_DIR="${RESTATE_DATA_DIR:-/restate-data}"

KNATIVE_SERVING_VERSION="${KNATIVE_SERVING_VERSION:-knative-v1.21.2}"
KNATIVE_KOURIER_VERSION="${KNATIVE_KOURIER_VERSION:-knative-v1.21.0}"
KNATIVE_DOMAIN_SUFFIX="${KNATIVE_DOMAIN_SUFFIX:-127.0.0.1.sslip.io}"
KOURIER_HTTP_NODEPORT="${KOURIER_HTTP_NODEPORT:-31080}"
KOURIER_HTTPS_NODEPORT="${KOURIER_HTTPS_NODEPORT:-31443}"

LOCAL_RESTATE_PORT="${LOCAL_RESTATE_PORT:-18080}"
LOCAL_ADMIN_PORT="${LOCAL_ADMIN_PORT:-19070}"
PORT_FORWARD_PID_FILE="${PORT_FORWARD_PID_FILE:-/tmp/restate-local-port-forward.pid}"
PORT_FORWARD_LOG_FILE="${PORT_FORWARD_LOG_FILE:-/tmp/restate-local-port-forward.log}"

usage() {
  cat >&2 <<EOF
Usage: $0 {bootstrap|build-image|load-image|deploy|register|start-forward|stop-forward|start|status|url|logs|delete|destroy}

Commands:
  bootstrap     Create KinD cluster if needed and install Knative.
  build-image   Build the local Restate handler container image.
  load-image    Load the handler image into KinD.
  deploy        Deploy/update the Restate server and Knative handler.
  register      Register the handler URL with Restate.
  start-forward Start localhost port-forward to Restate ingress.
  stop-forward  Stop the localhost port-forward.
  start         bootstrap + build-image + load-image + deploy + register + start-forward.
  status        Show Restate and Knative status.
  url           Print the local benchmark URL template.
  logs          Show recent logs for Restate and handler pods.
  delete        Delete Restate and handler resources.
  destroy       Delete the KinD cluster.
EOF
}

require_tool() {
  local tool="$1"
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Missing required tool: ${tool}" >&2
    exit 1
  fi
}

ensure_kind_cluster() {
  if ! kind get clusters | grep -Fx "${KIND_CLUSTER_NAME}" >/dev/null 2>&1; then
    echo "KinD cluster '${KIND_CLUSTER_NAME}' does not exist" >&2
    exit 1
  fi
}

kind_create_cluster() {
  require_tool docker
  require_tool kind
  if kind get clusters | grep -Fx "${KIND_CLUSTER_NAME}" >/dev/null 2>&1; then
    echo "KinD cluster '${KIND_CLUSTER_NAME}' already exists"
    return 0
  fi
  kind create cluster --name "${KIND_CLUSTER_NAME}" --config "${KIND_CONFIG}"
}

kind_delete_cluster() {
  require_tool kind
  stop_port_forward || true
  if kind get clusters | grep -Fx "${KIND_CLUSTER_NAME}" >/dev/null 2>&1; then
    kind delete cluster --name "${KIND_CLUSTER_NAME}"
  else
    echo "KinD cluster '${KIND_CLUSTER_NAME}' does not exist"
  fi
}

install_knative() {
  require_tool kubectl
  ensure_kind_cluster

  kubectl apply -f "https://github.com/knative/serving/releases/download/${KNATIVE_SERVING_VERSION}/serving-crds.yaml"
  kubectl apply -f "https://github.com/knative/serving/releases/download/${KNATIVE_SERVING_VERSION}/serving-core.yaml"
  kubectl apply -f "https://github.com/knative-extensions/net-kourier/releases/download/${KNATIVE_KOURIER_VERSION}/kourier.yaml"

  kubectl patch configmap/config-network \
    --namespace knative-serving \
    --type merge \
    --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

  kubectl patch configmap/config-deployment \
    --namespace knative-serving \
    --type merge \
    --patch '{"data":{"registries-skipping-tag-resolving":"dev.local"}}'

  kubectl patch configmap/config-domain \
    --namespace knative-serving \
    --type merge \
    --patch "{\"data\":{\"${KNATIVE_DOMAIN_SUFFIX}\":\"\"}}"

  kubectl patch service/kourier \
    --namespace kourier-system \
    --type merge \
    --patch "{\"spec\":{\"type\":\"NodePort\",\"ports\":[{\"name\":\"http2\",\"port\":80,\"protocol\":\"TCP\",\"targetPort\":8080,\"nodePort\":${KOURIER_HTTP_NODEPORT}},{\"name\":\"https\",\"port\":443,\"protocol\":\"TCP\",\"targetPort\":8443,\"nodePort\":${KOURIER_HTTPS_NODEPORT}}]}}"

  kubectl wait --namespace knative-serving --for=condition=Available deployment --all --timeout=300s
  kubectl wait --namespace kourier-system --for=condition=Available deployment --all --timeout=300s
}

build_image() {
  require_tool docker
  docker build -f "${SCRIPT_DIR}/Dockerfile.knative-handler" -t "${HANDLER_IMAGE}" "${MASTER_SEBS_ROOT}"
}

load_image() {
  require_tool kind
  ensure_kind_cluster
  kind load docker-image "${HANDLER_IMAGE}" --name "${KIND_CLUSTER_NAME}"
}

apply_namespace() {
  kubectl create namespace "${K8S_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
}

apply_restate() {
  require_tool kubectl
  apply_namespace

  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${RESTATE_DEPLOYMENT_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${RESTATE_DEPLOYMENT_NAME}
  template:
    metadata:
      labels:
        app: ${RESTATE_DEPLOYMENT_NAME}
    spec:
      containers:
        - name: restate
          image: ${RESTATE_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
          command:
            - /bin/sh
            - -c
            - |
              cat > /tmp/restate.toml <<CFG
              cluster-name = "local-restate"
              node-name = "node-0"
              default-replication = 1
              auto-provision = true
              advertised-address = "\${POD_IP}:5122"
              roles = ["worker", "log-server", "metadata-server", "admin", "http-ingress"]

              [metadata-client]
              addresses = ["127.0.0.1:5122"]

              [admin]
              bind-address = "0.0.0.0:9070"

              [ingress]
              bind-address = "0.0.0.0:8080"
              CFG
              exec restate-server --config-file /tmp/restate.toml
          ports:
            - name: ingress
              containerPort: 8080
            - name: admin
              containerPort: 9070
            - name: fabric
              containerPort: 5122
          volumeMounts:
            - name: restate-data
              mountPath: ${RESTATE_DATA_DIR}
      volumes:
        - name: restate-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ${RESTATE_INGRESS_SERVICE_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  selector:
    app: ${RESTATE_DEPLOYMENT_NAME}
  ports:
    - name: ingress
      port: 8080
      targetPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: ${RESTATE_ADMIN_SERVICE_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  selector:
    app: ${RESTATE_DEPLOYMENT_NAME}
  ports:
    - name: admin
      port: 9070
      targetPort: 9070
EOF

  kubectl wait deployment/"${RESTATE_DEPLOYMENT_NAME}" -n "${K8S_NAMESPACE}" --for=condition=Available --timeout=300s
}

apply_handler() {
  require_tool kubectl
  apply_namespace

  cat <<EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${KSERVICE_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  template:
    metadata:
      labels:
        networking.knative.dev/visibility: cluster-local
      annotations:
        autoscaling.knative.dev/min-scale: "${HANDLER_MIN_SCALE}"
        autoscaling.knative.dev/max-scale: "${HANDLER_MAX_SCALE}"
    spec:
      containerConcurrency: ${HANDLER_CONCURRENCY}
      timeoutSeconds: 300
      containers:
        - image: ${HANDLER_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - name: http1
              containerPort: ${HANDLER_PORT}
EOF

  kubectl wait ksvc/"${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" --for=condition=Ready --timeout=300s
}

wait_for_admin() {
  local tries=0
  while [[ "${tries}" -lt 60 ]]; do
    if curl -sf "http://127.0.0.1:${LOCAL_ADMIN_PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    tries=$((tries + 1))
  done
  echo "Timed out waiting for Restate admin health" >&2
  return 1
}

register_handler() {
  require_tool kubectl
  require_tool curl

  local handler_url="http://${KSERVICE_NAME}.${K8S_NAMESPACE}.svc.cluster.local"
  local pf_pid=""

  kubectl port-forward --address 127.0.0.1 -n "${K8S_NAMESPACE}" \
    svc/"${RESTATE_ADMIN_SERVICE_NAME}" "${LOCAL_ADMIN_PORT}:9070" \
    >/tmp/restate-admin-port-forward.log 2>&1 &
  pf_pid=$!

  cleanup() {
    if [[ -n "${pf_pid}" ]] && kill -0 "${pf_pid}" >/dev/null 2>&1; then
      kill "${pf_pid}" >/dev/null 2>&1 || true
      wait "${pf_pid}" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT

  wait_for_admin

  curl -sf -X POST "http://127.0.0.1:${LOCAL_ADMIN_PORT}/deployments" \
    -H 'Content-Type: application/json' \
    -d "{\"uri\":\"${handler_url}\"}" >/dev/null

  trap - EXIT
  cleanup
}

port_forward_running() {
  if [[ ! -f "${PORT_FORWARD_PID_FILE}" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "${PORT_FORWARD_PID_FILE}")"
  kill -0 "${pid}" >/dev/null 2>&1
}

start_port_forward() {
  require_tool kubectl
  require_tool python3
  if port_forward_running; then
    return 0
  fi
  local pid
  pid="$(python3 -c '
import os
import subprocess
import sys

pid_file, log_file, namespace, service_name, local_port = sys.argv[1:6]
log = open(log_file, "ab", buffering=0)
proc = subprocess.Popen(
    [
        "kubectl", "port-forward", "--address", "127.0.0.1",
        "-n", namespace, f"svc/{service_name}", f"{local_port}:8080",
    ],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print(proc.pid)
' "${PORT_FORWARD_PID_FILE}" "${PORT_FORWARD_LOG_FILE}" "${K8S_NAMESPACE}" "${RESTATE_INGRESS_SERVICE_NAME}" "${LOCAL_RESTATE_PORT}")"
  echo "${pid}" > "${PORT_FORWARD_PID_FILE}"
  sleep 2
}

stop_port_forward() {
  if ! [[ -f "${PORT_FORWARD_PID_FILE}" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "${PORT_FORWARD_PID_FILE}")"
  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
    wait "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${PORT_FORWARD_PID_FILE}"
}

show_status() {
  require_tool kubectl
  kubectl get pods -n "${K8S_NAMESPACE}" || true
  kubectl get svc -n "${K8S_NAMESPACE}" || true
  kubectl get ksvc -n "${K8S_NAMESPACE}" || true
  kubectl get revisions -n "${K8S_NAMESPACE}" || true
}

show_url() {
  echo "http://127.0.0.1:${LOCAL_RESTATE_PORT}/statefulBench/{key}/run"
}

show_logs() {
  require_tool kubectl
  kubectl logs -n "${K8S_NAMESPACE}" deployment/"${RESTATE_DEPLOYMENT_NAME}" --tail=200 || true
  kubectl logs -n "${K8S_NAMESPACE}" -l serving.knative.dev/service="${KSERVICE_NAME}" --tail=200 || true
}

delete_resources() {
  require_tool kubectl
  stop_port_forward || true
  kubectl delete ksvc "${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete deployment "${RESTATE_DEPLOYMENT_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete svc "${RESTATE_INGRESS_SERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete svc "${RESTATE_ADMIN_SERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
}

start_all() {
  kind_create_cluster
  install_knative
  build_image
  load_image
  apply_restate
  apply_handler
  register_handler
  start_port_forward
}

main() {
  case "${1:-}" in
    bootstrap)
      kind_create_cluster
      install_knative
      ;;
    build-image)
      build_image
      ;;
    load-image)
      load_image
      ;;
    deploy)
      apply_restate
      apply_handler
      ;;
    register)
      register_handler
      ;;
    start-forward)
      start_port_forward
      ;;
    stop-forward)
      stop_port_forward
      ;;
    start)
      start_all
      ;;
    status)
      show_status
      ;;
    url)
      show_url
      ;;
    logs)
      show_logs
      ;;
    delete)
      delete_resources
      ;;
    destroy)
      kind_delete_cluster
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
