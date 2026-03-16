BENCHMARK_NAME = 'boki-shared-log'
BENCHMARK_DESCRIPTION = 'Shared-log stateful runtime using LogBook API'
PARAMETERS = {'batch_append_size': 10,
 'logbook_id': 'test-app-log-001',
 'num_physical_logs': 4,
 'read_guarantee': 'monotonic-read',
 'replication_factor': 3,
 'sequencer_endpoint': '10.0.0.5:50051'}
EXPERIMENT = {'burn_in_period_s': 10, 'concurrency': [10, 100], 'iterations': 5}
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
