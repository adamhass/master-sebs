#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GRESSE_ROOT="${GRESSE_ROOT:-${MASTER_SEBS_ROOT}/../Gresse}"
KIND_CONFIG="${SCRIPT_DIR}/knative/kind-cluster.yaml"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-gresse-knative}"
K8S_NAMESPACE="${K8S_NAMESPACE:-gresse}"
KSERVICE_NAME="${KSERVICE_NAME:-gresse-bench}"
K8S_SECRET_NAME="${K8S_SECRET_NAME:-gresse-s3-config}"
AWS_PROFILE_SECRET_NAME="${AWS_PROFILE_SECRET_NAME:-gresse-aws-profile}"
GRESSE_IMAGE="${GRESSE_IMAGE:-dev.local/gresse-bench:knative-dev}"

KNATIVE_SERVING_VERSION="${KNATIVE_SERVING_VERSION:-knative-v1.21.2}"
KNATIVE_KOURIER_VERSION="${KNATIVE_KOURIER_VERSION:-knative-v1.21.0}"
KNATIVE_DOMAIN_SUFFIX="${KNATIVE_DOMAIN_SUFFIX:-127.0.0.1.sslip.io}"
KOURIER_HTTP_NODEPORT="${KOURIER_HTTP_NODEPORT:-31080}"
KOURIER_HTTPS_NODEPORT="${KOURIER_HTTPS_NODEPORT:-31443}"

GRESSE_HTTP_PORT="${GRESSE_HTTP_PORT:-8080}"
GRESSE_INTERNAL_PORT="${GRESSE_INTERNAL_PORT:-8081}"
GRESSE_RESULT_DIR_PATH="${GRESSE_RESULT_DIR_PATH:-/tmp/gresse-results}"
GRESSE_SYNC_INTERVAL_MS="${GRESSE_SYNC_INTERVAL_MS:-1000}"
GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS="${GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS:-1000}"
GRESSE_LOG="${GRESSE_LOG:-info}"
GRESSE_CONTAINER_CONCURRENCY="${GRESSE_CONTAINER_CONCURRENCY:-100}"
GRESSE_MIN_SCALE="${GRESSE_MIN_SCALE:-1}"
GRESSE_MAX_SCALE="${GRESSE_MAX_SCALE:-1}"

AWS_PROFILE="${AWS_PROFILE:-gresse}"
AWS_REGION="${AWS_REGION:-eu-north-1}"
AWS_SHARED_CREDENTIALS_FILE="${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}"
AWS_CONFIG_FILE="${AWS_CONFIG_FILE:-${HOME}/.aws/config}"

GRESSE_OBJECT_STORAGE_URL="${GRESSE_OBJECT_STORAGE_URL:-}"
GRESSE_OBJECT_STORAGE_REGION="${GRESSE_OBJECT_STORAGE_REGION:-eu-north-1}"
GRESSE_OBJECT_STORAGE_BUCKET="${GRESSE_OBJECT_STORAGE_BUCKET:-gresse}"
GRESSE_OBJECT_STORAGE_ACCESS_KEY="${GRESSE_OBJECT_STORAGE_ACCESS_KEY:-}"
GRESSE_OBJECT_STORAGE_SECRET_KEY="${GRESSE_OBJECT_STORAGE_SECRET_KEY:-}"
GRESSE_OBJECT_STORAGE_SESSION_TOKEN="${GRESSE_OBJECT_STORAGE_SESSION_TOKEN:-}"
GRESSE_PERSISTENT_REPLICA_PATH="${GRESSE_PERSISTENT_REPLICA_PATH:-experiment1/persistent.json}"
GRESSE_MEMBERSHIP_DIRECTORY_PATH="${GRESSE_MEMBERSHIP_DIRECTORY_PATH:-experiment1/membership}"

usage() {
  cat >&2 <<EOF
Usage: $0 {bootstrap|build-image|load-image|deploy|start|status|url|logs|delete|destroy}

Commands:
  bootstrap   Create a KinD cluster and install Knative Serving + Kourier.
  build-image Build the local Gresse benchmark container image.
  load-image  Load the local image into the KinD cluster.
  deploy      Create/update the S3 secret and deploy the Knative Service.
  start       bootstrap + build-image + load-image + deploy.
  status      Show Knative and service status.
  url         Print the Knative service URL.
  logs        Print recent logs from pods in the service namespace.
  delete      Delete the Knative Service and S3 secret.
  destroy     Delete the KinD cluster.
EOF
}

