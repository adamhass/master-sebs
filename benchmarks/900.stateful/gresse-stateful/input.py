BENCHMARK_NAME = "gresse-stateful"
BENCHMARK_DESCRIPTION = (
    "Native Gresse stateful benchmark using a replicated CRDT runtime "
    "(HTTP mutation request with local state read/write + compute)"
)
PARAMETERS = {
    "http_endpoint": "http://127.0.0.1:9090",
    "consistency_model": "eventual",
    "state_backend": "gresse-crdt",
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
    size_map = {"test": 1, "small": 64, "large": 512}
    state_size_kb = size_map.get(size, 64)

    return {
        "type": "Mutation",
        "params": {
            "Run": {
                "state_size_kb": state_size_kb,
                "state_key": "bench:state",
                "ops": 1,
            }
        },
    }
