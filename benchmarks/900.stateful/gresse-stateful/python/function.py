"""
REFERENCE ONLY — the deployed function lives in the sibling Gresse repo:
  examples/bench_function/main.rs

This file documents the benchmark contract for the Gresse integration.
The actual implementation is a native Rust CRDT replica that accepts
HTTP JSON requests encoded as:

    {
      "type": "Mutation",
      "params": {
        "Run": {
          "state_size_kb": 64,
          "state_key": "bench:state",
          "ops": 1
        }
      }
    }

State mechanism: in-memory CRDT state replicated between Gresse replicas,
with bootstrap and membership persisted via object storage.
Deployment: native Gresse replica process (local integration scaffold here).
Invocation: POST http://<gresse-replica>:9090/

Response format: JSON-serialized Rust enum wrapping a SeBS-compatible
payload with request_id, is_cold, begin, end, and measurement fields.
"""

raise NotImplementedError(
    "This is a reference stub. "
    "The deployed benchmark is the native Rust example in the Gresse repo "
    "(examples/bench_function/main.rs)."
)