require_tool() {
  local tool="$1"
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Missing required tool: ${tool}" >&2
    exit 1
  fi
}

ensure_gresse_root() {
  if [[ ! -d "${GRESSE_ROOT}" ]]; then
    echo "Gresse root not found: ${GRESSE_ROOT}" >&2
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
  ensure_gresse_root
  docker build \
    -f "${SCRIPT_DIR}/Dockerfile.knative" \
    -t "${GRESSE_IMAGE}" \
    "${GRESSE_ROOT}"
}

load_image() {
  require_tool kind
  ensure_kind_cluster
  kind load docker-image "${GRESSE_IMAGE}" --name "${KIND_CLUSTER_NAME}"
}

use_explicit_gresse_credentials() {
  [[ -n "${GRESSE_OBJECT_STORAGE_ACCESS_KEY}" || -n "${GRESSE_OBJECT_STORAGE_SECRET_KEY}" || -n "${GRESSE_OBJECT_STORAGE_SESSION_TOKEN}" ]]
}

require_s3_env() {
  local missing=0
  for var_name in GRESSE_OBJECT_STORAGE_BUCKET GRESSE_OBJECT_STORAGE_REGION; do
    if [[ -z "${!var_name}" ]]; then
      echo "Missing required environment variable: ${var_name}" >&2
      missing=1
    fi
  done
  if use_explicit_gresse_credentials; then
    for var_name in GRESSE_OBJECT_STORAGE_ACCESS_KEY GRESSE_OBJECT_STORAGE_SECRET_KEY; do
      if [[ -z "${!var_name}" ]]; then
        echo "Missing required environment variable: ${var_name}" >&2
        missing=1
      fi
    done
  else
    if [[ ! -f "${AWS_SHARED_CREDENTIALS_FILE}" ]]; then
      echo "Missing AWS shared credentials file: ${AWS_SHARED_CREDENTIALS_FILE}" >&2
      missing=1
    fi
    if [[ ! -f "${AWS_CONFIG_FILE}" ]]; then
      echo "Missing AWS config file: ${AWS_CONFIG_FILE}" >&2
      missing=1
    fi
  fi
  if [[ "${missing}" -ne 0 ]]; then
    exit 1
  fi
}

apply_config_secret() {
  require_tool kubectl
  require_s3_env
  kubectl create namespace "${K8S_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create secret generic "${K8S_SECRET_NAME}" \
    --namespace "${K8S_NAMESPACE}" \
    --from-literal=GRESSE_OBJECT_STORAGE_URL="${GRESSE_OBJECT_STORAGE_URL}" \
    --from-literal=GRESSE_OBJECT_STORAGE_REGION="${GRESSE_OBJECT_STORAGE_REGION}" \
    --from-literal=GRESSE_OBJECT_STORAGE_BUCKET="${GRESSE_OBJECT_STORAGE_BUCKET}" \
    --from-literal=GRESSE_OBJECT_STORAGE_ACCESS_KEY="${GRESSE_OBJECT_STORAGE_ACCESS_KEY}" \
    --from-literal=GRESSE_OBJECT_STORAGE_SECRET_KEY="${GRESSE_OBJECT_STORAGE_SECRET_KEY}" \
    --from-literal=GRESSE_OBJECT_STORAGE_SESSION_TOKEN="${GRESSE_OBJECT_STORAGE_SESSION_TOKEN}" \
    --from-literal=GRESSE_PERSISTENT_REPLICA_PATH="${GRESSE_PERSISTENT_REPLICA_PATH}" \
    --from-literal=GRESSE_MEMBERSHIP_DIRECTORY_PATH="${GRESSE_MEMBERSHIP_DIRECTORY_PATH}" \
    --dry-run=client \
    -o yaml | kubectl apply -f -
}

