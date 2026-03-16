#!/usr/bin/env bash
set -euo pipefail

# Run from repository root: master-sebs/

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c1.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c1
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c1.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c1

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c10.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c10
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c10.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c10

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c50.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c50
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c50.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c50

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c100.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c100
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c100.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c100

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c500.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c500
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-redis/perf-cost-c500.json --deployment aws --output-dir phase1-results/baseline-lambda-redis/c500

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c1.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c1
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c1.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c1

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c10.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c10
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c10.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c10

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c50.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c50
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c50.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c50

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c100.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c100
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c100.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c100

./sebs.py experiment invoke perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c500.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c500
./sebs.py experiment process perf-cost --config config/phase1/baseline-lambda-dynamodb/perf-cost-c500.json --deployment aws --output-dir phase1-results/baseline-lambda-dynamodb/c500

./sebs.py experiment invoke perf-cost --config config/phase1/boki-shared-log/perf-cost-c10.json --deployment aws --output-dir phase1-results/boki-shared-log/c10
./sebs.py experiment process perf-cost --config config/phase1/boki-shared-log/perf-cost-c10.json --deployment aws --output-dir phase1-results/boki-shared-log/c10

./sebs.py experiment invoke perf-cost --config config/phase1/boki-shared-log/perf-cost-c100.json --deployment aws --output-dir phase1-results/boki-shared-log/c100
./sebs.py experiment process perf-cost --config config/phase1/boki-shared-log/perf-cost-c100.json --deployment aws --output-dir phase1-results/boki-shared-log/c100

./sebs.py experiment invoke perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c1.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c1
./sebs.py experiment process perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c1.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c1

./sebs.py experiment invoke perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c10.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c10
./sebs.py experiment process perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c10.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c10

./sebs.py experiment invoke perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c50.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c50
./sebs.py experiment process perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c50.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c50

./sebs.py experiment invoke perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c100.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c100
./sebs.py experiment process perf-cost --config config/phase1/crdt-muller-stateful/perf-cost-c100.json --deployment aws --output-dir phase1-results/crdt-muller-stateful/c100
