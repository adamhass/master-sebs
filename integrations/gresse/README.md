# Gresse Integration Track

This folder provides a native Gresse integration path under `master-sebs/integrations/`.
It is separate from the generic SeBS provider abstraction because Gresse is currently exercised as its own replicated runtime.

## Contents

- `deploy_gresse.sh`: local Gresse + MinIO build/start/stop/status wrapper using `../Gresse`.
- `run_gresse_bench.sh`: HTTP repeat client + `collect_gresse_results.py` (set `GRESSE_HTTP_URL` if not using the default local replica).
- `collect_gresse_results.py` / `gresse_to_common_schema.py`: raw run → `collected_metrics.json` → common JSONL/CSV.
- `common_schema_columns.md`: normalization field contract.
- `results/raw/.gitkeep`: raw run outputs.
- `results/normalized/.gitkeep`: normalized outputs.

## Paths

Default Gresse source root:

- `../Gresse` relative to `master-sebs/`

Override with:

- `GRESSE_ROOT=/absolute/path/to/Gresse`

## Quickstart (Local)

From `master-sebs/`:

```bash
./integrations/gresse/deploy_gresse.sh start
./integrations/gresse/deploy_gresse.sh status
./integrations/gresse/run_gresse_bench.sh 50
./integrations/gresse/deploy_gresse.sh stop
```

The local deploy wrapper assumes:

- Docker is available for the MinIO dependency in `Gresse/docker-compose.minio.yml`.
- The benchmark replica is the Rust example `examples/bench_function`.
- The default HTTP endpoint is `http://127.0.0.1:9090/`.

## Benchmark → common schema

After the replica is reachable, run:

```bash
GRESSE_HTTP_URL='http://127.0.0.1:9090/' ./integrations/gresse/run_gresse_bench.sh 100
python3 integrations/gresse/gresse_to_common_schema.py \
  --input-glob 'integrations/gresse/results/raw/*/collected_metrics.json' \
  --output-jsonl integrations/gresse/results/normalized/gresse_common.jsonl \
  --output-csv integrations/gresse/results/normalized/gresse_common.csv
```

## Notes

- This first scaffold targets local native execution only.
- The current collector measures end-to-end HTTP invoke latency; deeper CRDT convergence metrics can be added later from Gresse-emitted sidecars.
- Gresse uses eventual consistency by default in this benchmark path, so `consistency_model` defaults to `eventual`.
