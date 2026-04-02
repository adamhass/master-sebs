BENCHMARK_NAME = "cloudburst-stateful"
BENCHMARK_DESCRIPTION = (
    "Native Cloudburst stateful benchmark using Anna KVS "
    "(put/get via executor user_library)"
)
PARAMETERS = {
    "scheduler_endpoint": "13.48.105.254",
    "anna_endpoint": "10.30.1.54",
    "consistency_model": "normal",
    "state_backend": "anna-kvs",
    "state_size_kb": 64,
}
EXPERIMENT = {
    "concurrency": [1, 10, 50, 100],
    "iterations": 200,
    "warmup_invocations": 1,
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
    import uuid

    size_map = {"test": 1, "small": 64, "large": 512}
    state_size_kb = size_map.get(size, 64)

    return {
        "state_size_kb": state_size_kb,
        "state_key": "bench:state",
        "ops": 1,
        "request_id": uuid.uuid4().hex,
    }
