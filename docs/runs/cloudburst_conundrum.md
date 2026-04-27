# Cloudburst Edge Latency: The Result-via-KVS Polling Tax

## Problem

Cloudburst edge (laptop → AWS) shows 691.9ms P50 client latency with **656ms serverless overhead** — 12x worse than Lambda (25.5ms overhead) and 18x worse than Boki (35.1ms overhead). From cloud (EC2 in-VPC), overhead drops to 85ms. What accounts for the 7.6x edge-to-cloud gap?

## Root Cause: `CloudburstFuture.get()` Busy-Polls Anna Over WAN

Cloudburst uses a **result-via-KVS** pattern. Executors don't return results directly — they write results to Anna KVS, and the caller polls Anna until the result appears.

`cloudburst/shared/future.py:22-28`:

```python
def get(self):
    obj = self.kvs_client.get(self.obj_id)[self.obj_id]
    while obj is None:
        obj = self.kvs_client.get(self.obj_id)[self.obj_id]
    return self.serializer.load_lattice(obj)
```

Tight busy-loop. No sleep. No backoff. No push notification. Each iteration = full Anna KVS GET round-trip over ZMQ TCP.

## Three Compounding Design Choices

### 1. Result-via-KVS (no direct response channel)

All other systems return results synchronously over the same connection:

| System | Result delivery | Poll overhead |
|--------|----------------|---------------|
| Lambda | HTTP response via API Gateway | 0 (synchronous) |
| Boki | HTTP response via gateway | 0 (synchronous) |
| Restate | HTTP response via server | 0 (synchronous) |
| **Cloudburst** | **Executor → Anna KVS → client polls** | **N x RTT** |

Executor writes result to Anna under a UUID key. Client enters `fut.get()` loop polling that key. Every invocation pays this poll tax.

### 2. No address cache hits on result keys

Result keys are UUIDs — unique per invocation. `AnnaTcpClient.address_cache` (per-connection instance) never hits for result retrieval. Every `fut.get()` call starts with `_query_routing()` — a ZMQ round-trip to Anna's ELB routing tier to discover which worker holds the key.

From EC2: routing query = ~1ms. From laptop: routing query = **~60ms**.

### 3. No receive timeout on poll socket

`AnnaTcpClient.response_puller` has no `RCVTIMEO` set. Each poll blocks in raw `recv()` until Anna responds. No way to short-circuit a miss — client waits full RTT before learning result isn't ready.

## Overhead Breakdown (Edge, P50)

| Phase | Latency | Source |
|-------|---------|--------|
| HTTP body transfer (not in PRETRANSFER_TIME) | ~30ms | WAN data transfer, excluded from RTT metric |
| Gateway → ZMQ → Scheduler | ~1ms | Localhost, fire-and-forget PUSH |
| Scheduler `poll(timeout=1000ms)` wakeup | 0-5ms | Wakes on message; up to 1s if idle |
| Scheduler DAG resolve + executor dispatch | ~1ms | Synchronous, no blocking I/O |
| Executor `poll(timeout=1000ms)` wakeup | 0-5ms | Same pattern as scheduler |
| *Function execution (excluded from overhead)* | *6.1ms* | *State write + read + compute* |
| Executor writes result to Anna (IPC) | ~1ms | Local Unix socket, fast |
| **Anna routing query for UUID result key** | **~60ms** | **`_query_routing()` over WAN, always cache miss** |
| **2-5 poll misses in `fut.get()` loop** | **120-300ms** | **Each miss = full WAN round-trip (~60ms)** |
| **Final successful poll** | **~60ms** | **GET that finds the key** |
| HTTP response transfer | ~30ms | WAN data transfer |
| **Total overhead** | **~300-500ms** | **Polling dominates** |

Measured P50 overhead: 656ms. Upper range of estimate — consistent with 4-5 poll misses + routing.

## Why Cloud Fixes It

From EC2 in same VPC, each Anna round-trip = ~1-2ms instead of ~60ms:

- Routing query: 1ms (not 60ms)
- 5 poll misses: 5-10ms (not 300ms)
- Final poll: 1ms (not 60ms)
- Total poll overhead: ~10-15ms

