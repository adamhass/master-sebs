# Run 1 — Full Experiment Matrix (2026-04-02)

First complete benchmark run across all three stateful serverless systems.

## Setup

| System | Endpoint | Instance(s) | Concurrency tested |
|--------|----------|-------------|-------------------|
| Lambda + Redis | `https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/` | Managed (256MB) | 1, 10, 50, 100 |
| Boki | `http://16.170.141.184:8080/function/statefulBench` | c5.2xlarge (infra) + c5.xlarge (engine ASG) | 1, 10, 50, 100 |
| Cloudburst + Anna | `http://13.60.72.131:8088/function/stateful_bench` | t3.medium (scheduler/executor/Anna) + HTTP gateway | 1, 10, 50 |

**Region:** eu-north-1 (Stockholm)
**Tool:** `scripts/batch_invoke.py` for all 3 systems (uniform HTTP invocation)
**Post-processing:** `scripts/postprocess_results.py`

## Results

### Steady-State Throughput (64KB state)

| Concurrency | Lambda (inv/s) | Boki (inv/s) | Cloudburst (inv/s) |
|-------------|---------------|-------------|-------------------|
| c=1 | 20.2 | 40.3 | 23.8 |
| c=10 | 45.9 | 255.3 | 30.5 |
| c=50 | 88.0 | 427.5 | 6.4 |
| c=100 | 93.4 | 341.3 | SATURATED |

**Observations:**
- Boki peaks at c=50 (~428/s), drops at c=100 (queueing). Fastest overall.
- Lambda scales smoothly to c=100 (~93/s). Limited by API Gateway + Redis round-trip.
- Cloudburst saturates at c=50 (~6.4/s via HTTP gateway). The single-threaded Python HTTP-to-ZMQ bridge is the bottleneck, not the executors. See LIMITATIONS.md L8, L9.

### Latency Distribution (64KB state, c=50 for Boki/Lambda, c=10 for Cloudburst)

| Metric | Lambda | Boki | Cloudburst |
|--------|--------|------|------------|
| Client P50 | 55.7ms | 51.6ms | 166.4ms |
| Client P95 | 73.9ms | 85.9ms | 458.3ms |
| State write P50 | 1,821us | 5,166us | 16,495us |
| State read P50 | 1,721us | 2us | 2,794us |
| Sample size | 1000 | 1000 | 1000 |

**Observations:**
- Lambda has the lowest write latency (~1.8ms) — ElastiCache Redis is highly optimized.
- Boki write latency (~5.2ms) reflects shared log append across real network hops (engine to sequencer/storage). Read is engine-cached (~2us). See LIMITATIONS.md L7.
- Cloudburst write/read latency (~16-17ms / ~2.8ms) includes Anna KVS round-trip. See LIMITATIONS.md L8.
- Cloudburst client E2E is highest due to HTTP gateway + ZMQ dispatch + scheduler overhead.

### State Size Impact (c=50 for Boki/Lambda, c=10 for Cloudburst)

| State Size | Lambda P50 | Boki P50 | Cloudburst P50 | Lambda Write P50 | Boki Write P50 | Cloudburst Write P50 |
|------------|-----------|---------|---------------|-----------------|---------------|---------------------|
| 1 KB | 55.1ms | 50.0ms | 158.9ms | 1,571us | 5,563us | 16,493us |
| 64 KB | 57.8ms | 47.3ms | 168.0ms | 1,863us | 5,392us | 16,067us |
| 512 KB | 63.7ms | 55.6ms | 154.1ms | 3,921us | 6,037us | 14,760us |

**Observations:**
- Lambda shows clear state size impact: write latency doubles from 1KB to 512KB (1.6ms to 3.9ms). Read latency increases 4x (1.4ms to 5.8ms).
- Boki write latency is relatively stable across sizes (5.1-6.0ms) — shared log append is dominated by network/sequencing, not payload size.
- Cloudburst shows minimal size sensitivity — Anna KVS overhead dominates regardless of payload.

## Metric Coverage

| Metric | Status | Data |
|--------|--------|------|
| Steady State Throughput | COLLECTED | throughput-c{1,10,50,100}.json |
| Latency Dist (P50/P95/P99) | COLLECTED | latency-dist.json |
| Cost per Unit Work | DERIVABLE | `postprocess_results.py --ec2-hourly-rate` |
| Throughput per Resource | DERIVABLE | throughput / instance cost |
| State Size Impact | COLLECTED | statesize-{1,64,512}kb.json |
| State Placement Impact | BLOCKED | Anna routing fix needed |
| Resource Usage over Time | NOT COLLECTED | Monitoring stack needed (TODO 1.4) |
| Cold Start Latency | NOT YET RUN | `measure_cold_start.sh` ready |
| Scale-up/down Interruption | NOT YET RUN | `measure_scaling.sh` ready |
| Scaling to Zero | CATEGORICAL | Lambda: yes, Boki/Cloudburst: no |
| Worker/Server Distinction | CATEGORICAL | Lambda: no, Boki/Cloudburst: yes |

## Findings

1. **Boki is fastest at throughput** but has higher write latency than Lambda due to shared log network hops. Read latency is near-zero (engine cache).
2. **Lambda is most consistent** — smooth scaling, predictable latency, minimal state size sensitivity at small sizes.
3. **Cloudburst is bottlenecked by the HTTP gateway** at c>10. The actual executor throughput is likely higher but masked by the single-threaded bridge. Need to benchmark natively from VPC for true capacity.
4. **State size matters most for Lambda** (Redis wire protocol overhead scales with payload). Boki and Cloudburst are more resilient to payload size.
5. **Cloudburst c=50 saturation** (6.4 inv/s) is a measurement artifact of the HTTP gateway, not a system limitation. c=10 gives 30 inv/s with stable latency.

## Files

Results in `master-sebs/results/`:
```
results/
  boki/
    throughput-c{1,10,50,100}.json
    latency-dist.json
    statesize-{1,64,512}kb.json
  lambda/
    throughput-c{1,10,50,100}.json
    latency-dist.json
    statesize-{1,64,512}kb.json
  cloudburst/
    throughput-c{1,10,50}.json
    latency-dist.json
    statesize-{1,64,512}kb.json
```

## Next Steps

1. Run cold start measurements (`measure_cold_start.sh`) for all 3 systems
2. Run scale-up/down interruption tests (`measure_scaling.sh`)
3. Fix Cloudburst HTTP gateway for higher concurrency (threaded server or async)
4. Consider running Cloudburst natively from VPC for true throughput numbers
5. Add monitoring stack for resource usage over time (TODO 1.4)
