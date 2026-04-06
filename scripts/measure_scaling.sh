#!/usr/bin/env bash
#
# Scale-up/down interruption measurement.
#
# Runs a sustained load, then mid-experiment adds or removes a worker.
# Captures per-invocation latency to measure the disruption window.
#
# Usage:
#   ./scripts/measure_scaling.sh boki <ssh_target> <gateway_url> <up|down> [duration_s] [concurrency]
#
# Examples:
#   ./scripts/measure_scaling.sh boki "ubuntu@13.63.165.110" "http://13.63.165.110:8080" up 120 10
#   ./scripts/measure_scaling.sh boki "ubuntu@13.63.165.110" "http://13.63.165.110:8080" down 120 10
#
set -euo pipefail

SYSTEM="${1:?Usage: $0 <boki|cloudburst> <ssh_target> <url> <up|down> [duration_s] [concurrency]}"
SSH_TARGET="${2:?SSH target required}"
URL="${3:?URL required}"
DIRECTION="${4:?Direction (up|down) required}"
DURATION_S="${5:-120}"
CONCURRENCY="${6:-10}"
SSH_KEY="${SSH_KEY:-thesis-key.pem}"

SCALE_AT=$((DURATION_S / 2))  # Scale event at midpoint
OUTPUT_FILE="scaling_${SYSTEM}_${DIRECTION}_$(date +%Y%m%d_%H%M%S).csv"
PAYLOAD='{"state_key":"scale_test","state_size_kb":1,"ops":1,"request_id":"scale"}'

echo "=== Scaling interruption measurement ==="
echo "System: $SYSTEM  Direction: $DIRECTION  Duration: ${DURATION_S}s  Concurrency: $CONCURRENCY"
echo "Scale event at: T+${SCALE_AT}s"
echo "Output: $OUTPUT_FILE"
echo ""

echo "timestamp_ms,latency_ms,phase" > "$OUTPUT_FILE"

# Background load generator
generate_load() {
    local END_TIME=$(($(date +%s) + DURATION_S))
    local PHASE="before"

    while [ "$(date +%s)" -lt "$END_TIME" ]; do
        local NOW_MS=$(($(date +%s%N) / 1000000))
        local ELAPSED=$(($(date +%s) - START_TIME))

        if [ "$ELAPSED" -ge "$SCALE_AT" ]; then
            PHASE="after"
        fi

        # Fire concurrent requests
        for j in $(seq 1 "$CONCURRENCY"); do
            (
                local T0=$(($(date +%s%N) / 1000000))
                curl -s --max-time 10 -X POST "$URL/function/statefulBench" -d "$PAYLOAD" > /dev/null 2>&1
                local T1=$(($(date +%s%N) / 1000000))
                echo "$T0,$((T1 - T0)),$PHASE" >> "$OUTPUT_FILE"
            ) &
        done
        wait

        sleep 0.5
    done
}

scale_boki() {
    echo "Waiting ${SCALE_AT}s before scaling event..."
    sleep "$SCALE_AT"

    if [ "$DIRECTION" = "up" ]; then
        echo "[T+${SCALE_AT}s] Scaling UP: starting additional echo-bench worker"
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_TARGET" \
            "cd /opt/boki/workspace && docker-compose up -d --scale echo-bench=2" 2>/dev/null
    else
        echo "[T+${SCALE_AT}s] Scaling DOWN: stopping echo-bench worker"
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_TARGET" \
            "cd /opt/boki/workspace && docker-compose up -d --scale echo-bench=0" 2>/dev/null
    fi

    echo "Scale event triggered. Continuing load..."
}

START_TIME=$(date +%s)

# Start load generator in background
generate_load &
LOAD_PID=$!

# Scale event at midpoint
scale_boki &
SCALE_PID=$!

# Wait for load generator to finish
wait "$LOAD_PID" 2>/dev/null || true
wait "$SCALE_PID" 2>/dev/null || true

echo ""
echo "Results written to $OUTPUT_FILE"
TOTAL=$(wc -l < "$OUTPUT_FILE")
echo "Total data points: $((TOTAL - 1))"

# Summary stats per phase
echo ""
echo "Phase summary:"
awk -F',' 'NR>1 {
    sum[$3]+=$2; n[$3]++;
    if($2>max[$3]) max[$3]=$2
} END {
    for(p in sum) printf "  %s: mean=%.0fms  max=%dms  n=%d\n", p, sum[p]/n[p], max[p], n[p]
}' "$OUTPUT_FILE"
