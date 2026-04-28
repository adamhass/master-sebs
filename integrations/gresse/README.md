# Gresse Integration Track

This folder provides a native Gresse integration path under `master-sebs/integrations/`.
It is separate from the generic SeBS provider abstraction because Gresse is currently exercised as its own replicated runtime.

## Contents

- `deploy_gresse.sh`: local Gresse + MinIO build/start/stop/status wrapper using `../Gresse`.
- `deploy_gresse_knative.sh`: local KinD + Knative deployment path for Gresse, using AWS S3-compatible object storage config.
- `Dockerfile.knative`: container build for `examples/bench_function`.
- `knative/kind-cluster.yaml`: KinD config with host port mappings for Knative ingress.
- `run_gresse_bench.sh`: HTTP repeat client + `collect_gresse_results.py` (set `GRESSE_HTTP_URL` if not using the default local replica).
- `collect_gresse_results.py` / `gresse_to_common_schema.py`: raw run → `collected_metrics.json` → common JSONL/CSV.
- `common_schema_columns.md`: normalization field contract.
- `results/raw/.gitkeep`: raw run outputs.
- `results/normalized/.gitkeep`: normalized outputs.

## Paths

Default Gresse source root:

- `../Gresse` relative to `master-sebs/`

Override with:

- `GRESSE_ROOT=/absolute/path/to/Gresse`

## Quickstart (Local)

From `master-sebs/`:

```bash
./integrations/gresse/deploy_gresse.sh start
./integrations/gresse/deploy_gresse.sh status
./integrations/gresse/run_gresse_bench.sh 50
./integrations/gresse/deploy_gresse.sh stop
```

The local deploy wrapper assumes:

- Docker is available for the MinIO dependency in `Gresse/docker-compose.minio.yml`.
- The benchmark replica is the Rust example `examples/bench_function`.
- The default HTTP endpoint is `http://127.0.0.1:9090/`.

## Quickstart (KinD + Knative + AWS S3)

This path is intended for local experimentation on a laptop, with Knative Serving running on a local KinD cluster and Gresse membership / persistent state stored in a remote AWS S3 bucket.

Prerequisites:

- `docker`
- `kind`
- `kubectl`
- outbound network access to download Knative manifests and to reach AWS S3

Required environment variables:

```bash
export AWS_PROFILE='gresse'
export AWS_REGION='eu-north-1'
```

Common optional overrides:

```bash
export GRESSE_OBJECT_STORAGE_REGION='eu-north-1'
export GRESSE_OBJECT_STORAGE_BUCKET='gresse'
export GRESSE_PERSISTENT_REPLICA_PATH='experiment1/persistent.json'
export GRESSE_MEMBERSHIP_DIRECTORY_PATH='experiment1/membership'
export GRESSE_MIN_SCALE='1'
export GRESSE_MAX_SCALE='3'
```

The script reads your local `~/.aws/credentials` and `~/.aws/config`, copies them into a Kubernetes secret, and mounts that secret into the Knative pod. Leave `GRESSE_OBJECT_STORAGE_URL` unset for real AWS S3.

Bring the stack up:

```bash
./integrations/gresse/deploy_gresse_knative.sh start
./integrations/gresse/deploy_gresse_knative.sh url
./integrations/gresse/deploy_gresse_knative.sh status
```

Then point the benchmark runner at the printed Knative URL:

```bash
GRESSE_HTTP_URL="$(./integrations/gresse/deploy_gresse_knative.sh url)" \
  ./integrations/gresse/run_gresse_bench.sh 50
```

Tear it down:

```bash
./integrations/gresse/deploy_gresse_knative.sh delete
./integrations/gresse/deploy_gresse_knative.sh destroy
```

## Benchmark → common schema

After the replica is reachable, run:

```bash
GRESSE_HTTP_URL='http://127.0.0.1:9090/' ./integrations/gresse/run_gresse_bench.sh 100
python3 integrations/gresse/gresse_to_common_schema.py \
  --input-glob 'integrations/gresse/results/raw/*/collected_metrics.json' \
  --output-jsonl integrations/gresse/results/normalized/gresse_common.jsonl \
  --output-csv integrations/gresse/results/normalized/gresse_common.csv
```

## Notes

- This integration now has two local execution paths: direct host execution with MinIO, and KinD + Knative with remote S3-backed membership / persistence.
- The current collector measures end-to-end HTTP invoke latency; deeper CRDT convergence metrics can be added later from Gresse-emitted sidecars.
- Gresse uses eventual consistency by default in this benchmark path, so `consistency_model` defaults to `eventual`.
- The Knative deployment path sets `GRESSE_MIN_SCALE=1` by default. That is deliberate: Gresse stores peer addresses in object storage, and aggressive pod churn will otherwise make membership unstable.
- For Knative, `GRESSE_ADDR` is sourced from the pod IP via the Kubernetes downward API so Gresse replicas can advertise pod-reachable internal addresses to each other.
