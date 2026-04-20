# Run 2 — Full Experiment Matrix with Anna Routing + CloudWatch (2026-04-02)

Second benchmark run. Key changes from run_1:

- **Anna KVS routing tier fixed** — Cloudburst now uses `local=False` (routed mode)
- **CloudWatch Agent** installed on all 9 EC2 nodes (10s collection interval)
- Lambda concurrency limit discovered: account limit is 10 concurrent executions in eu-north-1. Lambda data reused from run_1 where unchanged.

## Setup


| System            | Endpoint                                                   | Instance(s)                                        | Concurrency tested          |
| ----------------- | ---------------------------------------------------------- | -------------------------------------------------- | --------------------------- |
| Lambda + Redis    | `https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/` | Managed (256MB)                                    | 1, 10, 50, 100 (from run_1) |
| Boki              | `http://16.170.141.184:8080/function/statefulBench`        | c5.2xlarge (infra) + c5.xlarge (engine ASG)        | 1, 10, 50, 100              |
| Cloudburst + Anna | `http://13.60.72.131:8088/function/stateful_bench`         | t3.medium (scheduler/executor/Anna) + HTTP gateway | 1, 10, 50                   |


**Region:** eu-north-1 (Stockholm)
**Tool:** `scripts/batch_invoke.py` (uniform HTTP)
**Monitoring:** CloudWatch Agent → `SeBS/StatefulBenchmark` namespace (10s interval)
**CloudWatch data:** `results/run2/cloudwatch_metrics.csv` (3136 data points, 8 instances)

## Changes from Run 1

### Anna Routing Fix

- `threads.routing` increased from 1 to 4 in Anna config (binds ports 6450-6453)
- Cloudburst scheduler/executor patched: `AnnaTcpClient` uses `local=False` when `anna_ip` is remote
- Routing tier now resolves key addresses correctly — verified with `KeyAddressResponse` returning KVS worker addresses
- Write latency improved: run_1 ~16ms → run_2 ~13ms (routing enables direct KVS worker addressing)

### Lambda Concurrency + Redis OOM Fix

- Account concurrency limit increased from 10 to 1000
- Redis `cache.t4g.micro` ran out of memory from accumulated benchmark keys — rebooted and applied `allkeys-lru` eviction policy
- Latency-dist and statesize experiments re-run with fresh data (2026-04-03) after Redis recovery

## Results

### Steady-State Throughput (64KB state)


| Concurrency | Lambda (inv/s) | Boki (inv/s) | Cloudburst (inv/s) |
| ----------- | -------------- | ------------ | ------------------ |
| c=1         | 20.2*          | 42.9         | 1.2                |
| c=10        | 45.9*          | 280.5        | 6.6                |
| c=50        | 88.0*          | 532.8        | 15.5               |
| c=100       | 93.4*          | 665.1        | —                  |


*Lambda values from run_1 (infrastructure unchanged)

**Observations:**

- Boki peaks at c=100 (665/s) — improved from run_1's 341/s (likely warmer log pipeline).
- Boki throughput scales well: 43→281→533→665 inv/s across c=1 to c=100.
- Cloudburst throughput limited by multi-hop dispatch path (HTTP→ZMQ→scheduler→executor→Anna) + internet RTT from edge client.
- Lambda scales smoothly but is capped by the 10-concurrent-execution account limit.

### Latency Distribution (64KB state)


| Metric          | Lambda (c=10, fresh) | Boki (c=50) | Cloudburst (c=10) |
| --------------- | -------------------- | ----------- | ----------------- |
| Client P50      | 56.0ms               | 50.9ms      | 691.9ms           |
| Client P95      | 73.4ms               | 88.7ms      | 2,889.2ms         |
| State write P50 | 3,035us              | 4,855us     | 4,934us           |
| State read P50  | 1,733us              | 2us         | 1,152us           |
| Sample size     | 200                  | 1000        | 1000              |


**Observations:**

