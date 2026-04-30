#!/usr/bin/env python3
"""Stateful benchmark logic for the Knative + Redis variants."""

import os
import time
import uuid

import redis

_pool = None
_is_cold = True


def _get_pool():
    global _pool
    if _pool is None:
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        _pool = redis.ConnectionPool(
            host=host,
            port=port,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _pool


def handler(event):
    global _is_cold

    request_id = event.get("request_id", uuid.uuid4().hex)
    begin = time.time()

    state_size_kb = max(1, int(event.get("state_size_kb", 1)))
    state_key = event.get("state_key", "bench:state")
    ops = max(1, int(event.get("ops", 1)))

    client = redis.Redis(connection_pool=_get_pool())
    state_blob = os.urandom(state_size_kb * 1024)

    t0 = time.time()
    client.set(state_key, state_blob)
    state_write_lat_us = int((time.time() - t0) * 1_000_000)

    t1 = time.time()
    _ = client.get(state_key)
    state_read_lat_us = int((time.time() - t1) * 1_000_000)

    t2 = time.time()
    acc = 0
    for idx in range(min(ops * 64, 20000)):
        acc = (acc + idx + state_size_kb) % 1000003
    compute_time_us = int((time.time() - t2) * 1_000_000)

    end = time.time()

    cold = _is_cold
    _is_cold = False

    return {
        "request_id": request_id,
        "is_cold": cold,
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
