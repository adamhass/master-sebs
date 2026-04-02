import uuid

SIZE_TIERS = {"test": 1, "small": 64, "large": 512}


def generate_input(data_dir, size, benchmarks_bucket, input_buckets, output_buckets, upload_func, nosql_func):
    state_size_kb = SIZE_TIERS.get(size, 1)
    return {
        "state_key": f"bench:{uuid.uuid4().hex[:8]}",
        "state_size_kb": state_size_kb,
        "ops": 1,
        "request_id": uuid.uuid4().hex,
    }
