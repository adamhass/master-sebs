"""
Native Cloudburst stateful benchmark function.

Signature follows Cloudburst executor convention:
    def func(cloudburst, *args) -> result

The first argument is always the user_library object injected by the
executor.  State operations use cloudburst.put() / cloudburst.get()
which go through Anna KVS (with optional local executor cache).

This file is imported by the benchmark runner module
(master-cloudburst/cloudburst/server/benchmarks/stateful.py) and also
serves as the SeBS benchmark source of truth for the cloudburst-stateful
track.
"""

import os
import time
import uuid


def stateful_benchmark(cloudburst, state_key, state_size_kb, ops, request_id=None):
    """
    Single-invocation stateful benchmark.

    Args:
        cloudburst:     Cloudburst user_library (put/get/getid/send/recv).
        state_key:      KVS key to read/write.
        state_size_kb:  Size of the state blob in KB.
        ops:            Number of compute loop iterations (lightweight).
        request_id:     Optional; generated if not provided.

    Returns:
        dict with SeBS-compatible fields + measurement block.
    """
    if request_id is None:
        request_id = uuid.uuid4().hex

    begin = time.time()
    state_size_kb = max(1, int(state_size_kb))
    ops = max(1, int(ops))
    state_blob = os.urandom(state_size_kb * 1024)

    # --- State write (Anna KVS via executor) ---
    t0 = time.time()
    cloudburst.put(state_key, state_blob)
    state_write_lat_us = int((time.time() - t0) * 1_000_000)

    # --- State read ---
    t1 = time.time()
    _ = cloudburst.get(state_key)
    state_read_lat_us = int((time.time() - t1) * 1_000_000)

    # --- Lightweight compute ---
    t2 = time.time()
    acc = 0
    for idx in range(min(ops * 64, 20000)):
        acc = (acc + idx + state_size_kb) % 1000003
    compute_time_us = int((time.time() - t2) * 1_000_000)

    end = time.time()

    return {
        "request_id": request_id,
        "is_cold": False,
        "begin": begin,
        "end": end,
        "measurement": {
            "compute_time_us": compute_time_us,
            "state_read_lat_us": state_read_lat_us,
            "state_write_lat_us": state_write_lat_us,
            "state_size_kb": state_size_kb,
            "state_ops": ops,
            "accumulator": acc,
        },
    }
