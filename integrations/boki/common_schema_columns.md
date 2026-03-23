# Common schema columns (Boki)

**Pipeline (HTTP gateway smoke / bench)**

1. [`run_boki_bench.sh`](run_boki_bench.sh) (set `BOKI_HTTP_URL`; optional `HTTP_METHOD`, `BODY_JSON`) → `results/raw/<run>/` with `latency_samples.jsonl`, `timing.json`, `metadata.json`.
2. [`collect_boki_results.py`](collect_boki_results.py) → `collected_metrics.json`.
3. [`boki_to_common_schema.py`](boki_to_common_schema.py) → common JSONL/CSV.

**Canonical definitions:** [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md) and [`../common_schema/fields.py`](../common_schema/fields.py).

Boki-specific notes:

- Default `system_variant` in metadata: `boki-native` (override with `SYSTEM_VARIANT` env in `run_boki_bench.sh`).
- Point `BOKI_HTTP_URL` at a real gateway route; defaults use `GET`—switch to `POST` + body if your API requires it.
- For non-HTTP Boki benchmarks, emit the same `collected_metrics.json` shape or extend collectors later.