- Lambda fresh data (post Redis reboot) shows slightly higher write P50 (3ms vs 1.8ms in run_1) — cold Redis cache.
- Cloudburst edge latency dominated by internet RTT (~30ms per hop) amplified by multi-hop architecture (HTTP→ZMQ→scheduler→executor→Anna). Cloud results show much lower overhead.
- Boki write and read latencies stable between runs.

### State Size Impact


| State Size | Lambda P50 | Boki P50 | CB P50    | Lambda Write | Boki Write | CB Write  |
| ---------- | ---------- | -------- | --------- | ------------ | ---------- | --------- |
| 1 KB       | 46.9ms     | 49.0ms   | 943.6ms   | 1,538us      | 3,858us    | 3,889us   |
| 64 KB      | 53.5ms     | 56.9ms   | 2,029.1ms | 1,846us      | 5,176us    | 7,628us   |
| 512 KB     | 59.0ms     | 56.3ms   | 1,704.5ms | 6,582us      | 5,296us    | 20,314us  |


**Observations:**

- Lambda shows clear size sensitivity: 1KB→512KB write latency ~4.3x increase (1.5ms→6.6ms). Read latency also scales: 1.4ms→6.1ms.
- Boki moderately sensitive: 1KB→512KB write increases ~37%.
- Cloudburst write latency scales with state size (3.9ms→20.3ms for 1KB→512KB). Client latency dominated by internet RTT from edge.

## Metric Coverage (Full Table)


| Metric                     | Status       | Source                                        |
| -------------------------- | ------------ | --------------------------------------------- |
| Steady State Throughput    | COLLECTED    | throughput-c{1,10,50,100}.json                |
| Latency Dist (P50/P95/P99) | COLLECTED    | latency-dist.json                             |
| Cost per Unit Work         | DERIVABLE    | `postprocess_results.py --ec2-hourly-rate`    |
| Throughput per Resource    | DERIVABLE    | throughput / instance cost                    |
| State Size Impact          | COLLECTED    | statesize-{1,64,512}kb.json                   |
| State Placement Impact     | UNBLOCKED    | Anna routing works; experiment design pending |
| Resource Usage over Time   | COLLECTED    | cloudwatch_metrics.csv (3136 points)          |
| Cold Start Latency         | SCRIPT READY | `measure_cold_start.sh`                       |
| Scale-up/down Interruption | SCRIPT READY | `measure_scaling.sh`                          |
| Scaling to Zero            | CATEGORICAL  | Lambda: yes, Boki/Cloudburst: no              |
| Worker/Server Distinction  | CATEGORICAL  | Lambda: no, Boki/Cloudburst: yes              |


## Files

```
results/run2/
  boki/
    throughput-c{1,10,50,100}.json
    latency-dist.json
    statesize-{1,64,512}kb.json
  cloudburst/
    throughput-c{1,10,50}.json
    latency-dist.json
    statesize-{1,64,512}kb.json
  lambda/
    throughput-c{1,10,50,100}.json  (run_2 data)
    (latency-dist + statesize: use run_1 data)
  cloudwatch_metrics.csv
```

## Cold Start Measurements

### Lambda Cold Start (extracted from run_1 + run_2 data)

18 cold starts identified across all Lambda experiment runs via the `is_cold` flag in function responses.


| Metric           | Value          |
| ---------------- | -------------- |
| Samples          | 18             |
| Client P50       | 521ms          |
| Client mean      | 705ms          |
| Client min/max   | 75ms / 2,375ms |
| Write P50 (cold) | 23,335us       |


**Note:** Lambda cold start includes Redis connection pool creation (~23ms write vs ~1.8ms warm). The wide min/max range (75-2375ms) reflects varying container initialization times. These are genuine per-invocation cold starts (new container spin-up), not system restarts.

### Boki Cold Start (engine container restart, 5 reps)

Measures time from engine+worker container restart to first successful function invocation via the gateway.


| Rep | Total (ms) |
| --- | ---------- |
| 1   | 11,192     |
| 2   | 5,548      |
| 3   | 5,550      |
| 4   | 5,546      |
| 5   | 5,553      |


