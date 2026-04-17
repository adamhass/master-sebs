# Lambda + Redis (Baseline)

## Architecture

```
Client → API Gateway (HTTPS) → Lambda (Python 3.12) → ElastiCache Redis
```

Standard AWS serverless stack. Lambda handles compute, Redis handles state. API Gateway routes HTTP to Lambda. Each invocation is an independent container — no shared memory, no durable execution.

## Implementation

**Terraform** (`integrations/baseline/aws/`): VPC (10.50.0.0/16), 2 public subnets, Lambda function, API Gateway HTTP API, ElastiCache Redis (cache.t4g.micro, allkeys-lru), security groups isolating Redis to Lambda-only access.

**Benchmark function** (`lambda_package/handler.py`): API Gateway v2 event parsing → Redis SET (write) → Redis GET (read) → compute loop → SeBS-format JSON response. Module-level connection pool reused across warm invocations. Cold start detected via global `_is_cold` flag.

**State mechanism**: Redis SET/GET over network. State shared across invocations (same key readable by any Lambda instance). No durability — Redis is volatile cache with allkeys-lru eviction.

**Invocation**: `POST https://<api-gw-id>.execute-api.eu-north-1.amazonaws.com/`

## Design Decisions

- Redis chosen over DynamoDB for lower latency (in-VPC, sub-2ms vs ~5-10ms)
- allkeys-lru eviction policy prevents OOM (resolved L4 from early runs)
- Lambda concurrency increased to 1000 (eu-north-1 default was 10)
- No VPC endpoint for Redis — Lambda placed in same VPC with direct access

## Limitations Found

- **L4 — Redis OOM**: cache.t4g.micro filled with benchmark keys. Fixed with allkeys-lru eviction.
- **L5 — Concurrency limit**: Account default 10 in eu-north-1. Had to request increase.
- **512KB state from cloud**: 0.8 inv/s — rapid-fire DDB/Redis writes at low RTT caused timeouts.
- **Cold starts**: ~473ms median. Container init + Redis connection pool bootstrap.
- **No durability**: Redis crash = state loss. No checkpoint, no replay.
