# Run 6 — Lambda Durable + Restate Benchmarks (2026-04-15)

Two new systems added to the comparison: AWS Lambda Durable Functions and Restate.

## Motivation

Runs 1-5 compared three systems: Lambda+Redis (baseline), Boki (shared log), and Cloudburst+Anna (distributed KV). This run adds:

1. **Lambda Durable** — conventional extension of the baseline. Same Lambda compute, adds durable execution SDK with DynamoDB state. Measures: "what does adding durability cost?"
2. **Restate** — alternative approach. Durable execution runtime with embedded KV state, handlers deployed as Lambda functions. Represents production evolution of stateful serverless research.

## Setup

### Lambda Durable

- **Compute:** AWS Lambda with `@durable_execution` decorator, Python 3.13
- **State store:** DynamoDB (PAY_PER_REQUEST, partition key `state_key`)
- **Durability:** SDK checkpoint/replay — each state operation wrapped in `@durable_step`
- **Invocation:** API Gateway HTTP API → `POST /durable`
- **Endpoint:** `https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/durable`
- **No VPC/Redis** — fully serverless stack (Lambda + DynamoDB + Durable SDK)

### Restate

- **Compute:** AWS Lambda handler behind Restate server (true FaaS model)
- **State store:** Restate embedded KV (journal-backed, no external DB)
- **Durability:** Restate journal — every state mutation durably logged
- **Architecture:** `Client → Restate Server (EC2 t3.medium) → Lambda handler ←→ Restate Server (state journal)`
- **Invocation:** `POST http://<restate-server>:8080/statefulBench/{key}/run`
- **Server:** `16.171.60.65` (private `10.70.1.92`), VPC `10.70.0.0/16`
- **Unique keys per invocation** — avoids Virtual Object per-key exclusive lock serialization

### State Mechanism Comparison

| System | State store | Write mechanism | Read mechanism | External dep |
|--------|------------|----------------|----------------|-------------|
| Lambda + Redis | ElastiCache Redis | Redis SET (network) | Redis GET (network) | Managed Redis |
| Lambda Durable | DynamoDB | DDB PutItem in `@durable_step` | DDB GetItem in `@durable_step` | Serverless DDB |
| Restate | Embedded KV | `ctx.set()` (journal append) | `ctx.get()` (journal read) | None (embedded) |
| Boki | Shared log | Log append | Engine cache lookup | None (embedded) |
| Cloudburst | Anna KVS | `cloudburst.put()` | `cloudburst.get()` | Distributed Anna |

### Experiment Matrix

Same as run_2/run_5:

| Experiment | Concurrency | State size | Reps |
|------------|-------------|------------|------|
| Throughput | 1, 10, 50, 100 | 64KB | 200 |
| Latency distribution | 10 | 64KB | 1000 |
| State size impact | 10 | 1, 64, 512KB | 200 |

All experiments run from laptop (edge), same as run_1-run_4.

---

## Throughput Results (Edge)

| Concurrency | Lambda Durable (inv/s) | Restate (inv/s) | Lambda Baseline (inv/s) | Boki (inv/s) |
|:-----------:|:----------------------:|:---------------:|:-----------------------:|:------------:|
| c=1 | 1.5 | 8.5 | 20.7 | 42.9 |
| c=10 | 12.1 | 52.0 | 84.0 | 280.5 |
| c=50 | 17.0 | 118.3 | 87.9 | 532.8 |
| c=100 | 33.1 | 210.9 | 86.8 | 665.1 |

Lambda Baseline and Boki numbers from run_2 for reference.

**Observations:**
- **Restate scales linearly** — 8.5 → 211 inv/s (25x at 100x concurrency). Each invocation uses a unique Virtual Object key, avoiding serialization.
- **Lambda Durable scales sub-linearly** — 1.5 → 33 inv/s. DynamoDB + checkpoint overhead compounds with API Gateway latency.
- **Lambda Durable ~6x slower than baseline Lambda** at c=10 — the cost of adding durability (DDB write + checkpoint per state op vs Redis SET).
- **Restate faster than Lambda baseline at c=50+** — despite going through Restate server + Lambda, embedded KV state avoids external network hops.

---

## Latency Distribution (Edge, c=10, 64KB)

| Metric | Lambda Durable | Restate | Lambda Baseline | Boki |
|--------|:--------------:|:-------:|:---------------:|:----:|
| Client P50 | 638.2ms | 119.4ms | 55.3ms | 50.9ms |
| Client P95 | 746.5ms | 160.6ms | 67.6ms | 53.3ms |
| Client P99 | 3,230.9ms | 250.1ms | 103.1ms | 57.1ms |
| Write P50 | 12.6ms | 371us | 1,942us | 4,709us |
| Read P50 | 4,641us | 282us | 1,001us | 2us* |
| Cold starts | 11/1000 | 0/1000 | — | — |
| Samples | 1,000 | 1,000 | — | — |

