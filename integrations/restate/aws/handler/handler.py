"""
Restate Virtual Object handler — standalone HTTP server.

Runs as ASGI app via Hypercorn on port 9080. Restate server calls this
endpoint for handler execution. State managed by Restate's embedded KV.

Invocation flow:
  Client -> Restate Server (EC2 :8080) -> This handler (EC2 :9080) <-> Restate (state journal)
"""

import base64
import os
import time
import uuid

import restate
from restate import VirtualObject, ObjectContext

bench = VirtualObject("statefulBench")


@bench.handler()
async def run(ctx: ObjectContext, request: dict) -> dict:
    request_id = request.get("request_id", uuid.uuid4().hex)
    state_size_kb = max(1, int(request.get("state_size_kb", 1)))
    ops = max(1, int(request.get("ops", 1)))

    begin = time.time()
    state_blob = base64.b64encode(os.urandom(state_size_kb * 1024)).decode()

    # State write — journaled to Restate's replicated log
    t0 = time.time()
    ctx.set("state_blob", state_blob)
    state_write_lat_us = int((time.time() - t0) * 1_000_000)

    # State read — from Restate's embedded KV
    t1 = time.time()
    _ = await ctx.get("state_blob")
    state_read_lat_us = int((time.time() - t1) * 1_000_000)

    # Lightweight compute (same as all other systems)
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


app = restate.app(services=[bench])

if __name__ == "__main__":
    import asyncio
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:9080"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
