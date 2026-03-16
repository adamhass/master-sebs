BENCHMARK_NAME = 'baseline-lambda-dynamodb'
BENCHMARK_DESCRIPTION = 'Standard stateless Lambda with DynamoDB state backend'
PARAMETERS = {'consistency_model': 'strong',
 'primary_key': 'session_id',
 'read_capacity': 1000,
 'table_name': 'sebs-benchmark-state',
 'write_capacity': 1000}
EXPERIMENT = {'concurrency': [1, 10, 50, 100, 500],
 'iterations': 20,
 'payload_size': '1kb',
 'workload': 'read-modify-write'}
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
