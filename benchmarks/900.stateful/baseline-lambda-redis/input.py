BENCHMARK_NAME = 'baseline-lambda-redis'
BENCHMARK_DESCRIPTION = 'High-performance Lambda with ElastiCache Redis backend'
PARAMETERS = {'cluster_mode': 'disabled',
 'connection_pooling': True,
 'redis_endpoint': 'sebs-cache.xxxxxx.0001.use1.cache.amazonaws.com',
 'redis_port': 6379}
EXPERIMENT = {'concurrency': [1, 10, 50, 100, 500], 'iterations': 20, 'warmup_invocations': 50}
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
