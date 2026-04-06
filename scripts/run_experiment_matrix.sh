#!/usr/bin/env bash
#
# Run the full experiment matrix across all three systems.
#
# Usage:
#   ./scripts/run_experiment_matrix.sh [boki|lambda|all] [--dry-run]
#
# Results are written to results/<system>/<experiment>/
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEBS_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="${SEBS_DIR}/results"
DRY_RUN="${2:-}"

# Endpoints
BOKI_GATEWAY="http://16.170.141.184:8080"
LAMBDA_API="https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/"
CLOUDBURST_GATEWAY="http://13.60.72.131:8088"

mkdir -p "$RESULTS_DIR"

run_cmd() {
    echo ">>> $*"
    if [ "$DRY_RUN" != "--dry-run" ]; then
        eval "$@"
    fi
}

# ── Boki experiments (via SeBS provider) ──
run_boki() {
    echo ""
    echo "============================================"
    echo "  BOKI EXPERIMENTS"
    echo "============================================"

    # Steady-state throughput
    for c in 1 10 50 100; do
        echo ""
        echo "--- Boki throughput c=$c ---"
        run_cmd "cd '$SEBS_DIR' && SEBS_WITH_BOKI=true uv run python3 sebs.py experiment invoke perf-cost \
            --config config/experiments/boki-throughput-c${c}.json \
            --output-dir '$RESULTS_DIR/boki/throughput-c${c}'"
    done

    # Latency distribution
    echo ""
    echo "--- Boki latency distribution ---"
    run_cmd "cd '$SEBS_DIR' && SEBS_WITH_BOKI=true uv run python3 sebs.py experiment invoke perf-cost \
        --config config/experiments/boki-latency-dist.json \
        --output-dir '$RESULTS_DIR/boki/latency-dist'"

    # State size impact
    for kb in 1 64 512; do
        echo ""
        echo "--- Boki state size ${kb}KB ---"
        run_cmd "cd '$SEBS_DIR' && SEBS_WITH_BOKI=true uv run python3 sebs.py experiment invoke perf-cost \
            --config config/experiments/boki-statesize-${kb}kb.json \
            --output-dir '$RESULTS_DIR/boki/statesize-${kb}kb'"
    done
}

# ── Lambda experiments (via batch_invoke.py) ──
run_lambda() {
    echo ""
    echo "============================================"
    echo "  LAMBDA + REDIS EXPERIMENTS"
    echo "============================================"

    # Steady-state throughput
    for c in 1 10 50 100; do
        echo ""
        echo "--- Lambda throughput c=$c ---"
        mkdir -p "$RESULTS_DIR/lambda/throughput-c${c}/perf-cost"
        run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$LAMBDA_API' \
            --reps 200 --concurrency $c --state-size-kb 64 --function-name baseline-fn \
            --output '$RESULTS_DIR/lambda/throughput-c${c}/perf-cost/warm_results.json'"
    done

    # Latency distribution
    echo ""
    echo "--- Lambda latency distribution ---"
    mkdir -p "$RESULTS_DIR/lambda/latency-dist/perf-cost"
    run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$LAMBDA_API' \
        --reps 1000 --concurrency 50 --state-size-kb 64 --function-name baseline-fn \
        --output '$RESULTS_DIR/lambda/latency-dist/perf-cost/warm_results.json'"

    # State size impact
    for kb in 1 64 512; do
        echo ""
        echo "--- Lambda state size ${kb}KB ---"
        mkdir -p "$RESULTS_DIR/lambda/statesize-${kb}kb/perf-cost"
        run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$LAMBDA_API' \
            --reps 200 --concurrency 50 --state-size-kb $kb --function-name baseline-fn \
            --output '$RESULTS_DIR/lambda/statesize-${kb}kb/perf-cost/warm_results.json'"
    done
}

# ── Cloudburst experiments (via HTTP gateway + batch_invoke.py) ──
run_cloudburst() {
    echo ""
    echo "============================================"
    echo "  CLOUDBURST + ANNA KVS EXPERIMENTS"
    echo "============================================"

    # Steady-state throughput
    for c in 1 10 50 100; do
        echo ""
        echo "--- Cloudburst throughput c=$c ---"
        mkdir -p "$RESULTS_DIR/cloudburst/throughput-c${c}/perf-cost"
        run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$CLOUDBURST_GATEWAY/function/stateful_bench' \
            --reps 200 --concurrency $c --state-size-kb 64 --function-name stateful_bench \
            --output '$RESULTS_DIR/cloudburst/throughput-c${c}/perf-cost/warm_results.json'"
    done

    # Latency distribution
    echo ""
    echo "--- Cloudburst latency distribution ---"
    mkdir -p "$RESULTS_DIR/cloudburst/latency-dist/perf-cost"
    run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$CLOUDBURST_GATEWAY/function/stateful_bench' \
        --reps 1000 --concurrency 50 --state-size-kb 64 --function-name stateful_bench \
        --output '$RESULTS_DIR/cloudburst/latency-dist/perf-cost/warm_results.json'"

    # State size impact
    for kb in 1 64 512; do
        echo ""
        echo "--- Cloudburst state size ${kb}KB ---"
        mkdir -p "$RESULTS_DIR/cloudburst/statesize-${kb}kb/perf-cost"
        run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/batch_invoke.py '$CLOUDBURST_GATEWAY/function/stateful_bench' \
            --reps 200 --concurrency 50 --state-size-kb $kb --function-name stateful_bench \
            --output '$RESULTS_DIR/cloudburst/statesize-${kb}kb/perf-cost/warm_results.json'"
    done
}

# ── Post-processing ──
postprocess() {
    echo ""
    echo "============================================"
    echo "  POST-PROCESSING"
    echo "============================================"

    for system in boki lambda cloudburst; do
        if [ -d "$RESULTS_DIR/$system" ]; then
            echo ""
            echo "--- $system ---"
            run_cmd "cd '$SEBS_DIR' && uv run python3 scripts/postprocess_results.py \
                '$RESULTS_DIR/$system' --csv '$RESULTS_DIR/${system}_all.csv'"
        fi
    done
}

# ── Main ──
SYSTEM="${1:-all}"

case "$SYSTEM" in
    boki)       run_boki; postprocess ;;
    lambda)     run_lambda; postprocess ;;
    cloudburst) run_cloudburst; postprocess ;;
    all)        run_boki; run_lambda; run_cloudburst; postprocess ;;
    *)          echo "Usage: $0 [boki|lambda|cloudburst|all] [--dry-run]"; exit 1 ;;
esac

echo ""
echo "Done. Results in $RESULTS_DIR/"
