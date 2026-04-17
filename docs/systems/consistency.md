# Consistency & Durability Guarantees

Cross-system comparison of state durability, execution durability, and consistency models.

## Summary

| System | State Durability | Execution Durability | Consistency Model | Crash Recovery |
|--------|:---:|:---:|---|---|
| Lambda + Redis | None (volatile cache) | None | Eventual | Re-invoke from scratch |
| Lambda Durable | DynamoDB (durable) | Checkpoint/replay | Strong (single-item) | Replay from last checkpoint |
| Boki | Shared log (replicated) | Log-based | Linearizable | Replay log |
| Cloudburst + Anna | Anna KVS (tunable) | None | Eventual (CRDT) | State survives, execution lost |
| Restate | Embedded KV (journal) | Journal replay | Serializable per key | Replay journal |

## State Durability

**Lambda + Redis**: ElastiCache Redis with `allkeys-lru` eviction. No persistence configured. Node restart = total state loss. State exists only as performance optimization, not source of truth.

**Lambda Durable**: DynamoDB on-demand. Durable by default — replicated across 3 AZs. State survives any single failure. Each write wrapped in `@durable_step` checkpoint for execution-level guarantees on top.

**Boki**: Shared log replicated across storage nodes. All state mutations are log entries. Engine-local cache provides fast reads (~2us) but authoritative state lives in the log. Storage node failure = recover from replicas.

**Cloudburst + Anna**: Anna KVS uses lattice-based CRDTs for conflict resolution. Tunable consistency (eventual by default). State survives executor crashes — lives in Anna, not executor memory. Multi-node Anna replicates across nodes.

**Restate**: Embedded KV backed by quorum-replicated journal (Bifrost log). State persisted per Virtual Object key. 3-node cluster with replication factor 2 — journal entries replicated to 2+ nodes before ack (quorum writes). Server crash = replay journal from replicas, reconstruct state. Tolerates 1 node failure without data loss.

## Execution Durability

**Lambda + Redis**: None. Lambda crash mid-execution = partial state (Redis write done, but no read). No replay, no compensation. Caller must retry entire invocation.

**Lambda Durable**: Checkpoint/replay via AWS Durable Execution SDK. Each `context.step()` creates checkpoint in Lambda's execution log. On crash: Lambda re-invokes handler, SDK replays from beginning, completed steps return cached results. Guarantees: completed steps never re-execute, incomplete steps retry.

**Boki**: Log-based execution tracking. All operations recorded in shared log. On engine crash: new engine replays log entries for affected functions. Guarantees: exactly-once semantics for logged operations.

**Cloudburst + Anna**: None. Executor crash = execution lost. Function state in Anna survives, but execution progress doesn't. Scheduler may re-dispatch, but from scratch — no replay.

**Restate**: Journal-based replay with quorum replication. Every handler step (state mutations, side effects, sleep) durably journaled to Bifrost log, replicated across 2+ nodes before ack. On crash: surviving nodes replay journal, handler re-executes but journaled operations return cached results. Virtual Object exclusive lock ensures no concurrent mutations during replay. Guarantees: exactly-once semantics per handler invocation. Comparable to Boki's shared log model — both use replicated append-only logs as source of truth.

## Consistency Models

**Eventual** (Lambda+Redis, Cloudburst): No ordering guarantees across concurrent operations. Redis: last-write-wins. Anna: CRDT merge (lattice join). Concurrent writers may see stale reads.

**Strong/Single-item** (Lambda Durable): DynamoDB provides strong consistency for single-item operations (`ConsistentRead=True`). Our benchmark uses single-item put/get — effectively serializable per key. Cross-item transactions require DynamoDB Transactions (not used).

**Linearizable** (Boki): Shared log provides total order on all operations. Any read reflects the most recent write in log order. Strongest guarantee — but requires log coordination (sequencer).

**Serializable per key** (Restate): Virtual Object exclusive handlers guarantee at-most-one concurrent writer per key. Within a key: fully serializable. Across keys: no ordering guarantees (independent Virtual Objects). Shared handlers allow concurrent reads but no writes.

## Thesis Implication

Lambda Durable and Restate provide equivalent durability guarantees (checkpoint/replay, durable state) but achieve them through fundamentally different architectures:

- **Lambda Durable**: external-service durability. Every checkpoint = network round-trip to AWS Checkpoint API + DynamoDB write. Cost proportional to number of durable operations.
- **Restate**: embedded durability. Every checkpoint = local journal append (disk I/O). Cost proportional to disk write speed, not network latency.

Same guarantees, ~1000x cost difference per operation. Architecture matters more than feature parity.
