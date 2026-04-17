# Restate (Durable Execution Runtime)

## Architecture

```
Client → Restate Cluster (3x EC2 :8080) → Handler (EC2 :9080) ←→ Restate Cluster (replicated journal)
```

Production system. Rust binary manages durable execution + embedded KV state. Deployed as **3-node cluster** with replication factor 2 (quorum-replicated journal via Bifrost log). Handler runs as **standalone HTTP server** (Hypercorn ASGI) co-located on node 0 — same deployment model as Boki engines and Cloudburst executors. Restate proxies requests to handler, manages state journal transparently. Virtual Objects provide per-key state with exclusive access.

## Implementation

**Terraform** (`integrations/restate/aws/`): VPC (10.70.0.0/16). 3x Restate server EC2 (t3.medium, Ubuntu 22.04) with fixed private IPs (10.70.1.10-12), running Docker image `restatedev/restate` with `--network host`. TOML config per node: `cluster-name`, `node-name`, `default-replication = 2`, roles `[worker, log-server, metadata-server, admin, http-ingress]`. Node 0 auto-provisions cluster + deploys handler; nodes 1+2 join via `metadata-client.addresses`. Client EC2 (t3.small, Ubuntu 22.04).

**Standalone handler** (`handler/handler.py`): Restate Virtual Object `statefulBench` served via Hypercorn on port 9080. Uses `ctx.set("state_blob", blob)` / `await ctx.get("state_blob")` for state. State blob base64-encoded (Restate JSON serde can't handle raw bytes). Handler registered with Restate as HTTP endpoint using **private IP**: `POST /deployments {"uri": "http://10.70.1.10:9080"}`. Must use private IP (not localhost) so all 3 nodes can reach the handler.

**State mechanism**: Restate embedded KV. Write = journal append (`ctx.set()`). Read = journal lookup (`await ctx.get()`). Journal quorum-replicated across 2+ nodes via Bifrost log before ack. State persisted per Virtual Object key, retained indefinitely.

**Invocation**: `POST http://<server>:8080/statefulBench/{unique-key}/run` — unique key per invocation avoids exclusive handler lock serialization.

## Design Decisions

- **Standalone over Lambda-backed**: Restate docs show handlers as HTTP servers as the idiomatic deployment. Lambda-backed adds ~80ms dispatch overhead that Boki/Cloudburst don't have (they also use persistent handlers). Standalone = fair apples-to-apples comparison.
- **3-node cluster**: Mirrors Boki (infra + 2 engines) and Cloudburst (scheduler + 2 executors + Anna). Replication factor 2 = quorum writes, tolerates 1 node failure.
- **Handler co-located on node 0**: Like Boki engine on infra node. Minimizes network hop between Restate server and handler.
- **Ubuntu 22.04 over AL2023**: pycurl on AL2023 hangs against Restate's HTTP/2 ingress. Ubuntu's libcurl handles negotiation correctly.
- **Handler registered via private IP** (not localhost): Multi-node cluster routes requests across nodes. Only node 0 runs the handler — other nodes must reach it via `10.70.1.10:9080`.
- Unique keys per invocation: Virtual Object exclusive handlers serialize same-key requests. Unique keys = full parallelism.
- base64 encoding: Restate SDK JSON serializer can't handle raw `bytes`. Encode before `ctx.set()`.

## Findings (Standalone, 3-node cluster)

**Client latency P50 = 90.8ms** (cloud, c=10, 64KB):
- Network RTT: 0.3ms (in-VPC, private IP)
- Function execution: 5.2ms (state ops + compute)
- **Serverless overhead: 85.3ms** (Restate dispatch: partition routing, quorum journal, HTTP proxy to handler)

**Throughput scaling** (cloud):
| c=1 | c=10 | c=50 | c=100 |
|:---:|:----:|:----:|:-----:|
| 29.4 | 84.9 | 154.7 | 171.6 inv/s |

**State operations** (P50):
- Write (`ctx.set()`): 488us — quorum journal append to 2+ nodes
- Read (`await ctx.get()`): 4,171us — journal lookup via async SDK. Includes Restate internal processing + event loop scheduling. NOT a pure memory read despite being "embedded KV."

**Read latency is higher than expected** — 4ms for an "embedded" store. The `await ctx.get()` path goes: Python async call → Restate SDK protocol → Restate server journal lookup → response back to SDK → Python resume. The async boundary + Restate protocol overhead dominates. Compare: Boki read = 2us (direct engine cache, no async boundary).

**85ms dispatch overhead** — comparable to Cloudburst (82ms scheduler dispatch). Restate's overhead comes from: HTTP ingress parsing → partition leader lookup → route to correct node → invoke handler via HTTP → quorum journal ops → return. Same multi-hop dispatch pattern as Cloudburst's ZMQ→scheduler→executor chain.

**Edge = Cloud results**: Standalone handler only reachable via private IP (no public ingress). Both edge and cloud benchmarks run from within VPC. Results are identical — this is a measurement limitation, not an error.

## Limitations Found

- **No cold start**: Restate server + handler both persistent. No per-invocation container provisioning.
- **Virtual Object key contention**: Same-key invocations serialize (exclusive handler). Thesis uses unique keys for fair parallel comparison.
- **base64 overhead**: JSON serde forces base64 for binary state. ~33% size overhead. Custom binary serde would eliminate this.
- **Read latency higher than expected**: `await ctx.get()` = 4ms P50 despite embedded KV. Async SDK protocol overhead, not storage latency.
- **SDK maturity**: Python SDK newer than TypeScript/Java. Async-only API. `time.time()` around await includes event loop scheduling.
- **No scale-to-zero**: Persistent handler process, like Boki/Cloudburst. Trade-off: no cold starts but always-on infrastructure cost.
- **pycurl/AL2023 incompatibility**: pycurl with nghttp2 on AL2023 hangs against Restate's HTTP ingress. Required Ubuntu 22.04 for reliable measurements.

## Thesis Framing

Standalone deployment makes Restate directly comparable to Boki and Cloudburst — all three are self-hosted systems with persistent handler processes. The key finding: Restate's 85ms dispatch overhead is comparable to Cloudburst's 82ms despite fundamentally different architectures (Rust binary with replicated journal vs Python scheduler with ZMQ dispatch). Boki's 4ms overhead remains the outlier due to its direct gateway→engine path with no partition routing.

State access latency is NOT the differentiator between these systems — all achieve sub-10ms state ops. The dispatch layer architecture is what determines end-to-end performance.
