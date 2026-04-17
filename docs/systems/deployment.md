# Deployment Models

How each system is deployed, what infrastructure is required, and operational complexity.

## Summary

| System | Compute | State Store | Infra Components | Terraform Resources | Deploy Complexity |
|--------|---------|-------------|:----------------:|:-------------------:|:-----------------:|
| Lambda + Redis | Managed (Lambda) | Managed (ElastiCache) | 2 | ~15 | Low |
| Lambda Durable | Managed (Lambda) | Managed (DynamoDB) | 2 | ~10 | Low |
| Boki | Self-hosted (EC2) | Self-hosted (shared log) | 7+ containers | ~12 | High |
| Cloudburst + Anna | Self-hosted (EC2) | Self-hosted (Anna KVS) | 4+ nodes | ~15 | High |
| Restate | Hybrid (EC2 + Lambda) | Self-hosted (embedded KV) | 2 | ~20 | Medium |

## Lambda + Redis

```
Terraform → VPC + Lambda + API Gateway + ElastiCache Redis
```

Fully managed. No EC2, no Docker, no manual lifecycle. Deploy = `terraform apply`. Scale = automatic (Lambda concurrency + Redis node type). VPC required for Lambda↔Redis private access.

**Operational burden**: Minimal. Monitor Redis memory (allkeys-lru). Increase Lambda concurrency limit if needed.

## Lambda Durable

```
Terraform → Lambda (durable_config) + API Gateway + DynamoDB
```

Fully serverless. No VPC needed — DynamoDB accessed via public endpoint. Simpler than baseline (no Redis to manage). Deploy = `terraform apply`. Scale = automatic (Lambda + DynamoDB on-demand).

**Operational burden**: Minimal. Monitor DynamoDB throttling (unlikely with on-demand). Published Lambda version/alias required for durable invocation. AWS provider >= 6.25 needed for `durable_config`.

**Limitation**: DynamoDB 400KB item size limit constrains large state objects.

## Boki

```
Terraform → VPC + Infra EC2 (7 Docker containers) + Engine ASG + Client EC2
```

Most complex deployment. Infra node runs: ZooKeeper, Controller, 2x Sequencer, Storage, Gateway — all via docker-compose with host networking. Engines run engine+worker containers with tmpfs IPC volume. Benchmark binary compiled separately (`CGO_ENABLED=0`).

**Lifecycle issues**:
- ZK discovery one-shot: `cmd/start` must be issued after all engines register. Missed = gateway can't find engines.
- Engine restart: engines re-register with ZK but gateway doesn't re-discover. Recovery = full destroy+apply.
- Binary deployment: SCP static Go binary to engine nodes. No package manager, no S3 auto-download (manual).

**Operational burden**: High. Multi-step coordinated startup (infra → engines → ZK start → binary deploy). Any component restart risks ZK state inconsistency. Auto-scaling non-functional (L7).

## Cloudburst + Anna

```
Terraform → VPC + Scheduler EC2 + Executor ASG + Anna EC2 + Client EC2
```

4 distinct node roles, each built from source. Scheduler manages function dispatch via ZMQ. Executors run Python functions with injected user_library. Anna KVS runs in Docker with custom config.

**Lifecycle issues**:
- Function pinning per-executor: functions registered on specific executors, lost on termination (L10).
- Anna routing: requires `threads.routing: 4` for remote mode. Wrong config = `NO_SERVERS` crash.
- HTTP gateway: extra process on client node bridging HTTP→ZMQ. Must be running before benchmarks.

**Operational burden**: High. Build from source (both repos). Patch scheduler/executor for remote Anna (`local=False`). Manual function re-registration after executor restarts. Auto-scaling breaks function dispatch.

## Restate

```
Terraform → VPC + 3x Restate Server EC2 (Docker cluster) + Standalone handler (node 0) + Client EC2
```

Self-hosted model. 3-node Restate cluster with replication factor 2. Each node = Docker container with `--network host` (ports 8080 ingress, 9070 admin, 5122 fabric). Nodes use fixed private IPs (10.70.1.10-12) for deterministic cluster discovery. Handler = standalone Python HTTP server (Hypercorn ASGI on port 9080) co-located on node 0 — same model as Boki engines and Cloudburst executors. State replicated across cluster via Bifrost journal.

**Deployment steps**:
1. `terraform apply` creates 3 server EC2s + client
2. Each server user_data: installs Docker + Python, writes `restate.toml`, pulls Docker image, starts Restate
3. Node 0: auto-provisions cluster, installs `restate_sdk[serde]` + `hypercorn`, starts handler, registers HTTP endpoint
4. Nodes 1+2: join cluster via node 0's fabric address (5122)
5. Cluster formation: ~60s. Raft consensus for metadata, quorum writes for journal.

**Operational burden**: Medium. Single binary per node (no ZK, no multi-container coordination). 3-node cluster with automatic Raft-based metadata replication. Handler is a simple Python process (no Lambda, no IAM chains). Fixed-IP cluster discovery. Tolerates 1 node failure. Adding nodes requires config change + new EC2 (not dynamic).

## Elasticity Spectrum

```
Fully managed          Light engineering         Engineering obligation
(platform property)    (self-hosted, simple)     (multi-component, fragile)
       |                      |                           |
  Lambda Baseline       Restate                    Boki / Cloudburst
  Lambda Durable        (single binary,            (ZK lifecycle, multi-node,
  (auto-scale,           manual scaling)            coordinated restart,
   zero ops)                                        build from source)
```

Core thesis finding: elasticity as platform property (Lambda) vs engineering obligation (Boki/Cloudburst). Restate sits in between — simpler than research systems, not as managed as Lambda.