apply_aws_profile_secret() {
  require_tool kubectl
  if use_explicit_gresse_credentials; then
    kubectl delete secret "${AWS_PROFILE_SECRET_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
    return 0
  fi
  kubectl create secret generic "${AWS_PROFILE_SECRET_NAME}" \
    --namespace "${K8S_NAMESPACE}" \
    --from-file=credentials="${AWS_SHARED_CREDENTIALS_FILE}" \
    --from-file=config="${AWS_CONFIG_FILE}" \
    --dry-run=client \
    -o yaml | kubectl apply -f -
}

apply_ksvc() {
  require_tool kubectl
  apply_config_secret
  apply_aws_profile_secret

  local volume_block=""
  local volume_mount_block=""
  local aws_env_block=""
  if ! use_explicit_gresse_credentials; then
    volume_block=$(cat <<EOF
      volumes:
        - name: aws-profile
          secret:
            secretName: ${AWS_PROFILE_SECRET_NAME}
EOF
)
    volume_mount_block=$(cat <<'EOF'
          volumeMounts:
            - name: aws-profile
              mountPath: /var/run/aws
              readOnly: true
EOF
)
    aws_env_block=$(cat <<EOF
            - name: AWS_PROFILE
              value: "${AWS_PROFILE}"
            - name: AWS_REGION
              value: "${AWS_REGION}"
            - name: AWS_DEFAULT_REGION
              value: "${AWS_REGION}"
            - name: AWS_SHARED_CREDENTIALS_FILE
              value: /var/run/aws/credentials
            - name: AWS_CONFIG_FILE
              value: /var/run/aws/config
EOF
)
  fi

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
        autoscaling.knative.dev/min-scale: "${GRESSE_MIN_SCALE}"
        autoscaling.knative.dev/max-scale: "${GRESSE_MAX_SCALE}"
    spec:
      containerConcurrency: ${GRESSE_CONTAINER_CONCURRENCY}
      timeoutSeconds: 300
${volume_block}
      containers:
        - image: ${GRESSE_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - name: http1
              containerPort: ${GRESSE_HTTP_PORT}
${volume_mount_block}
          env:
            - name: GRESSE_ADDR
              value: "0.0.0.0"
${aws_env_block}
            - name: GRESSE_HTTP_PORT
              value: "${GRESSE_HTTP_PORT}"
            - name: GRESSE_INTERNAL_PORT
              value: "${GRESSE_INTERNAL_PORT}"
            - name: GRESSE_RESULT_DIR_PATH
              value: "${GRESSE_RESULT_DIR_PATH}"
            - name: GRESSE_SYNC_INTERVAL_MS
              value: "${GRESSE_SYNC_INTERVAL_MS}"
            - name: GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS
              value: "${GRESSE_OBJECT_STORAGE_DISCOVERY_INTERVAL_MS}"
            - name: GRESSE_LOG
              value: "${GRESSE_LOG}"
            - name: GRESSE_OBJECT_STORAGE_URL
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_URL
            - name: GRESSE_OBJECT_STORAGE_REGION
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_REGION
            - name: GRESSE_OBJECT_STORAGE_BUCKET
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_BUCKET
            - name: GRESSE_OBJECT_STORAGE_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_ACCESS_KEY
            - name: GRESSE_OBJECT_STORAGE_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_SECRET_KEY
            - name: GRESSE_OBJECT_STORAGE_SESSION_TOKEN
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_OBJECT_STORAGE_SESSION_TOKEN
            - name: GRESSE_PERSISTENT_REPLICA_PATH
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_PERSISTENT_REPLICA_PATH
            - name: GRESSE_MEMBERSHIP_DIRECTORY_PATH
              valueFrom:
                secretKeyRef:
                  name: ${K8S_SECRET_NAME}
                  key: GRESSE_MEMBERSHIP_DIRECTORY_PATH
EOF

  kubectl wait ksvc/"${KSERVICE_NAME}" -n "${K8S_NAMESPACE}" --for=condition=Ready --timeout=300s
}

show_status() {
  require_tool kubectl
  kubectl get pods -n knative-serving
  kubectl get pods -n kourier-system
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
  kubectl delete secret "${K8S_SECRET_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
  kubectl delete secret "${AWS_PROFILE_SECRET_NAME}" -n "${K8S_NAMESPACE}" --ignore-not-found=true
}

start_all() {
  kind_create_cluster
  install_knative
  build_image
  load_image
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
      load_image
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
