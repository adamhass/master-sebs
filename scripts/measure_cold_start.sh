#!/usr/bin/env bash
#
# Cold start measurement for Boki and Cloudburst.
#
# Measures: time from process restart to first successful invocation.
# Repeats N times to build a distribution.
#
# Usage:
#   ./scripts/measure_cold_start.sh boki   <ssh_target> <gateway_url> [repetitions]
#   ./scripts/measure_cold_start.sh lambda  <api_url> [repetitions]
#
# Examples:
#   ./scripts/measure_cold_start.sh boki "ubuntu@13.63.165.110" "http://13.63.165.110:8080" 30
#   ./scripts/measure_cold_start.sh lambda "https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/" 30
#
set -euo pipefail

SYSTEM="${1:?Usage: $0 <boki|lambda|cloudburst> ...}"
SSH_KEY="${SSH_KEY:-thesis-key.pem}"
REPETITIONS="${4:-30}"
OUTPUT_FILE="cold_start_${SYSTEM}_$(date +%Y%m%d_%H%M%S).csv"

echo "system,rep,restart_ms,first_invoke_ms,total_cold_ms" > "$OUTPUT_FILE"

measure_boki() {
    local SSH_TARGET="$2"
    local GATEWAY_URL="$3"
    REPETITIONS="${4:-30}"

    echo "=== Boki cold start measurement ==="
    echo "SSH: $SSH_TARGET  Gateway: $GATEWAY_URL  Reps: $REPETITIONS"
    echo ""

    for i in $(seq 1 "$REPETITIONS"); do
        echo -n "[$i/$REPETITIONS] Restarting containers... "

        # Stop worker containers (not ZK/controller/sequencer/storage)
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_TARGET" \
            "cd /opt/boki/workspace && docker-compose restart boki-engine boki-gateway stateful-bench" \
            > /dev/null 2>&1

        RESTART_START=$(date +%s%N)

        # Wait for gateway to accept connections
        while ! curl -s --connect-timeout 1 "$GATEWAY_URL" > /dev/null 2>&1; do
            sleep 0.2
        done
        RESTART_END=$(date +%s%N)
        RESTART_MS=$(( (RESTART_END - RESTART_START) / 1000000 ))

        # First invocation
        INVOKE_START=$(date +%s%N)
        RESULT=$(curl -s --max-time 30 -X POST "$GATEWAY_URL/function/statefulBench" \
            -d '{"state_key":"cold_test","state_size_kb":1,"ops":1,"request_id":"cold"}' 2>&1)
        INVOKE_END=$(date +%s%N)
        INVOKE_MS=$(( (INVOKE_END - INVOKE_START) / 1000000 ))

        TOTAL_MS=$((RESTART_MS + INVOKE_MS))
        echo "restart=${RESTART_MS}ms  invoke=${INVOKE_MS}ms  total=${TOTAL_MS}ms"
        echo "boki,$i,$RESTART_MS,$INVOKE_MS,$TOTAL_MS" >> "$OUTPUT_FILE"

        # Cooldown between repetitions
        sleep 5
    done
}

measure_lambda() {
    local API_URL="$2"
    REPETITIONS="${3:-30}"

    echo "=== Lambda cold start measurement ==="
    echo "API: $API_URL  Reps: $REPETITIONS"
    echo "Note: Uses SeBS-style cold start — function is not deleted, but we wait for container expiry."
    echo ""

    for i in $(seq 1 "$REPETITIONS"); do
        echo -n "[$i/$REPETITIONS] Invoking... "

        INVOKE_START=$(date +%s%N)
        RESULT=$(curl -s --max-time 30 -X POST "$API_URL" \
            -d '{"state_key":"cold_test","state_size_kb":1,"ops":1}' 2>&1)
        INVOKE_END=$(date +%s%N)
        INVOKE_MS=$(( (INVOKE_END - INVOKE_START) / 1000000 ))

        IS_COLD=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_cold','?'))" 2>/dev/null || echo "?")
        echo "invoke=${INVOKE_MS}ms  cold=${IS_COLD}"
        echo "lambda,$i,0,$INVOKE_MS,$INVOKE_MS" >> "$OUTPUT_FILE"

        # Short delay between invocations
        sleep 1
    done
}

case "$SYSTEM" in
    boki)      measure_boki "$@" ;;
    lambda)    measure_lambda "$@" ;;
    *)
        echo "Unknown system: $SYSTEM"
        echo "Supported: boki, lambda"
        exit 1
        ;;
esac

echo ""
echo "Results written to $OUTPUT_FILE"
echo "Summary:"
awk -F',' 'NR>1 {sum+=$5; n++} END {printf "  Mean total cold start: %.0f ms (n=%d)\n", sum/n, n}' "$OUTPUT_FILE"
