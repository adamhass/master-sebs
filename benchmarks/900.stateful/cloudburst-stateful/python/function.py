import hashlib
import time


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return str(value).encode("utf-8")


def handler(event):
    """Synthetic compute; same shape as other 900.stateful placeholders (not native Cloudburst IPC)."""
    begin = time.perf_counter_ns()

    payload = event.get("payload", "")
    payload_hash = hashlib.sha256(_to_bytes(payload)).hexdigest()
    ops = max(1, int(event.get("ops", 1)))
    state_size_kb = max(0, int(event.get("state_size_kb", 0)))

    acc = 0
    for idx in range(min(ops * 64, 20000)):
        acc = (acc + idx + state_size_kb + len(payload_hash)) % 1000003

    duration_us = int((time.perf_counter_ns() - begin) / 1000)

    return {
        "result": {
            "ok": True,
            "system": event.get("system", "unknown"),
            "workload": event.get("workload", "default"),
            "payload_sha256": payload_hash,
            "accumulator": acc,
        },
        "measurement": {
            "compute_time": duration_us,
            "workload_ops": ops,
            "state_size_kb": state_size_kb,
        },
    }
