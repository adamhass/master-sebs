"""Shared event-sidecar parsing and lightweight metric derivations.

Minimal event envelope (JSONL, one object per line):
{
  "schema_version": "1.0",
  "run_id": "...",
  "system": "...",
  "ts_ms": 1711272000123,
  "event_type": "invoke_end",
  "ok": true,
  "function_id": "f1",            # optional
  "state_unit_id": "shard-1",     # optional
  "key_id": "user:123",           # optional
  "latency_ms": 4.2,              # optional
  "error_code": "timeout",        # optional
  "attributes": {}                 # optional extension block
}
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_event_records(run_dir: Path) -> List[Dict[str, Any]]:
    for name in ("events.jsonl", "event_log.jsonl", "runtime_events.jsonl"):
        path = run_dir / name
        if not path.exists():
            continue
        out: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return out
    return []


def validate_event_records(
    events: List[Dict[str, Any]],
    *,
    required_run_id: Optional[str] = None,
    expected_event_types: Optional[Sequence[str]] = None,
) -> List[str]:
    errors: List[str] = []
    if not events:
        return errors

    seen_types: Set[str] = set()
    for idx, e in enumerate(events):
        if not isinstance(e, dict):
            errors.append(f"event[{idx}] is not an object")
            continue
        if "event_type" not in e:
            errors.append(f"event[{idx}] missing event_type")
        else:
            seen_types.add(str(e.get("event_type")))
        if "ts_ms" not in e:
            errors.append(f"event[{idx}] missing ts_ms")
        if "ok" not in e:
            errors.append(f"event[{idx}] missing ok")
        if required_run_id is not None:
            rid = e.get("run_id")
            if not rid:
                errors.append(f"event[{idx}] missing run_id")
            elif str(rid) != str(required_run_id):
                errors.append(f"event[{idx}] run_id mismatch: {rid} != {required_run_id}")

    if expected_event_types:
        missing = [t for t in expected_event_types if t not in seen_types]
        if missing:
            errors.append(f"missing expected event types: {missing}")
    return errors


def _median(values: Iterable[float]) -> Optional[float]:
    vals = [float(v) for v in values]
    if not vals:
        return None
    return float(statistics.median(vals))


def derive_event_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        return {}

    invoke_events = [e for e in events if e.get("event_type") == "invoke_end"]
    total_invokes = len(invoke_events)
    failed = 0
    timeouts = 0

    funcs_to_state: Dict[str, Set[str]] = {}
    state_to_funcs: Dict[str, Set[str]] = {}
    key_counts: Dict[str, int] = {}

    divergence_start: Dict[str, int] = {}
    convergence_windows: List[float] = []
    stale_total = 0
    stale_hits = 0
    raw_total = 0
    raw_violations = 0

    for e in events:
        event_type = str(e.get("event_type", ""))
        ok = bool(e.get("ok"))
        if event_type == "invoke_end":
            if not ok:
                failed += 1
            err = str(e.get("error_code", "")).lower()
            if "timeout" in err:
                timeouts += 1

        fn = e.get("function_id")
        su = e.get("state_unit_id")
        if fn and su:
            funcs_to_state.setdefault(str(fn), set()).add(str(su))
            state_to_funcs.setdefault(str(su), set()).add(str(fn))

        key_id = e.get("key_id")
        if key_id is not None:
            k = str(key_id)
            key_counts[k] = key_counts.get(k, 0) + 1

        attrs = e.get("attributes", {})
        if not isinstance(attrs, dict):
            attrs = {}
        crdt = attrs.get("crdt", {})
        if not isinstance(crdt, dict):
            crdt = {}
        object_id = crdt.get("object_id") or e.get("key_id")
        ts = _safe_int(e.get("ts_ms"))
        if object_id and ts is not None:
            oid = str(object_id)
            if event_type == "crdt_divergence_detected":
                divergence_start[oid] = ts
            elif event_type == "crdt_converged" and oid in divergence_start:
                dt = ts - divergence_start[oid]
                if dt >= 0:
                    convergence_windows.append(float(dt))
                divergence_start.pop(oid, None)

        stale = attrs.get("stale_read")
        if stale is not None:
            stale_total += 1
            if bool(stale):
                stale_hits += 1

        raw_ok = attrs.get("read_after_write_ok")
        if raw_ok is not None:
            raw_total += 1
            if not bool(raw_ok):
                raw_violations += 1

    out: Dict[str, Any] = {}
    if total_invokes > 0:
        out["failed_requests"] = failed
        out["error_rate"] = failed / total_invokes
        out["timeout_rate"] = timeouts / total_invokes

    if funcs_to_state:
        out["state_units_per_function_n"] = _median(len(v) for v in funcs_to_state.values())
    if state_to_funcs:
        out["concurrent_functions_per_state_unit_n"] = _median(len(v) for v in state_to_funcs.values())
    if key_counts:
        counts = sorted(key_counts.values())
        p50 = _median(counts) or 0.0
        out["keys_count"] = len(key_counts)
        out["key_skew_ratio"] = (counts[-1] / p50) if p50 > 0 else None

    if convergence_windows:
        out["convergence_time_ms"] = _median(convergence_windows)
    if stale_total > 0:
        out["stale_read_rate"] = stale_hits / stale_total
    if raw_total > 0:
        out["read_after_write_violation_rate"] = raw_violations / raw_total

    return out


def merge_metric_overrides(target: Dict[str, Any], updates: Dict[str, Any]) -> None:
    for k, v in updates.items():
        if v is not None:
            target[k] = v
