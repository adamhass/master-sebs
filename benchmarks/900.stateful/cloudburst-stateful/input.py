BENCHMARK_NAME = 'cloudburst-stateful'
BENCHMARK_DESCRIPTION = (
    'SeBS Lambda benchmark profile aligned with Cloudburst-style stateful serverless '
    '(payload encodes scheduler / Anna-style metadata; native Cloudburst runs via integrations/cloudburst/)'
)
PARAMETERS = {
    'scheduler_endpoint': '127.0.0.1:8080',
    'anna_endpoint': '127.0.0.1:6450',
    'consistency_model': 'normal',
    'state_backend': 'anna-kvs',
    'client_mode': 'cloudburst-client',
    'composition_mode': 'single-function',
    'state_size_kb': 0,
}
EXPERIMENT = {
    'burn_in_period_s': 10,
    'concurrency': [1, 10, 50, 100],
    'iterations': 10,
    'workload': 'mixed',
    'payload_size': '1kb',
}
PAYLOAD_SIZE_BYTES = 1024


def generate_input(data_dir, size, benchmarks_bucket, input_buckets, output_buckets, upload_func, nosql_func):
    scale = {"test": 1, "small": 4, "large": 16}.get(size, 1)
    payload_len = min(PAYLOAD_SIZE_BYTES * scale, 64 * 1024)
    payload = "x" * payload_len

    return {
        "system": BENCHMARK_NAME,
        "description": BENCHMARK_DESCRIPTION,
        "parameters": PARAMETERS,
        "workload": EXPERIMENT.get("workload", "default"),
        "state_size_kb": PARAMETERS.get("state_size_kb", 0),
        "ops": max(1, scale),
        "payload": payload,
    }
