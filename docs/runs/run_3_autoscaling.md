# Run 3 — Auto-Scaling Experiment (2026-04-06)

Attempted to add AWS Target Tracking auto-scaling policies to Boki and Cloudburst ASGs, then observe autonomous scaling behaviour under load. The experiment revealed that infrastructure-level auto-scaling (ASG) does not translate to application-level auto-scaling for either system.

## Setup

| Parameter | Value |
|-----------|-------|
| Scaling policy | Target Tracking, ASGAverageCPUUtilization = 50% |
| Instance warmup | 120s (Boki), 180s (Cloudburst) |
| ASG min/desired/max | 1/1/4 |
| Systems | Boki Engine ASG, Cloudburst Executor ASG |

## Procedure

1. Applied `TargetTrackingScaling` policies to both ASGs
2. Set desired capacity to 1 (scale down from 2)
3. Smoke-tested both systems at minimum capacity
4. Planned to ramp load and observe auto-scale-out

## Results: Both Systems Failed at Minimum Capacity

### Boki

After ASG scaled down to 1 engine, the surviving instance was a **newly launched replacement** (the original engines were terminated). The new engine:

- Bootstrapped via user_data (cloud-init completed)
- Docker Compose file was present
- Engine container started and registered with ZooKeeper
- **But:** The `stateful_bench` Go binary was not deployed (empty `/opt/boki/workspace/stateful_bench/` directory)
- **But:** Even after manually deploying the binary, the gateway returned empty responses — the ZK controller's `cmd/start` had already fired during initial cluster setup and does not re-trigger for new engines joining mid-flight

**Root causes:**
1. **Binary deployment is manual.** The user_data template downloads from S3 if `bench_binary_s3_uri` is set, but this was empty. Each new engine needs the binary deployed via SCP.
2. **Gateway discovery is one-shot.** The ZK-setup script waits 120s then issues `cmd/start`, after which the gateway discovers all registered engines. New engines that join after this point are registered in ZK but not picked up by the gateway until a cluster restart.

### Cloudburst

After ASG scaled down to 1 executor, function registration failed:

- The surviving executor was running and connected to the scheduler
- The HTTP gateway attempted to re-register `stateful_bench` via `CloudburstConnection.register()`
- Registration failed: `"Function stateful_bench not registered. Please register before including it in a DAG."`
- The function had been pinned to a now-terminated executor; the scheduler's internal state was stale

**Root causes:**
1. **Function pinning is per-executor.** When Cloudburst registers a function, it gets pinned to specific executor(s). When those executors are terminated, the function is lost.
2. **No automatic re-registration.** The scheduler does not re-pin functions to new executors. The client must re-register, but `register_dag()` fails if the function was previously registered with a now-stale reference.
3. **Scheduler state is not reconciled.** There is no mechanism to detect that pinned executors have departed and automatically re-register functions.

## Finding: Infrastructure Scaling ≠ Application Scaling

Lambda auto-scales transparently because **function deployment is managed** — every new container receives the code, runtime, and configuration automatically. The developer never thinks about which container has their code.

Boki and Cloudburst auto-scale at the infrastructure level (ASG launches/terminates EC2 instances), but the **application layer does not handle the lifecycle**:

| Concern | Lambda | Boki | Cloudburst |
|---------|--------|------|------------|
| Code deployment to new instance | Automatic | Manual (SCP or S3) | Automatic (git clone in user_data) |
| Service discovery | Managed | ZK registration works, gateway discovery is one-shot | ZMQ connection works automatically |
| Function registration | Automatic | N/A (binary is the function) | Per-executor, lost on termination |
| State continuity | Managed (Redis persists) | Log persists, engine cache cold | Anna persists, executor cache cold |
| Scale-to-zero | Yes | No (needs running infra) | No (needs running scheduler) |

**The operational burden of self-hosted serverless is not just deployment — it is lifecycle management.** True auto-scaling requires solving binary deployment, function registration, service discovery refresh, and state warm-up on every scale event. These are precisely the problems that managed platforms like Lambda solve natively.

## Decision

Auto-scaling policies reverted. Both systems use **managed scaling** (manual `desired_capacity` changes) for all experiments. This is documented as a design choice:

- Manual scaling proves the mechanism works (new instances bootstrap, connect, serve traffic when properly configured)
- The lifecycle gaps (binary deployment, function re-registration, gateway discovery) are documented as findings
- Lambda's auto-scaling is compared against the self-hosted systems' manual scaling, with the operational burden explicitly acknowledged

## Files

No benchmark data collected — the experiment failed before load generation.
Scaling policies were applied and removed within the same session.