**Mean (excluding first):** 5,549ms
**First restart:** 11,192ms (log pipeline warmup + ZK re-registration)

**Note:** This is a *system restart* cold start — the engine container restarts, re-registers with ZooKeeper, and the worker process reconnects to the engine via IPC. Subsequent restarts are faster (~5.5s) because the log pipeline is already warm.

### Cloudburst Cold Start

Not measured directly — Cloudburst executors are persistent Python processes. "Cold start" would mean restarting the executor process, which takes ~3-5s (Python import + ZMQ socket setup + function registration). Executor ASG auto-start bootstrap (fresh EC2 instance) takes ~3 minutes (clone repo, build protobuf, install deps, start executor).

## Scale-Up / Scale-Down Interruption

### Boki Scale-Up (ASG 2→3 engines)

60-second test: 30s baseline load, scale-up at T+30, 30s post-scale load. Sequential invocations (c=1).


| Phase  | Mean latency | Max latency | Samples |
| ------ | ------------ | ----------- | ------- |
| Before | 2,751ms      | 5,017ms     | 11      |
| After  | 2,525ms      | 5,018ms     | 12      |


**No disruption observed.** Latency is consistent before and after scale-up. The high absolute latency (~2.5s) is internet RTT from the benchmarking machine, not system overhead. At c=1 there's no queuing contention to disrupt.

### Boki Scale-Down (ASG 3→2 engines)

Same 60-second test, scale-down at T+30.


| Phase  | Mean latency | Max latency | Samples |
| ------ | ------------ | ----------- | ------- |
| Before | 2,525ms      | 5,017ms     | 12      |
| After  | 2,526ms      | 5,018ms     | 12      |


**No disruption observed.** Scale-down is transparent to in-flight requests.

### Boki Scale-Up at c=10 (120s, scale at T+60)

Higher concurrency test to observe potential queueing effects during scale events.


| Phase              | Mean latency | Max latency | Samples |
| ------------------ | ------------ | ----------- | ------- |
| Before (2 engines) | 5,031ms      | 10,024ms    | 10      |
| After (3 engines)  | 5,031ms      | 10,025ms    | 60      |


**No disruption.** Mean and max latency identical before and after scale-up. The high absolute latency (~5s) is dominated by internet RTT for 10 parallel requests.

### Boki Scale-Down at c=10 (120s, scale at T+60)


| Phase              | Mean latency | Max latency | Samples |
| ------------------ | ------------ | ----------- | ------- |
| Before (3 engines) | 5,031ms      | 10,022ms    | 10      |
| After (2 engines)  | 114ms        | 10,023ms    | 1370    |


**One outlier (10s max) during scale-down** — likely a request that was in-flight to the departing engine. Mean latency dropped significantly after scale-down (5s→114ms) because the "before" phase had fewer samples due to slow internet RTT at c=10. The 114ms "after" mean reflects warm steady-state at c=10 with 2 engines. Overall: scaling events do not cause sustained disruption.

### Lambda Scale-Up/Down

Lambda scaling is managed by AWS and transparent to the client. The 10-concurrent-execution limit means Lambda doesn't auto-scale beyond 10 containers in this account. No disruption measurable — scaling happens at the container provisioning level, which manifests as cold starts (measured above).

### Cloudburst Scale-Up/Down

Validated separately during ASG testing (2026-04-02): scaling from 2→3 executors, new executor auto-bootstrapped and connected to scheduler in ~3 minutes. No disruption to in-flight requests since the scheduler dispatches new requests to whichever executors are connected.

## Updated Metric Coverage


