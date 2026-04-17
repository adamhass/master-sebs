# Programming Models

How each system exposes state operations and handler logic to developers.

## Summary

| System | Language | State API | Handler Model | Async? |
|--------|---------|-----------|--------------|:------:|
| Lambda + Redis | Python 3.12 | `redis.set()` / `redis.get()` | Event handler | No |
| Lambda Durable | Python 3.13 | `ddb.put_item()` / `ddb.get_item()` in `@durable_step` | Durable execution | No |
| Boki | Go | `BokiStore.Put()` / `BokiStore.Get()` | Registered function | No |
| Cloudburst + Anna | Python | `cloudburst.put()` / `cloudburst.get()` | Injected user_library | No |
| Restate | Python 3.13 | `ctx.set()` / `await ctx.get()` | Virtual Object handler | Yes |

## Lambda + Redis

Standard Lambda handler. Developer manages Redis connection pool, serialization, error handling.

```python
def handler(event):
    client = redis.Redis(connection_pool=pool)
    client.set(key, blob)        # explicit network call
    val = client.get(key)        # explicit network call
    return result
```

No SDK abstraction over state. Developer responsible for connection lifecycle, retry logic, serialization format. State API = raw Redis protocol.

## Lambda Durable

Wraps Lambda handler with `@durable_execution`. State operations in `@durable_step` functions — SDK checkpoints return values automatically.

```python
@durable_step
def write_state(step_ctx, key, size_kb):
    table.put_item(Item={"state_key": key, "blob": blob})
    return latency_us    # checkpointed by SDK

@durable_execution
def handler(event, context: DurableContext):
    write_lat = context.step(write_state(key, size))  # checkpointed
    read_lat = context.step(read_state(key))           # checkpointed
    # compute outside steps — no checkpoint needed
```

Developer still manages DynamoDB client. SDK adds checkpoint/replay layer. Non-deterministic code (random, time) safe inside steps (steps don't re-execute on replay). Code outside steps must be deterministic.

## Boki

Go binary registered with Boki Launcher. State via `BokiStore` API backed by shared log.

```go
store := boki.NewStore(ctx)
store.Put(key, blob)    // appended to shared log
val := store.Get(key)   // engine-cached read
```

Tightest coupling — function must be Go, compiled against Boki SDK, deployed as binary in engine container. No language flexibility. State API is log-native: writes = log appends, reads = cache lookups.

## Cloudburst + Anna

Python function with injected `user_library` (cloudburst object). Registered via scheduler, dispatched to executors.

```python
def stateful_benchmark(cloudburst, key, size_kb, ops, request_id=None):
    cloudburst.put(key, blob)     # Anna KVS write
    val = cloudburst.get(key)     # Anna KVS read
    return result
```

Simplest state API — `put`/`get` with automatic Anna routing. But function signature must match executor's injection pattern (first arg = cloudburst library). No standard handler interface.

## Restate

Async Python handler on Virtual Object. State managed by Restate SDK — developer never touches storage directly.

```python
bench = VirtualObject("statefulBench")

@bench.handler()
async def run(ctx: ObjectContext, request: dict):
    ctx.set("state_blob", blob)           # journal append (sync)
    val = await ctx.get("state_blob")     # journal read (async)
    return result
```

Highest abstraction. State API is `ctx.set()`/`ctx.get()` — no connection pool, no client library, no external service configuration. Developer writes business logic; Restate handles durability, state persistence, concurrency control (exclusive handler per key). Trade-off: async-only, must understand Virtual Object key semantics.

## Developer Experience Spectrum

```
Low abstraction                                    High abstraction
(more control)                                     (less boilerplate)
    |                                                      |
    Lambda+Redis  →  Lambda Durable  →  Boki  →  Cloudburst  →  Restate
    (raw Redis)      (DDB+checkpoint)   (Go SDK)  (put/get)     (ctx.set/get)
```

Lambda+Redis: most flexibility, most boilerplate. Restate: least boilerplate, most opinionated (Virtual Objects, async, key-based routing).
