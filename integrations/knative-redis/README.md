# Knative + Redis Integration Track

This folder provides a local Knative benchmark path for the stateful Redis baseline.
It is intended to support two controlled comparison variants:

- `Knative (edge) + Redis (edge)` via an in-cluster Redis deployment
- `Knative (edge) + Redis (cloud)` by pointing the same Knative service at a remote Redis host

## Contents

- `deploy_knative_redis.sh`: KinD + Knative deployment wrapper for the HTTP benchmark service and Redis.
- `Dockerfile`: container build for the benchmark HTTP service.
- `app.py`: minimal POST-based HTTP server exposing the benchmark.
- `benchmark.py`: benchmark logic mirrored from the Lambda+Redis function.

## Quickstart

Deploy the edge variant:

```bash
./integrations/knative-redis/deploy_knative_redis.sh start
./integrations/knative-redis/deploy_knative_redis.sh url
./integrations/knative-redis/deploy_knative_redis.sh status
```

Invoke it through the Knative ingress:

```bash
python3 scripts/batch_invoke.py \
  'http://redis-bench.knative-redis.127.0.0.1.sslip.io:8080/' \
  --reps 1000 \
  --concurrency 10 \
  --state-size-kb 64 \
  --function-name statefulBench
```

For the cloud Redis variant, redeploy with:

```bash
REDIS_MODE=remote \
REDIS_HOST='<redis-hostname>' \
REDIS_PORT='6379' \
./integrations/knative-redis/deploy_knative_redis.sh deploy
```
