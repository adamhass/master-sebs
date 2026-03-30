BENCHMARK_NAME = "baseline-lambda-redis"
BENCHMARK_DESCRIPTION = "Lambda with ElastiCache Redis stateful benchmark"
# endpoint is within VPC, therefore it's safe to expose
PARAMETERS = {
    "cluster_mode": "disabled",
    "connection_pooling": True,
    "redis_endpoint": "master-sebs-baseline-redis.fax5sd.ng.0001.eun1.cache.amazonaws.com",
    "redis_port": 6379,
    "state_size_kb": 64,
}
EXPERIMENT = {
    "concurrency": [1, 10, 50, 100],
    "iterations": 200,
    "warmup_invocations": 10,
}
PAYLOAD_SIZE_BYTES = 1024


def generate_input(
    data_dir,
    size,
    benchmarks_bucket,
    input_buckets,
    output_buckets,
    upload_func,
    nosql_func,
):
    size_map = {"test": 1, "small": 64, "large": 512}
    state_size_kb = size_map.get(size, 64)

    return {
        "state_size_kb": state_size_kb,
        "state_key": "bench:state",
        "ops": 1,
    }
