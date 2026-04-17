# Cloudburst + Anna KVS

## Architecture

```
Client → HTTP Gateway (:8088) → Scheduler (ZMQ) → Executor(s) → Anna KVS
```

Research system (VLDB '20). Scheduler-based dispatch with distributed KV store (Anna). HTTP gateway bridges HTTP to ZMQ protocol. Executors run Python functions with injected `user_library` for state access.

## Implementation

**Terraform** (`integrations/cloudburst/aws/`): VPC (10.30.0.0/16). Scheduler EC2 (t3.medium), executor ASG (t3.medium, desired=2), Anna KVS EC2 (t3.medium), client EC2 (t3.small). All Amazon Linux 2023. Built from source (`master-cloudburst/`, `master-anna/` repos).

**HTTP gateway** (`scripts/cloudburst_http_gateway.py`): ThreadingHTTPServer + pool of 10 CloudburstConnection instances (each unique ZMQ tid). Translates HTTP POST → ZMQ → scheduler → executor → response. Function registration via dedicated connection (tid=99).

**Benchmark function** (`benchmarks/900.stateful/cloudburst-stateful/python/function.py`): Uses `cloudburst.put(key, blob)` / `cloudburst.get(key)` — Anna KVS operations via executor's injected user_library.

**SeBS provider** (`sebs/cloudburst_provider/`): LibraryTrigger wraps CloudburstConnection (ZMQ). Reports trigger type as HTTP for compatibility.

**State mechanism**: Anna KVS PUT/GET. Distributed KV with tunable consistency. Remote routing mode (`local=False`) for EC2 deployment. State shared across executors via Anna.

**Invocation**: `POST http://<client-ip>:8088/call/statefulBench` (HTTP gateway on client node)

## Design Decisions

- Anna routing fix: `threads.routing: 4` (binds ports 6450-6453) — client in `local=False` mode expects 4 routing ports
- Scheduler/executor patched: `anna_local = anna_addr == '127.0.0.1'` for remote Anna detection
- ThreadingHTTPServer: fixed single-threaded bottleneck (L9). c=50 improved 6.7→38.9 inv/s
- Function registration via gateway inline definition (not file upload)

## Limitations Found

- **L8 — HTTP gateway hop**: Extra translation layer (HTTP→ZMQ) adds ~2-5ms per request. Other systems are HTTP-native.
- **L9 — Concurrency bottleneck (resolved)**: Original HTTPServer serialized requests. Fixed with ThreadingHTTPServer + connection pool.
- **L10 — Function lifecycle**: Function pinning per-executor, lost on termination. Manual re-registration required.
- **L11 — Anna elasticity disabled**: Multi-node Anna requires manual hash ring configuration. Auto-scaling not functional.
- **L12 — State placement no benefit**: Same-key vs unique-key showed no performance difference — Anna routing overhead dominates.
- **Scheduler bottleneck**: 82ms serverless overhead at c=10 (cloud). ZMQ → scheduler → executor chain is longest dispatch path of all systems.
