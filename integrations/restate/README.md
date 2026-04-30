# Restate Integration Track

This folder contains a local Restate deployment path for controlled benchmark runs.

## Local Restate + Knative Handler

`deploy_restate_knative.sh` deploys:

- a single-node local Restate orchestrator into the existing KinD cluster
- a Knative-hosted Restate handler built from `aws/handler/handler.py`
- a local `kubectl port-forward` so benchmarks can invoke Restate at `127.0.0.1`

Default benchmark URL:

```bash
http://127.0.0.1:18080/statefulBench/{key}/run
```

Bring it up:

```bash
./integrations/restate/deploy_restate_knative.sh start
./integrations/restate/deploy_restate_knative.sh url
./integrations/restate/deploy_restate_knative.sh status
```

Smoke-test it:

```bash
python3 scripts/batch_invoke.py \
  'http://127.0.0.1:18080/statefulBench/{key}/run' \
  --reps 20 \
  --concurrency 10 \
  --state-size-kb 64 \
  --output /tmp/restate-local-smoke.json \
  --function-name statefulBench
```

Tear it down:

```bash
./integrations/restate/deploy_restate_knative.sh delete
./integrations/restate/deploy_restate_knative.sh destroy
```
