"""
Canonical metric columns for integrations/*_to_common_schema.py adapters.

Keep in sync with integrations/COMMON_SCHEMA.md.
"""

COMMON_FIELDS = [
    "system",
    "system_variant",
    "consistency_model",
    "deployment_mode",
    "benchmark_name",
    "metric_scope",
    "num_requests",
    "sample_size",
    "throughput_ops_per_sec",
    "latency_mean_ms",
    "latency_p50_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "latency_min_ms",
    "latency_max_ms",
    "total_computation_time_sec",
    "cost_per_million_ops_usd",
    "throughput_per_resource_unit",
    "resource_cpu_avg",
    "resource_memory_avg_mb",
    "state_size_kb",
    "state_placement",
    "convergence_time_ms",
    "source_file",
]
