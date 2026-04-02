# Boki — Next Session Plan

## Primary Goal
Deploy Boki via Docker Compose on a single EC2 instance, get the smoke test passing.

## Instance
- `c5.4xlarge` (16 vCPU, 32GB RAM) — enough headroom for saturation testing
- Amazon Linux 2 with kernel 5.10 (for io_uring)
- 100GB EBS (Docker images + RocksDB storage)

## Docker Compose Setup
Based on `boki-benchmarks/experiments/workflow/boki-movie/docker-compose.yml`.

Key flags from official benchmarks:
- `--privileged` or `--security-opt seccomp=unconfined` for io_uring
- `--num_io_workers=4` (engine), `--num_io_workers=2` (gateway, sequencer, storage)
- `--io_uring_entries=2048 --io_uring_fd_slots=4096` (all nodes)
- `--slog_engine_enable_cache --slog_engine_cache_cap_mb=1024` (engine)
- `--lb_per_fn_round_robin --max_running_requests=0` (gateway)

## Checklist

- [ ] Provision `c5.4xlarge` with AL2 kernel 5.10, 100GB EBS
- [ ] Install Docker, docker-compose
- [ ] Write `docker-compose.yml` for single-node Boki cluster
- [ ] Use `zjia/boki:sosp-ae` with `--privileged` for io_uring
- [ ] Mount Go benchmark binary via shared volume (avoid image rebuild)
- [ ] ZK setup script from `boki-benchmarks/scripts/zk_setup.sh` (50s wait before `cmd/start`)
- [ ] Fix JSON parsing — `json.Number` for GET query string params (already done in code, need static binary rebuild on AL2)
- [ ] Apply `mem_limit` and `cpus` in Compose for fair comparison
- [ ] Smoke test: `curl http://localhost:8080/function/statefulBench?state_key=test&state_size_kb=1&ops=1`
- [ ] Run 5 invocations, compare with Lambda+Redis and Cloudburst numbers

## Elasticity Metrics on Single Host

### Scale-up Interruption
- `docker-compose scale worker=N` — measure delta to first successful `Append` from new worker
- Boki workers are "stateless" until they pull log tail — measure Log Replay phase duration

### Cold Start
- `docker-compose stop worker` → trigger request → measure startup
- Two components: io_uring init (infrastructure) + Go runtime init (application)

### Throughput Saturation
- Test with 2, 4, 8, 12 workers on 16 vCPUs
- Monitor Sequencer CPU — log-structured writes bottleneck sequencer before workers

## Data Consistency
Ensure same parameters across all 3 systems:
- `state_size_kb`: 1, 64, 512
- `ops`: 1
- `state_key`: "bench:state"
- Response format: `request_id`, `is_cold`, `begin`, `end`, `measurement` block

## Latency Collection
- **Lambda+Redis**: SeBS `ExecutionResult` + `measurement` block from function response
- **Cloudburst**: `print_latency_stats` (P1-P99) from `run_benchmark.py`
- **Boki**: Function response contains per-invocation timing in `measurement` block. External driver (curl/wrk) measures E2E. No `docker stats` parsing needed — timing is in the Go function output.