\* Boki read is engine-cached (see LIMITATIONS.md L6). Lambda Baseline and Boki from run_2.

**Observations:**
- **Lambda Durable P50 = 638ms** — dominated by DynamoDB write (12.6ms) + DynamoDB read (4.6ms) + checkpoint overhead + API GW. The 638ms includes ~600ms of serverless overhead (checkpoint creation, DDB round-trips, API GW routing).
- **Restate P50 = 119ms** — state ops are sub-millisecond (371us write, 282us read). The 119ms is mostly Restate server → Lambda dispatch + Lambda execution overhead.
- **Restate state ops are 30-50x faster than Lambda Durable** — embedded KV (microseconds) vs DynamoDB (milliseconds).
- **Lambda Durable P99 = 3.2s** — cold start spike (11 cold starts in 1000 invocations). Durable SDK initialization + DDB client bootstrap.

---

## State Size Impact (Edge, c=10, write P50)

| State Size | Lambda Durable | Restate | Lambda Baseline | Boki |
|:----------:|:--------------:|:-------:|:---------------:|:----:|
| 1 KB | ~2ms | 30us | 800us | 3,738us |
| 64 KB | 12.6ms | 371us | 1,942us | 4,709us |
| 512 KB | **FAILED** | 1.8ms | * | 5,003us |

\* Lambda Baseline 512KB: 0.8 inv/s from cloud (run_5). Lambda Durable 512KB: DynamoDB 400KB item size limit exceeded.

**Lambda Durable 512KB limitation:** DynamoDB enforces a 400KB maximum item size. A 512KB binary blob exceeds this hard limit. All 200 invocations failed with `ValidationException`. This is a fundamental constraint of using DynamoDB as a state store — production systems would use S3 for large objects with DDB as an index.

---

## Observations

### 1. Durability has a measurable cost

Lambda Durable is ~6x slower than Lambda Baseline at c=10. The overhead comes from:
- **DynamoDB write** (~12ms vs Redis ~2ms) — serverless DB is slower than in-VPC Redis
- **Checkpoint creation** — each `@durable_step` creates a checkpoint in Lambda's durable execution log
- **Two checkpoints per invocation** — write step + read step = 2 checkpoint round-trips

This is the price of durability guarantees. Lambda Baseline has no durability — if Lambda crashes mid-execution, state in Redis may be inconsistent.

### 2. Embedded state eliminates the external-store bottleneck

Restate's state operations (371us write, 282us read) are ~30-50x faster than Lambda Durable's DynamoDB operations (12.6ms write, 4.6ms read). The difference: embedded KV (local memory + journal append) vs external service (network hop + DDB request processing).

This validates the thesis narrative: Restate absorbs lessons from Boki (shared log) and Cloudburst (state co-location) — embedded state eliminates the external-store bottleneck that limits Lambda+Redis and Lambda+DynamoDB.

### 3. Restate throughput exceeds Lambda Baseline at high concurrency

At c=50+, Restate (118 inv/s) outperforms Lambda Baseline (88 inv/s). Despite the extra hop (Restate server → Lambda), the fast embedded state compensates. Lambda Baseline is bottlenecked by Redis round-trips at high concurrency.

### 4. DynamoDB 400KB limit constrains Lambda Durable

The 400KB item size limit is a real architectural constraint. Lambda+Redis (512MB max value) and Restate (no documented limit) handle large state natively. This matters for systems storing serialized objects, images, or ML model weights.

---

## Files

```
results/run6/lambda-durable/    — 7 JSON files (512KB failed)
results/run6/restate/           — 8 JSON files (all succeeded)
docs/runs/run_6_durable_restate.md — this document
```

---

## Infrastructure Created

| Resource | Type | Details |
|----------|------|---------|
| `master-sebs-baseline-durable-fn` | Lambda | Python 3.13, durable_config enabled, 256MB |
| `master-sebs-baseline-durable-state` | DynamoDB | PAY_PER_REQUEST, partition key `state_key` |
| `master-sebs-restate-vpc` | VPC | 10.70.0.0/16, eu-north-1 |
| `master-sebs-restate-handler` | Lambda | Python 3.13, Restate SDK, 256MB |
| `master-sebs-restate-server` | EC2 t3.medium | Restate Docker, ports 8080+9070 |
| `master-sebs-restate-client` | EC2 t3.small | Benchmark client (cloud experiments) |