Measured cloud overhead: 85ms. Remaining ~70ms = ZMQ dispatch chain + HTTP processing — the true architectural cost.

## Architectural Significance

Cloudburst was designed for **co-located deployment** (Berkeley RISE Lab). The paper assumes clients, schedulers, executors, and Anna nodes share a datacenter. The result-via-KVS pattern has negligible overhead when Anna round-trips are sub-millisecond.

This design becomes a **multiplicative penalty** when any component crosses a network boundary:

```
overhead ∝ N_polls × RTT_to_Anna
```

Lambda, Boki, and Restate all use synchronous response channels — their overhead is additive (fixed dispatch cost), not multiplicative (proportional to network distance).

This explains the edge-to-cloud improvement ratios:

| System | Edge → Cloud | Pattern |
|--------|-------------|---------|
| Lambda | 2.0x | Additive: TLS halves in-region |
| Boki | 5.0x | Additive: private IP eliminates internet RTT |
| **Cloudburst** | **7.6x** | **Multiplicative: N polls × RTT eliminated** |
| Restate | 1.0x | Additive: already low, embedded state |

## Code References

| File | Line | What |
|------|------|------|
| `cloudburst/shared/future.py` | 22-28 | Busy-poll loop (no sleep) |
| `cloudburst/client/client.py` | 265 | `call_dag()` returns `CloudburstFuture` |
| `anna/client/python/anna/client.py` | 267-291 | `_query_routing()` (cache miss on UUID keys) |
| `anna/client/python/anna/client.py` | 79-116 | `response_puller.recv()` (no RCVTIMEO) |
| `cloudburst/server/scheduler/server.py` | 168 | `poll(timeout=1000ms)` |
| `cloudburst/server/executor/server.py` | 180 | `poll(timeout=1000ms)` |

## Provenance

The busy-poll pattern in `future.py` is **original upstream code** from the hydro-project/cloudburst repository. It was introduced in the initial commit (`cc90b9d`, 2019-08-07) as `DropletFuture.get()` by UC Berkeley RISE Lab, and renamed to `CloudburstFuture` in `c9bbebf` (2020-01-28, PR #21) with identical `get()` logic. No modifications were made to `future.py`, `client.py`, or the scheduler/executor dispatch code in this research fork — the 4 thesis-specific commits (`7802794`, `67f0e06`, `19c7e56`, `09fff07`) only added Anna connection mode configuration and the benchmark function. The HTTP gateway (`cloudburst_http_gateway.py`) calls `call_dag()` + `fut.get()` — the same API any Cloudburst client uses.

## Missing anna-cache Layer

The Cloudburst paper (VLDB '20) describes a co-located **anna-cache** sidecar on each executor VM that absorbs state writes via local IPC (`ipc:///` Unix domain sockets) and propagates them asynchronously to the remote Anna memory tier. This evaluation omits the anna-cache layer — executors access a single Anna node directly via `AnnaTcpClient` (TCP).

With anna-cache present, the `fut.get()` polling loop would hit a local IPC socket (~microseconds per poll) instead of a remote TCP socket (~1-2ms in-VPC, ~60ms over WAN). The polling overhead that dominates the edge latency would be negligible.

This is documented as LIMITATIONS.md L13. The measured Cloudburst latencies represent the worst-case direct-to-KVS path. anna-cache (`hydro-project/anna-cache`) is a separate C++ component requiring its own build pipeline and Kubernetes pod co-location — deploying it on EC2 was out of scope.

## Implications for Thesis

1. **Edge latency is not a useful metric for Cloudburst** — it measures WAN polling overhead, not system performance. Cloud (EC2) results represent true system characteristics.
2. **The 85ms cloud overhead is the defensible number** — this is the real cost of Cloudburst's ZMQ dispatch chain + result-via-KVS with sub-ms Anna RTTs.
3. **Cloudburst's architecture assumes datacenter locality** — a valid design for its intended use case (autoscaling prediction serving) but a structural disadvantage when compared against systems with synchronous response paths.
4. **The missing anna-cache layer inflates both dispatch overhead and write P95** — documented in LIMITATIONS.md L13. With the paper's full stack, writes are absorbed locally and result polling uses IPC. Without it, all state access is synchronous TCP to a single remote KVS node.
