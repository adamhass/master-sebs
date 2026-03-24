Shared Python package:

- `fields.py` — `COMMON_FIELDS`
- `io.py` — JSONL/CSV writers
- `latency_stats.py` — aggregate latency samples (seconds) into metric blocks
- `collect_http_run.py` — build `collected_metrics.json` from `http_latency_bench.py` run dirs
- `http_latency_bench.py` — CLI: repeated HTTP requests → `latency_samples.jsonl` + `timing.json`

Spec: [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md).
