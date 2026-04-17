# Boki (Shared Log FaaS)

## Architecture

```
Client → Gateway (HTTP :8080) → Engine containers → Shared Log (Sequencer + Storage)
                                      ↕
                              ZooKeeper (discovery)
```

Research system (SOSP '21). Shared log architecture where all state mutations append to durable log. Engine containers cache log entries locally for fast reads. Gateway dispatches HTTP requests to engines via ZooKeeper-based discovery.

## Implementation

**Terraform** (`integrations/boki/aws/EC2/`): VPC (10.41.0.0/16). Infra node (c5.2xlarge) runs 7 Docker containers via docker-compose: ZooKeeper, Controller, 2x Sequencer, Storage, Gateway. Engine ASG (c5.xlarge, desired=2, max=4) runs engine+worker containers. Optional client EC2 (t3.small). All containers use host networking for cross-machine communication.

**Benchmark function**: Go binary in `master-boki/benchmarks/stateful/` (separate repo). Compiled with `CGO_ENABLED=0` for static linking (container uses GLIBC 2.31). Registered with Boki Launcher. Python stub in SeBS is dead code — real logic lives in Go.

**SeBS provider** (`sebs/boki/`): HTTPTrigger POSTs to `http://<gateway>:8080/function/statefulBench`. Skips code packaging (pre-deployed system).

**State mechanism**: Shared log append (write) + engine-local cache (read). Write = log append to sequencer → replicated to storage. Read = engine cache lookup (~2us). State shared via log — any engine can read any key.

**Invocation**: `POST http://<infra-public-ip>:8080/function/statefulBench`

## Design Decisions

- Docker images from original SOSP artifact (`zjia/boki:sosp-ae`)
- Ubuntu 20.04 AMI (io_uring support, matches container base)
- Static Go binary to avoid GLIBC mismatch
- Host networking for Docker — required for cross-EC2 engine communication
- ZK-based engine discovery: `cmd/start` issued after all engines register

## Limitations Found

- **L6 — Engine-cached reads**: 2us read latency = local memory, not network. Not comparable to Redis/DynamoDB GET. Documented as architectural characteristic.
- **L7 — ZK lifecycle**: Gateway discovery is one-shot via `cmd/start`. After any restart, engines register but gateway doesn't see them. Only recovery: full terraform destroy+apply.
- **Infra user_data bug**: `tee` before `mkdir` — fixed order.
- **Binary GLIBC mismatch**: Built with 2.34, container has 2.31. Fixed with static linking.
- **No auto-scaling**: ASG + ZK discovery = engines join but gateway doesn't discover. Documented as operational burden.
