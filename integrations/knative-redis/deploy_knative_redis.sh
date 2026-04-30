#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KIND_CONFIG="${MASTER_SEBS_ROOT}/integrations/gresse/knative/kind-cluster.yaml"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-gresse-knative}"
K8S_NAMESPACE="${K8S_NAMESPACE:-knative-redis}"
KSERVICE_NAME="${KSERVICE_NAME:-redis-bench}"
REDIS_DEPLOYMENT_NAME="${REDIS_DEPLOYMENT_NAME:-redis-edge}"
REDIS_SERVICE_NAME="${REDIS_SERVICE_NAME:-redis-edge}"
APP_IMAGE="${APP_IMAGE:-dev.local/knative-redis-bench:dev}"
APP_PORT="${APP_PORT:-8080}"
CONTAINER_CONCURRENCY="${CONTAINER_CONCURRENCY:-100}"
MIN_SCALE="${MIN_SCALE:-1}"
MAX_SCALE="${MAX_SCALE:-1}"

KNATIVE_SERVING_VERSION="${KNATIVE_SERVING_VERSION:-knative-v1.21.2}"
KNATIVE_KOURIER_VERSION="${KNATIVE_KOURIER_VERSION:-knative-v1.21.0}"
KNATIVE_DOMAIN_SUFFIX="${KNATIVE_DOMAIN_SUFFIX:-127.0.0.1.sslip.io}"
KOURIER_HTTP_NODEPORT="${KOURIER_HTTP_NODEPORT:-31080}"
KOURIER_HTTPS_NODEPORT="${KOURIER_HTTPS_NODEPORT:-31443}"

REDIS_MODE="${REDIS_MODE:-local}"
REDIS_HOST="${REDIS_HOST:-${REDIS_SERVICE_NAME}.${K8S_NAMESPACE}.svc.cluster.local}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_IMAGE="${REDIS_IMAGE:-redis:7.2-alpine}"

usage() {
  cat >&2 <<EOF
Usage: $0 {bootstrap|build-image|load-image|deploy|start|status|url|logs|delete|destroy}

Environment:
  REDIS_MODE=local|remote  Deploy local in-cluster Redis or use REDIS_HOST/REDIS_PORT.
  CONTAINER_CONCURRENCY    Knative per-pod concurrency limit (default: 100).
  MIN_SCALE/MAX_SCALE      Knative autoscaling bounds (default: 1/1).
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
  docker build -f "${SCRIPT_DIR}/Dockerfile" -t "${APP_IMAGE}" "${MASTER_SEBS_ROOT}"
}

load_images() {
  require_tool kind
  ensure_kind_cluster
  kind load docker-image "${APP_IMAGE}" --name "${KIND_CLUSTER_NAME}"
  if [[ "${REDIS_MODE}" == "local" ]]; then
    kind load docker-image "${REDIS_IMAGE}" --name "${KIND_CLUSTER_NAME}" || true
  fi
}

apply_namespace() {
  kubectl create namespace "${K8S_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
}

apply_redis() {
  require_tool kubectl
  apply_namespace

  if [[ "${REDIS_MODE}" != "local" ]]; then
    kubectl delete deployment "${REDIS_DEPLOYMENT_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
    kubectl delete service "${REDIS_SERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
    return 0
  fi

  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${REDIS_DEPLOYMENT_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${REDIS_DEPLOYMENT_NAME}
  template:
    metadata:
      labels:
        app: ${REDIS_DEPLOYMENT_NAME}
    spec:
      containers:
        - name: redis
          image: ${REDIS_IMAGE}
          imagePullPolicy: IfNotPresent
          args:
            - redis-server
            - --save
            - ""
            - --appendonly
            - "no"
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: ${REDIS_SERVICE_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  selector:
    app: ${REDIS_DEPLOYMENT_NAME}
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
EOF

  kubectl wait deployment/"${REDIS_DEPLOYMENT_NAME}" -n "${K8S_NAMESPACE}" --for=condition=Available --timeout=300s
}

apply_ksvc() {
  require_tool kubectl
  apply_namespace
  apply_redis

  cat <<EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${KSERVICE_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/min-scale: "${MIN_SCALE}"
        autoscaling.knative.dev/max-scale: "${MAX_SCALE}"
    spec:
      containerConcurrency: ${CONTAINER_CONCURRENCY}
      timeoutSeconds: 300
      containers:
        - image: ${APP_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - name: http1
              containerPort: ${APP_PORT}
          env:
            - name: REDIS_HOST
              value: "${REDIS_HOST}"
            - name: REDIS_PORT
              value: "${REDIS_PORT}"
EOF

  kubectl wait ksvc/"${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" --for=condition=Ready --timeout=300s
}

show_status() {
  require_tool kubectl
  kubectl get pods -n "${K8S_NAMESPACE}" || true
  kubectl get svc -n "${K8S_NAMESPACE}" || true
  kubectl get ksvc -n "${K8S_NAMESPACE}" || true
  kubectl get revisions -n "${K8S_NAMESPACE}" || true
}

show_url() {
  require_tool kubectl
  kubectl get ksvc "${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" -o jsonpath='{.status.url}{"\n"}'
}

show_logs() {
  require_tool kubectl
  kubectl logs -n "${K8S_NAMESPACE}" -l serving.knative.dev/service="${KSERVICE_NAME}" --tail=200
}

delete_service() {
  require_tool kubectl
  kubectl delete ksvc "${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete deployment "${REDIS_DEPLOYMENT_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete service "${REDIS_SERVICE_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
}

start_all() {
  kind_create_cluster
  install_knative
  build_image
  load_images
  apply_ksvc
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
      load_images
      ;;
    deploy)
      apply_ksvc
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
      delete_service
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
