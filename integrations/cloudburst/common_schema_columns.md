# Common schema columns (Cloudburst)

Cloudburst runs use [`cloudburst_to_common_schema.py`](cloudburst_to_common_schema.py), which maps `collected_metrics.json` (from [`collect_cloudburst_results.py`](collect_cloudburst_results.py)) into the shared column set.

**Canonical definitions:** [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md) and [`../common_schema/fields.py`](../common_schema/fields.py).

Cloudburst-specific notes:

- `system` comes from the collected payload (default `cloudburst`).
- `metric_scope` is each parsed latency block identifier from Cloudburst logs.
- Latency fields are converted from **seconds** in the raw metrics to **milliseconds** in the common schema.
