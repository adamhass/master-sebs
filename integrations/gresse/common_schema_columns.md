# Common schema columns (Gresse)

**Pipeline (native HTTP bench)**

1. [`run_gresse_bench.sh`](run_gresse_bench.sh) (set `GRESSE_HTTP_URL`; optional `BODY_JSON`) → `results/raw/<run>/` with `latency_samples.jsonl`, `timing.json`, `metadata.json`.
2. [`collect_gresse_results.py`](collect_gresse_results.py) → `collected_metrics.json`.
3. [`gresse_to_common_schema.py`](gresse_to_common_schema.py) → common JSONL/CSV.

**Canonical definitions:** [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md) and [`../common_schema/fields.py`](../common_schema/fields.py).

Gresse-specific notes:

- Default `system_variant` in metadata: `gresse-native`.
- Default request payload is a Gresse `CRDTClientRequest` mutation for the benchmark CRDT.
- Current normalization tracks HTTP invoke latency; replica-side convergence and sync metrics can be added once the runtime emits sidecars in a stable format.