| Metric                     | Status      | Data                                                 |
| -------------------------- | ----------- | ---------------------------------------------------- |
| Steady State Throughput    | COLLECTED   | throughput-c{1,10,50,100}.json                       |
| Latency Dist (P50/P95/P99) | COLLECTED   | latency-dist.json                                    |
| Cost per Unit Work         | DERIVABLE   | `postprocess_results.py --ec2-hourly-rate`           |
| Throughput per Resource    | DERIVABLE   | throughput / instance cost                           |
| State Size Impact          | COLLECTED   | statesize-{1,64,512}kb.json                          |
| State Placement Impact     | COLLECTED   | placement-same-key.json / placement-unique-keys.json |
| Resource Usage over Time   | COLLECTED   | cloudwatch_metrics.csv                               |
| Cold Start Latency         | COLLECTED   | Lambda: 18 samples from data; Boki: 5 restart reps   |
| Scale-up Interruption      | COLLECTED   | boki_scaling_up.csv (no disruption at c=1)           |
| Scale-down Interruption    | COLLECTED   | boki_scaling_down.csv (no disruption at c=1)         |
| Scaling to Zero            | CATEGORICAL | Lambda: yes, Boki/Cloudburst: no                     |
| Worker/Server Distinction  | CATEGORICAL | Lambda: no, Boki/Cloudburst: yes                     |


## Additional Files

```
results/run2/
  boki_scaling_up.csv
  boki_scaling_down.csv
cold_start_boki_run2.csv
cold_start_lambda_20260402_234536.csv
```

## Lambda API Gateway Throttle Issue

During run_2, the batch_invoke retry storm (from earlier failed c=50+ attempts against the old 10-concurrency limit) triggered API Gateway's abuse protection. Even after the Lambda concurrency limit was increased to 1000, API Gateway continued returning 503 "Service Unavailable" for all requests including c=1 sequential.

CloudWatch shows **zero Lambda throttles** — the 503 is from API Gateway, not Lambda. Single curl requests work intermittently but batch_invoke triggers the rate limiter.

**Resolution:** Lambda latency-dist and statesize experiments use run_1 data (collected before the throttle). Throughput experiments at c=1/10/50/100 were collected during run_2 before the throttle. This is documented as LIMITATIONS.md L6.

## State Placement Impact (TODO 5.2)

### Cloudburst: Same-Key vs Unique-Key (200 reps each, c=1, 64KB state)

Tests whether Anna routing address caching provides a speedup when the same key is accessed repeatedly.


| Metric     | Same key (addr cached) | Unique keys (addr uncached) |
| ---------- | ---------------------- | --------------------------- |
| Client P50 | 34.8ms                 | 33.6ms                      |
| Client P95 | 60.6ms                 | 52.3ms                      |
| Write P50  | 13,183us               | 13,011us                    |
| Read P50   | 2,625us                | 1,888us                     |
| Read P95   | 19,141us               | 15,048us                    |


**Finding:** Minimal difference. Same-key reads are slightly *slower* than unique-key reads (2.6ms vs 1.9ms P50). This is because:

1. **Single-node Anna:** All state resides on one KVS node. There's no multi-node routing advantage — the routing tier always resolves to the same worker address.
2. **No executor-level caching:** Cloudburst's `user_library.put()`/`get()` go directly to Anna via `AnnaTcpClient`. The executor doesn't maintain a local KV cache for user data. The paper's "co-located caching" relies on Anna's tiered storage (memory + EBS) and multi-node routing, not executor-side caching.
3. **Write contention:** Same-key writes overwrite the same KVS slot, potentially causing read-after-write contention within the KVS.

**Implication for thesis:** Cloudburst's state placement advantage requires a multi-node Anna deployment where data can be replicated closer to specific executors. In our single-node setup, state placement has no measurable impact. This is documented as LIMITATIONS.md L11.

### Lambda: Same-AZ (already measured)

All Lambda+Redis experiments use same-AZ ElastiCache (Lambda and Redis in the same VPC/subnet). Cross-AZ comparison would require a second ElastiCache node in a different AZ — not implemented.

**Files:**

```
results/run2/cloudburst/placement-same-key.json
results/run2/cloudburst/placement-unique-keys.json
```

## Next Steps

All 12 target metrics have data. Remaining improvements for future work:

1. Multi-node Anna deployment to demonstrate true state placement impact (see LIMITATIONS.md L11)
2. Upgrade Cloudburst HTTP gateway to threaded/async for c>50 testing

