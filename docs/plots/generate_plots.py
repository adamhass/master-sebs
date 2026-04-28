#!/usr/bin/env python3
"""
Generate thesis comparison plots for the stateful serverless systems.

Usage:
    cd master-sebs
    uv run python3 docs/plots/generate_plots.py
"""

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Paths
SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR.parent.parent / "results" / "run2"
CLOUD_RESULTS_DIR = SCRIPT_DIR.parent.parent / "results" / "cloud"
RESULTS_DIR_RUN6 = SCRIPT_DIR.parent.parent / "results" / "run6"
OUT_DIR = SCRIPT_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

POINTS_PER_INCH = 72.0
FIGURE_WIDTH_PT = 516.0
FIGURE_WIDTH_IN = FIGURE_WIDTH_PT / POINTS_PER_INCH

# Style
COLORS = {
    "Gresse": "#795548",
    "Lambda + Redis": "#FF9900",
    "Cloudburst + Anna": "#4CAF50",
    "Boki": "#2196F3",
    "Restate": "#9C27B0",
    "Lambda Durable": "#E53935",
}
SYSTEMS = [
    "Gresse",
    "Lambda + Redis",
    "Cloudburst + Anna",
    "Boki",
    "Restate",
    "Lambda Durable",
]
SYSTEM_DIRS = {
    "Lambda + Redis": "lambda",
    "Lambda Durable": "lambda-durable",
    "Boki": "boki",
    "Cloudburst + Anna": "cloudburst",
    "Restate": "restate",
    "Gresse": "gresse",
}
SHORT_NAMES = {
    "Lambda + Redis": "Lambda\nBaseline",
    "Lambda Durable": "Lambda\nDurable",
    "Boki": "Boki",
    "Cloudburst + Anna": "Cloudburst",
    "Restate": "Restate",
    "Gresse": "Gresse",
}
PLOT_1_SYSTEMS = list(SYSTEMS)
RUN6_SYSTEMS = {"Lambda Durable", "Restate", "Gresse"}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 10,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 150,
    "figure.constrained_layout.use": True,
    "savefig.bbox": None,
    "savefig.pad_inches": 0.05,
})


def scaled_figsize(width_in: float, height_in: float) -> tuple:
    """Scale an existing figure aspect to the fixed publication width."""
    scale = FIGURE_WIDTH_IN / width_in
    return (FIGURE_WIDTH_IN, height_in * scale)


def load_results(system_dir, filename):
    path = CLOUD_RESULTS_DIR / system_dir / filename
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    inv_key = "_invocations"
    invocations = list(data.get(inv_key, {}).values())
    if not invocations:
        return None
    results = list(invocations[0].values())
    duration = data.get("end_time", 0) - data.get("begin_time", 1)
    return results, duration


def load_results_run6(system_dir, filename):
    path = RESULTS_DIR_RUN6 / system_dir / filename
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    inv_key = "_invocations"
    invocations = list(data.get(inv_key, {}).values())
    if not invocations:
        return None
    results = list(invocations[0].values())
    duration = data.get("end_time", 0) - data.get("begin_time", 1)
    return results, duration


def _load(name, filename):
    """Load primary comparison results for a system."""
    sdir = SYSTEM_DIRS[name]
    return load_results(sdir, filename)


def _is_warm(r):
    """Return True if invocation is not a cold start and not a failure."""
    if r.get("stats", {}).get("failure"):
        return False
    if r.get("stats", {}).get("cold_start"):
        return False
    if r.get("output", {}).get("is_cold"):
        return False
    return True


def extract_client_latencies(results, warm_only=True):
    if warm_only:
        return [r["times"]["client"] / 1000 for r in results if _is_warm(r)]
    return [r["times"]["client"] / 1000 for r in results if not r.get("stats", {}).get("failure")]


def extract_write_latencies(results, warm_only=True):
    filt = (r for r in results if "measurement" in r.get("output", {}))
    if warm_only:
        filt = (r for r in filt if _is_warm(r))
    return [r["output"]["measurement"]["state_write_lat_us"] for r in filt]


def extract_read_latencies(results, warm_only=True):
    filt = (r for r in results if "measurement" in r.get("output", {}))
    if warm_only:
        filt = (r for r in filt if _is_warm(r))
    return [r["output"]["measurement"]["state_read_lat_us"] for r in filt]


# ── Plot 1: Throughput Scaling Curve ──

def plot_throughput_scaling():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    concurrencies = [1, 10, 50, 100]

    for name in PLOT_1_SYSTEMS:
        throughputs = []
        concs_available = []
        for c in concurrencies:
            data = _load(name, f"throughput-c{c}.json")
            if data:
                results, duration = data
                valid = [r for r in results if not r.get("stats", {}).get("failure")]
                tp = len(valid) / duration if duration > 0 else 0
                throughputs.append(tp)
                concs_available.append(c)
        if concs_available:
            ax.plot(concs_available, throughputs, "o-", color=COLORS[name], label=name,
                    linewidth=2, markersize=7)

    ax.set_xlabel("Concurrency (number of parallel invocations)")
    ax.set_ylabel("Throughput (invocations/sec)")
    ax.set_title("Throughput Scaling (64KB state)")
    ax.set_xlim(0, 105)
    ax.set_xticks(concurrencies)
    ax.set_autoscale_on(False)
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.text(0.5, -0.02,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "01_throughput_scaling.png")
    plt.close(fig)
    print("  01_throughput_scaling.png")


# ── Plot 2: Latency CDF ──

def plot_latency_cdf():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))

    for name in SYSTEMS:
        data = _load(name, "latency-dist.json")
        if not data:
            continue
        results, _ = data
        lats = sorted(extract_client_latencies(results))
        percentiles = np.arange(1, len(lats) + 1) / len(lats) * 100
        ax.plot(lats, percentiles, color=COLORS[name], label=name, linewidth=1.5)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("Percentile (%)")
    ax.set_title("Latency Distribution (CDF)")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, -0.02,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "02_latency_cdf.png")
    plt.close(fig)
    print("  02_latency_cdf.png")


# ── Plot 3: Latency Percentiles (Grouped Bar) ──

def plot_latency_percentiles():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    percentile_labels = ["P50", "P95", "P99"]
    percentile_vals = [50, 95, 99]
    x = np.arange(len(percentile_labels))
    width = 0.25

    active = []
    for name in SYSTEMS:
        data = _load(name, "latency-dist.json")
        if not data:
            continue
        active.append((name, data))

    width = 0.8 / max(len(active), 1)
    for i, (name, data) in enumerate(active):
        results, _ = data
        lats = sorted(extract_client_latencies(results))
        n = len(lats)
        vals = [lats[min(int(p / 100 * n), n - 1)] for p in percentile_vals]
        ax.bar(x + i * width, vals, width, label=name, color=COLORS[name])

    ax.set_xlabel("Percentile")
    ax.set_ylabel("Client Latency (ms)")
    ax.set_title("Client Latency Percentiles (64KB state)")
    ax.set_xticks(x + width * max(len(active) - 1, 0) / 2)
    ax.set_xticklabels(percentile_labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.savefig(OUT_DIR / "03_latency_percentiles.png")
    plt.close(fig)
    print("  03_latency_percentiles.png")


# ── Plot 4: Write vs Read Latency Breakdown ──

def plot_write_read_breakdown():
    fig, ax = plt.subplots(figsize=scaled_figsize(8, 4.5))

    active_systems = []
    writes = []
    reads = []
    for name in SYSTEMS:
        data = _load(name, "latency-dist.json")
        if not data:
            continue
        results, _ = data
        wl = sorted(extract_write_latencies(results))
        rl = sorted(extract_read_latencies(results))
        if not wl or not rl:
            continue
        active_systems.append(name)
        writes.append(wl[len(wl) // 2] / 1000)  # us -> ms
        reads.append(rl[len(rl) // 2] / 1000)

    x = np.arange(len(active_systems))
    width = 0.35

    bars1 = ax.bar(x - width / 2, writes, width, label="Write P50",
                   color=[COLORS[s] for s in active_systems], alpha=0.9)
    bars2 = ax.bar(x + width / 2, reads, width, label="Read P50",
                   color=[COLORS[s] for s in active_systems], alpha=0.5, hatch="//")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("State Write vs Read Latency (P50, 64KB)")
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT_NAMES[s] for s in active_systems], fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # Add value labels — show us for very small values
    for bar, raw_us in zip(bars1, [w * 1000 for w in writes]):
        h = bar.get_height()
        label = f"{h:.1f}ms" if h >= 0.1 else f"{raw_us:.0f}us"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar, raw_us in zip(bars2, [r * 1000 for r in reads]):
        h = bar.get_height()
        label = f"{h:.1f}ms" if h >= 0.1 else f"{raw_us:.0f}us*"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    # Caveat footnote for Boki read
    ax.annotate("* Engine-cached read latency.",
                xy=(0.5, -0.15), xycoords="axes fraction", ha="center", fontsize=7,
                style="italic", color="gray")

    fig.savefig(OUT_DIR / "04_write_read_breakdown.png")
    plt.close(fig)
    print("  04_write_read_breakdown.png")


# ── Plot 5: State Size Impact ──

def plot_state_size_impact():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    sizes = [1, 64, 512]
    size_files = {1: "statesize-1kb.json", 64: "statesize-64kb.json", 512: "statesize-512kb.json"}

    for name in SYSTEMS:
        write_p50s = []
        sizes_available = []
        for sz in sizes:
            data = _load(name, size_files[sz])
            if not data:
                continue
            results, _ = data
            wl = sorted(extract_write_latencies(results))
            if not wl:
                continue
            write_p50s.append(wl[len(wl) // 2] / 1000)  # us -> ms
            sizes_available.append(sz)
        if sizes_available:
            ax.plot(sizes_available, write_p50s, "o-", color=COLORS[name], label=name,
                    linewidth=2, markersize=7)

    ax.set_xlabel("State Size (KB)")
    ax.set_ylabel("Write Latency P50 (ms)")
    ax.set_title("State Size Impact on Write Latency")
    ax.set_xscale("log")
    ax.set_xticks(sizes)
    ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, -0.02,
             "Lambda Durable external storage (DynamoDB) disallows state >400KB.",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "05_state_size_impact.png")
    plt.close(fig)
    print("  05_state_size_impact.png")


# ── Plot 6: Cold Start Comparison ──

def plot_cold_start():
    fig, ax = plt.subplots(figsize=scaled_figsize(6, 4))

    # Only Lambda systems have per-invocation cold starts.
    # Boki/Cloudburst/Restate are persistent processes — one-time infrastructure
    # bootstrap, not comparable to per-invocation container provisioning.

    # Lambda baseline: extract cold starts from latency-dist data
    lambda_cold = []
    data = load_results("lambda", "latency-dist.json")
    if data:
        results, _ = data
        for r in results:
            if r.get("stats", {}).get("cold_start"):
                lambda_cold.append(r["times"]["client"] / 1000)

    # Lambda Durable: extract cold starts from run6 latency-dist
    durable_cold = []
    durable_data = load_results_run6("lambda-durable", "latency-dist.json")
    if durable_data:
        results, _ = durable_data
        for r in results:
            if r.get("stats", {}).get("cold_start") or r.get("output", {}).get("is_cold"):
                durable_cold.append(r["times"]["client"] / 1000)

    labels = []
    values = []
    colors = []

    if lambda_cold:
        labels.append("Lambda Baseline\n(container init)")
        values.append(np.median(lambda_cold))
        colors.append(COLORS["Lambda + Redis"])
    if durable_cold:
        labels.append("Lambda Durable\n(container + SDK init)")
        values.append(np.median(durable_cold))
        colors.append(COLORS["Lambda Durable"])

    bars = ax.bar(labels, values, color=colors, width=0.4)
    ax.set_ylabel("Cold Start Latency (ms)")
    ax.set_title("Per-Invocation Cold Start Latency")
    ax.grid(True, alpha=0.3, axis="y")

    for bar, val in zip(bars, values):
        label = f"{val:.0f}ms" if val < 10000 else f"{val/1000:.0f}s"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)

    fig.savefig(OUT_DIR / "06_cold_start.png")
    plt.close(fig)
    print("  06_cold_start.png")


# ── Plot 7: Cost per Invocation ──

def plot_cost():
    fig, ax = plt.subplots(figsize=scaled_figsize(6, 4))

    lambda_per_invoke = 0.0000166667  # per GB-second, 256MB = 0.25GB
    costs = {}

    # Lambda + Redis: use median execution time from throughput-c10
    lambda_data = load_results("lambda", "throughput-c10.json")
    if lambda_data:
        results, _ = lambda_data
        exec_times = [r["times"]["client"] / 1e6 for r in results if not r.get("stats", {}).get("failure")]
        median_exec_s = sorted(exec_times)[len(exec_times) // 2]
        lambda_cost_per_invoke = median_exec_s * 0.25 * lambda_per_invoke  # GB-seconds * price
        costs["Lambda + Redis"] = lambda_cost_per_invoke * 1000

    # Lambda Durable: same pricing model, data from run6
    lambda_dur_data = load_results_run6("lambda-durable", "throughput-c10.json")
    if lambda_dur_data:
        results, _ = lambda_dur_data
        exec_times = [r["times"]["client"] / 1e6 for r in results if not r.get("stats", {}).get("failure")]
        median_exec_s = sorted(exec_times)[len(exec_times) // 2]
        lambda_cost_per_invoke = median_exec_s * 0.25 * lambda_per_invoke
        costs["Lambda Durable"] = lambda_cost_per_invoke * 1000

    if not costs:
        print("  07_cost_per_invocation.png -- SKIPPED (no data)")
        return

    labels = list(costs.keys())
    vals = [costs[l] for l in labels]
    bar_colors = [COLORS[l] for l in labels]

    bars = ax.bar(labels, vals, color=bar_colors, width=0.5)
    ax.set_ylabel("Cost per 1000 Invocations (USD)")
    ax.set_title("Cost per Unit Work — Lambda Variants (concurrency = 10)")
    ax.grid(True, alpha=0.3, axis="y")

    for bar, val in zip(bars, vals):
        ax.annotate(f"${val:.4f}", xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)

    fig.savefig(OUT_DIR / "07_cost_per_invocation.png")
    plt.close(fig)
    print("  07_cost_per_invocation.png")


# ── Plot 8: Resource Usage During Experiment ──

def plot_resource_usage():
    csv_path = RESULTS_DIR / "cloudwatch_metrics.csv"
    if not csv_path.exists():
        print("  08_resource_usage.png — SKIPPED (no cloudwatch_metrics.csv)")
        return

    import csv
    from datetime import datetime

    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("  08_resource_usage.png — SKIPPED (empty CSV)")
        return

    # Group by instance, use friendly names
    instances = {}
    for row in rows:
        iid = row["instance_name"] if row["instance_name"] != row["instance_id"] else row["instance_id"][:12]
        if iid not in instances:
            instances[iid] = {"cpu": [], "mem": []}
        metric = row["metric"]
        ts = row["timestamp"]
        val = float(row["value"])
        if metric == "cpu_usage_user":
            instances[iid]["cpu"].append((ts, val))
        elif metric == "mem_used_percent":
            instances[iid]["mem"].append((ts, val))

    # Select key instances: one per role
    priority = ["boki-infra", "boki-engine-1", "boki-engine-2",
                "cb-scheduler", "cb-anna", "cb-executor-1", "cb-executor-2", "cb-executor-3",
                "cb-client"]
    selected = [iid for iid in priority if iid in instances][:6]
    # Add any unnamed ones if we have space
    for iid in instances:
        if iid not in selected and len(selected) < 6:
            selected.append(iid)

    if not selected:
        print("  08_resource_usage.png — SKIPPED (no instances)")
        return

    # Distinct colors per instance — contrasting within each system group
    INSTANCE_COLORS = {
        "boki-infra":    "#1565C0",  # dark blue
        "boki-engine-1": "#42A5F5",  # medium blue
        "boki-engine-2": "#90CAF9",  # light blue
        "cb-scheduler":  "#2E7D32",  # dark green
        "cb-anna":       "#E65100",  # dark orange (stands out from green)
        "cb-executor-1": "#66BB6A",  # medium green
        "cb-executor-2": "#A5D6A7",  # light green
        "cb-executor-3": "#C8E6C9",  # very light green
        "cb-client":     "#FFC107",  # amber
    }

    def get_color(iid):
        return INSTANCE_COLORS.get(iid, "#999999")

    fig, axes = plt.subplots(2, 1, figsize=scaled_figsize(10, 6), sharex=True)

    for iid in selected:
        color = get_color(iid)
        ls = "-" if "infra" in iid or "scheduler" in iid or "anna" in iid else "--"

        cpu_data = sorted(instances[iid]["cpu"], key=lambda x: x[0])
        mem_data = sorted(instances[iid]["mem"], key=lambda x: x[0])

        if cpu_data:
            times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _ in cpu_data]
            vals = [v for _, v in cpu_data]
            axes[0].plot(times, vals, label=iid, linewidth=1.2, alpha=0.8, color=color, linestyle=ls)

        if mem_data:
            times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _ in mem_data]
            vals = [v for _, v in mem_data]
            axes[1].plot(times, vals, label=iid, linewidth=1.2, alpha=0.8, color=color, linestyle=ls)

    axes[0].set_ylabel("CPU User (%)")
    axes[0].set_title("Resource Usage over time (Boki = blue, Cloudburst = green)")
    axes[0].legend(fontsize=7, loc="upper right", ncol=2)
    axes[0].grid(True, alpha=0.3)

    axes[1].set_ylabel("Memory Used (%)")
    axes[1].set_xlabel("Time")
    axes[1].legend(fontsize=7, loc="upper right", ncol=2)
    axes[1].grid(True, alpha=0.3)

    for label in axes[1].get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment("right")
    fig.savefig(OUT_DIR / "08_resource_usage.png")
    plt.close(fig)
    print("  08_resource_usage.png")


# ── Plot 9: State Placement Impact ──

def plot_state_placement():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))

    experiments = [
        ("Same key\n(1 Anna node)", "placement-same-key.json"),
        ("Unique keys\n(1 Anna node)", "placement-unique-keys.json"),
        ("Same key\n(2 Anna nodes)", "placement-same-key-multinode.json"),
        ("Unique keys\n(2 Anna nodes)", "placement-unique-keys-multinode.json"),
    ]

    labels = []
    write_vals = []
    read_vals = []

    for label, filename in experiments:
        data = load_results("cloudburst", filename)
        if not data:
            continue
        results, _ = data
        wl = sorted(extract_write_latencies(results))
        rl = sorted(extract_read_latencies(results))
        labels.append(label)
        write_vals.append(wl[len(wl) // 2] / 1000)
        read_vals.append(rl[len(rl) // 2] / 1000)

    if not labels:
        print("  09_state_placement.png — SKIPPED (no data)")
        return

    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width / 2, write_vals, width, label="Write P50",
                   color=COLORS["Cloudburst + Anna"], alpha=0.9)
    bars2 = ax.bar(x + width / 2, read_vals, width, label="Read P50",
                   color=COLORS["Cloudburst + Anna"], alpha=0.5, hatch="//")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("State Placement Impact — Cloudburst + Anna KVS")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for bar in bars1:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    ax.annotate("No significant difference — Cloudburst does not cache state on executors.\n"
                "Co-location requires Anna replica placement near executors (not implemented).",
                xy=(0.5, -0.22), xycoords="axes fraction", ha="center", fontsize=7,
                style="italic", color="gray")

    fig.savefig(OUT_DIR / "09_state_placement.png")
    plt.close(fig)
    print("  09_state_placement.png")


# ── Plot 10: Scaling Timeline (Cloudburst) ──
#
# Boki scaling timeline was dropped because:
# 1. The shell-based load generator produced sparse, bursty data (10 points per batch with
#    long gaps) compared to the Python continuous generator used for Cloudburst (7020 even points)
# 2. Boki's ZK discovery lifecycle prevents clean restarts — after any infra restart, engines
#    register with ZK but the gateway never discovers them (cmd/start is one-shot). This made
#    it impossible to produce a clean scaling test on the redeployed cluster.
# 3. Boki scaling was validated in run_2 (boki_scaling_up_c10.csv) showing no latency disruption,
#    but that data is not suitable for a thesis figure due to the sparse "before" phase.
#
# The Cloudburst plot below is the primary scaling timeline figure for the thesis.

def plot_scaling_timeline_cb():
    import csv

    csv_path = RESULTS_DIR / "cloudburst_scaling_timeline.csv"
    if not csv_path.exists():
        print("  11_scaling_cloudburst.png — SKIPPED")
        return

    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("  11_scaling_cloudburst.png — SKIPPED (empty)")
        return

    timestamps = [int(row["timestamp_ms"]) for row in rows]
    latencies = [int(row["latency_ms"]) for row in rows]
    phases = [row["phase"] for row in rows]

    t0 = min(timestamps)
    elapsed_s = [(t - t0) / 1000 for t in timestamps]

    scale_time = None
    for i, phase in enumerate(phases):
        if phase == "after" and (i == 0 or phases[i - 1] == "before"):
            scale_time = elapsed_s[i]
            break

    fig, axes = plt.subplots(3, 1, figsize=scaled_figsize(10, 7), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1.5, 1]})

    # Throughput
    window = 5
    if len(elapsed_s) > window:
        tp_times = []
        tp_vals = []
        for i in range(window, len(elapsed_s)):
            dt = elapsed_s[i] - elapsed_s[i - window]
            if dt > 0:
                tp_times.append(elapsed_s[i])
                tp_vals.append(window / dt)
        axes[0].plot(tp_times, tp_vals, color=COLORS["Cloudburst + Anna"], linewidth=1)
    axes[0].set_ylabel("Throughput\n(inv/s)")
    axes[0].set_title("Cloudburst Manual Scale-Up (2→3 executors, c=5)")
    axes[0].grid(True, alpha=0.3)

    # Latency scatter
    before_t = [t for t, p in zip(elapsed_s, phases) if p == "before"]
    before_l = [l for l, p in zip(latencies, phases) if p == "before"]
    after_t = [t for t, p in zip(elapsed_s, phases) if p == "after"]
    after_l = [l for l, p in zip(latencies, phases) if p == "after"]

    axes[1].scatter(before_t, before_l, s=8, alpha=0.5, color=COLORS["Cloudburst + Anna"], label="Before scale")
    axes[1].scatter(after_t, after_l, s=8, alpha=0.5, color="#FF9900", label="After scale")
    axes[1].set_ylabel("Latency (ms)")
    axes[1].set_yscale("log")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Instance count
    axes[2].step([0, scale_time or 120, max(elapsed_s)],
                 [2, 3, 3], where="post", color=COLORS["Cloudburst + Anna"], linewidth=2)
    axes[2].set_ylabel("Executor\ncount")
    axes[2].set_xlabel("Time (seconds)")
    axes[2].set_ylim(0.5, 4.5)
    axes[2].set_yticks([1, 2, 3, 4])
    axes[2].grid(True, alpha=0.3)

    if scale_time:
        for ax in axes:
            ax.axvline(x=scale_time, color="red", linestyle="--", alpha=0.7, linewidth=1)
        axes[0].annotate("Scale event", xy=(scale_time, 0.95), xycoords=("data", "axes fraction"),
                         fontsize=8, color="red", ha="left", va="top",
                         xytext=(5, 0), textcoords="offset points")

    fig.savefig(OUT_DIR / "10_scaling_timeline.png")
    plt.close(fig)
    print("  10_scaling_timeline.png")


# ── Plot 13: Latency CDF — Cloud ──

def plot_latency_cdf_cloud():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        path = CLOUD_RESULTS_DIR / sdir / "latency-dist.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        inv_key = "_invocations"
        invocations = list(data.get(inv_key, {}).values())
        if not invocations:
            continue
        results = list(invocations[0].values())
        lats = sorted(extract_client_latencies(results))
        percentiles = np.arange(1, len(lats) + 1) / len(lats) * 100
        ax.plot(lats, percentiles, color=COLORS[name], label=name, linewidth=1.5)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("Percentile (%)")
    ax.set_title("Latency Distribution (CDF)")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, -0.02,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "13_latency_cdf_cloud.png")
    plt.close(fig)
    print("  13_latency_cdf_cloud.png")


# ── Plot 12: Throughput Scaling — Cloud ──

def plot_throughput_scaling_cloud():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    concurrencies = [1, 10, 50, 100]

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        throughputs = []
        concs_available = []
        for c in concurrencies:
            path = CLOUD_RESULTS_DIR / sdir / f"throughput-c{c}.json"
            if not path.exists():
                continue
            with open(path) as f:
                data = json.load(f)
            inv_key = "_invocations"
            invocations = list(data.get(inv_key, {}).values())
            if not invocations:
                continue
            results = list(invocations[0].values())
            duration = data.get("end_time", 0) - data.get("begin_time", 1)
            valid = [r for r in results if not r.get("stats", {}).get("failure")]
            tp = len(valid) / duration if duration > 0 else 0
            throughputs.append(tp)
            concs_available.append(c)
        if concs_available:
            ax.plot(concs_available, throughputs, "o-", color=COLORS[name], label=name,
                    linewidth=2, markersize=7)

    ax.set_xlabel("Concurrency (number of parallel invocations)")
    ax.set_ylabel("Throughput (invocations/sec)")
    ax.set_title("Throughput Scaling (64KB state)")
    ax.set_xlim(0, 105)
    ax.set_xticks(concurrencies)
    ax.set_autoscale_on(False)
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.text(0.5, -0.02,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "12_throughput_scaling_cloud.png")
    plt.close(fig)
    print("  12_throughput_scaling_cloud.png")


# ── Plot 11: Latency Decomposition — Edge vs Cloud ──

def plot_latency_decomposition():
    """Stacked bar chart decomposing client latency into Network RTT,
    serverless overhead, and function execution for each system."""

    def decompose(results_dir, system_dir, percentile=50):
        """Extract decomposition at a given percentile from latency-dist.json."""
        data_path = results_dir / system_dir / "latency-dist.json"
        if not data_path.exists():
            return None
        with open(data_path) as f:
            data = json.load(f)
        inv_key = "_invocations"
        invocations = list(data.get(inv_key, {}).values())
        if not invocations:
            return None
        results = list(invocations[0].values())

        # Filter warm invocations
        warm = [r for r in results
                if not r.get("stats", {}).get("cold_start")
                and not r.get("stats", {}).get("failure")]
        if not warm:
            return None

        clients = sorted([r["times"]["client"] / 1000 for r in warm])
        benchmarks = sorted([r["times"]["benchmark"] / 1000 for r in warm])
        rtts = sorted([r["times"]["http_startup"] * 1000 for r in warm])

        n = len(clients)
        pick = lambda vals: vals[min(int(percentile / 100 * n), n - 1)]

        client_val = pick(clients)
        func_val = pick(benchmarks)
        rtt_val = pick(rtts)
        overhead_val = max(0, client_val - func_val - rtt_val)

        return {
            "client": client_val,
            "rtt": rtt_val,
            "function": func_val,
            "overhead": overhead_val,
            "count": n,
        }

    def _build_decomposition_plot(ax, systems_data, percentile_label, ylabel,
                                   plot_order=None):
        """Shared logic for decomposition stacked bar charts."""
        if plot_order is None:
            plot_order = ["Gresse", "Lambda + Redis", "Cloudburst + Anna", "Boki", "Restate", "Lambda Durable"]

        bar_labels = []
        rtt_vals = []
        overhead_vals = []
        func_vals = []
        bar_colors = []

        for name in plot_order:
            d = systems_data.get(name)
            if not d:
                continue
            bar_labels.append(SHORT_NAMES[name])
            rtt_vals.append(d["rtt"])
            overhead_vals.append(d["overhead"])
            func_vals.append(d["function"])
            bar_colors.append(COLORS[name])

        positions = np.arange(len(bar_labels))

        width = 0.7

        ax.bar(positions, overhead_vals, width, label="Serverless overhead",
               color=bar_colors, alpha=0.5, hatch="//", edgecolor="white", linewidth=0.5)
        ax.bar(positions, func_vals, width, bottom=overhead_vals,
               label="Function execution",
               color=bar_colors, alpha=0.9, edgecolor="white", linewidth=0.5)
        ax.bar(positions, rtt_vals, width,
               bottom=[o + f for o, f in zip(overhead_vals, func_vals)],
               label="Network RTT",
               color=bar_colors, alpha=0.25, hatch="...", edgecolor="white", linewidth=0.5)

        for i, (p, rtt, oh, fn) in enumerate(zip(positions, rtt_vals, overhead_vals, func_vals)):
            total = rtt + oh + fn
            ax.annotate(f"{total:.1f}ms", xy=(p, total), xytext=(0, 4),
                        textcoords="offset points", ha="center", fontsize=8, fontweight="bold")

        ax.set_ylabel(ylabel)
        ax.set_xticks(positions)
        ax.set_xticklabels(bar_labels, fontsize=9)

        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#888888", alpha=0.5, hatch="//", label="Serverless overhead"),
            Patch(facecolor="#888888", alpha=0.9, label="Function execution"),
            Patch(facecolor="#888888", alpha=0.25, hatch="...", label="Network RTT"),
        ]
        ax.legend(handles=legend_elements, loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")

    systems_p50 = {}
    for name, sdir in SYSTEM_DIRS.items():
        d = decompose(CLOUD_RESULTS_DIR, sdir, percentile=50)
        if d:
            systems_p50[name] = d

    if not systems_p50:
        print("  11_latency_decomposition.png — SKIPPED (missing data)")
        return

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p50, "P50",
                              "Client Latency P50 (ms)")
    ax.set_title("Latency Decomposition (P50)")
    fig.savefig(OUT_DIR / "11_latency_decomposition.png")
    plt.close(fig)
    print("  11_latency_decomposition.png")

    systems_p95 = {}
    for name, sdir in SYSTEM_DIRS.items():
        d = decompose(CLOUD_RESULTS_DIR, sdir, percentile=95)
        if d:
            systems_p95[name] = d

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p95, "P95",
                              "Client Latency P95 (ms)")
    ax.set_title("Latency Decomposition (P95)")
    fig.savefig(OUT_DIR / "14_latency_decomposition_p95.png")
    plt.close(fig)
    print("  14_latency_decomposition_p95.png")

    # ── Plot 18: P50 without Lambda Durable (zoom into other systems) ──
    no_durable = ["Gresse", "Lambda + Redis", "Cloudburst + Anna", "Boki", "Restate"]

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p50, "P50",
                              "Client Latency P50 (ms)", plot_order=no_durable)
    ax.set_title("Latency Decomposition (P50) — Excluding Lambda Durable")
    fig.savefig(OUT_DIR / "18_latency_decomp_no_durable_p50.png")
    plt.close(fig)
    print("  18_latency_decomp_no_durable_p50.png")

    # ── Plot 19: P95 without Lambda Durable ──
    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p95, "P95",
                              "Client Latency P95 (ms)", plot_order=no_durable)
    ax.set_title("Latency Decomposition (P95) — Excluding Lambda Durable")
    fig.savefig(OUT_DIR / "19_latency_decomp_no_durable_p95.png")
    plt.close(fig)
    print("  19_latency_decomp_no_durable_p95.png")

    # ── Plot 28: P95 without Cloudburst ──
    no_cloudburst = ["Gresse", "Lambda + Redis", "Boki", "Restate", "Lambda Durable"]

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p95, "P95",
                              "Client Latency P95 (ms)", plot_order=no_cloudburst)
    ax.set_title("Latency Decomposition (P95) — Excluding Cloudburst")
    fig.savefig(OUT_DIR / "28_latency_decomp_p95_no_cloudburst.png")
    plt.close(fig)
    print("  28_latency_decomp_p95_no_cloudburst.png")

    # ── Plot 29: P95 without Cloudburst and without Lambda Durable ──
    core_only = ["Gresse", "Lambda + Redis", "Boki", "Restate"]

    fig, ax = plt.subplots(figsize=scaled_figsize(8, 5.5))
    _build_decomposition_plot(ax, systems_p95, "P95",
                              "Client Latency P95 (ms)", plot_order=core_only)
    ax.set_title("Latency Decomposition (P95) — Excl. Cloudburst \& Durable")
    fig.savefig(OUT_DIR / "29_latency_decomp_p95_core.png")
    plt.close(fig)
    print("  29_latency_decomp_p95_core.png")

    # ── Plot 30: P50 without Cloudburst and without Lambda Durable ──
    fig, ax = plt.subplots(figsize=scaled_figsize(8, 5.5))
    _build_decomposition_plot(ax, systems_p50, "P50",
                              "Client Latency P50 (ms)", plot_order=core_only)
    ax.set_title("Latency Decomposition (P50) — Excl. Cloudburst \& Durable")
    fig.savefig(OUT_DIR / "30_latency_decomp_p50_core.png")
    plt.close(fig)
    print("  30_latency_decomp_p50_core.png")

    # ── Plot 31: P50 without Cloudburst (includes Durable) ──
    no_cloudburst_p50 = ["Gresse", "Lambda + Redis", "Boki", "Restate", "Lambda Durable"]

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))
    _build_decomposition_plot(ax, systems_p50, "P50",
                              "Client Latency P50 (ms)", plot_order=no_cloudburst_p50)
    ax.set_title("Latency Decomposition (P50) — Excluding Cloudburst")
    fig.savefig(OUT_DIR / "31_latency_decomp_p50_no_cloudburst.png")
    plt.close(fig)
    print("  31_latency_decomp_p50_no_cloudburst.png")


# ── Plot 15: Write vs Read P95 Breakdown ──

def plot_write_read_p95():
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    active_systems = []
    writes = []
    reads = []
    width = 0.35

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        path = CLOUD_RESULTS_DIR / sdir / "latency-dist.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            continue
        results = list(invocations[0].values())
        wl = sorted(extract_write_latencies(results))
        rl = sorted(extract_read_latencies(results))
        if not wl or not rl:
            continue
        n = len(wl)
        p95_idx = min(int(0.95 * n), n - 1)
        active_systems.append(name)
        writes.append(wl[p95_idx] / 1000)
        reads.append(rl[p95_idx] / 1000)

    x = np.arange(len(active_systems))
    bars1 = ax.bar(x - width / 2, writes, width, label="Write P95",
                   color=[COLORS[s] for s in active_systems], alpha=0.9)
    bars2 = ax.bar(x + width / 2, reads, width, label="Read P95",
                   color=[COLORS[s] for s in active_systems], alpha=0.5, hatch="//")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("State Write vs Read (P95)")
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT_NAMES[s] for s in active_systems], fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    for bar, raw_us in zip(bars1, [w * 1000 for w in writes]):
        h = bar.get_height()
        label = f"{h:.1f}" if h >= 0.1 else f"{raw_us:.0f}us"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    for bar, raw_us in zip(bars2, [r * 1000 for r in reads]):
        h = bar.get_height()
        label = f"{h:.1f}" if h >= 0.1 else f"{raw_us:.0f}us*"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)

    fig.savefig(OUT_DIR / "15_write_read_p95.png")
    plt.close(fig)
    print("  15_write_read_p95.png")


# ── Plot 16: Latency Scatter (wallclock vs latency) ──

def plot_latency_scatter():
    """Scatter: x=wallclock time, y=latency per invocation. Shows stability,
    bimodality (cold starts), variance over time."""
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        path = CLOUD_RESULTS_DIR / sdir / "latency-dist.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            continue
        results = list(invocations[0].values())

        points = []
        for r in results:
            begin = r.get("output", {}).get("begin", 0)
            client_ms = r["times"]["client"] / 1000
            cold = r.get("stats", {}).get("cold_start", False)
            if begin > 0:
                points.append((begin, client_ms, cold))

        if not points:
            continue

        t0 = min(p[0] for p in points)
        elapsed = [(p[0] - t0) for p in points]
        lats = [p[1] for p in points]
        colds = [p[2] for p in points]

        elapsed, lats, colds = zip(*[
            (t, l, c) for t, l, c in zip(elapsed, lats, colds) if t <= 10
        ]) if any(t <= 10 for t in elapsed) else ([], [], [])

        warm_t = [t for t, l, c in zip(elapsed, lats, colds) if not c]
        warm_l = [l for t, l, c in zip(elapsed, lats, colds) if not c]
        ax.scatter(warm_t, warm_l, s=6, alpha=0.4, color=COLORS[name], label=name)

        cold_t = [t for t, l, c in zip(elapsed, lats, colds) if c]
        cold_l = [l for t, l, c in zip(elapsed, lats, colds) if c]
        if cold_t:
            ax.scatter(cold_t, cold_l, s=30, alpha=0.9, color=COLORS[name],
                      marker="x", linewidths=1.5, label=f"{name} (cold)")

    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Client Latency (ms)")
    ax.set_title("Latency over Time")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1, top=10000)
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.3)

    fig.text(0.5, -0.02,
             "Boki and Lambda complete 1000 invocations before the 10s cutoff.",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "16_latency_scatter_10s.png")
    plt.close(fig)
    print("  16_latency_scatter_10s.png")


def _plot_scatter_subset(subset_systems, filename, title_tag, cutoff_s=10):
    """Scatter plot for a subset of systems."""
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    for name in subset_systems:
        sdir = SYSTEM_DIRS[name]
        path = CLOUD_RESULTS_DIR / sdir / "latency-dist.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            continue
        results = list(invocations[0].values())

        points = []
        for r in results:
            begin = r.get("output", {}).get("begin", 0)
            client_ms = r["times"]["client"] / 1000
            cold = r.get("stats", {}).get("cold_start", False)
            if begin > 0:
                points.append((begin, client_ms, cold))

        if not points:
            continue

        t0 = min(p[0] for p in points)
        elapsed = [(p[0] - t0) for p in points]
        lats = [p[1] for p in points]
        colds = [p[2] for p in points]

        elapsed, lats, colds = zip(*[
            (t, l, c) for t, l, c in zip(elapsed, lats, colds) if t <= cutoff_s
        ]) if any(t <= cutoff_s for t in elapsed) else ([], [], [])

        warm_t = [t for t, l, c in zip(elapsed, lats, colds) if not c]
        warm_l = [l for t, l, c in zip(elapsed, lats, colds) if not c]
        ax.scatter(warm_t, warm_l, s=6, alpha=0.4, color=COLORS[name], label=name)

        cold_t = [t for t, l, c in zip(elapsed, lats, colds) if c]
        cold_l = [l for t, l, c in zip(elapsed, lats, colds) if c]
        if cold_t:
            ax.scatter(cold_t, cold_l, s=30, alpha=0.9, color=COLORS[name],
                      marker="x", linewidths=1.5, label=f"{name} (cold)")

    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Client Latency (ms)")
    ax.set_title(title_tag)
    ax.set_yscale("log")
    ax.set_ylim(bottom=1, top=10000)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    fig.savefig(OUT_DIR / filename)
    plt.close(fig)
    print(f"  {filename}")


def plot_scatter_boki_lambda():
    _plot_scatter_subset(
        ["Lambda + Redis", "Boki"],
        "22_scatter_boki_lambda.png",
        "Latency Scatter — Lambda Baseline & Boki")


def plot_scatter_others():
    _plot_scatter_subset(
        ["Lambda Durable", "Cloudburst + Anna", "Restate"],
        "23_scatter_durable_cloudburst_restate.png",
        "Latency Scatter — Lambda Durable, Cloudburst, Restate",
        cutoff_s=15)


# ── Plot 24: Temporal Variance (5 rounds, error bars) ──

def plot_temporal_variance():
    """P50 latency across 5 temporal rounds with min-max error bars.
    Shows system stability over time (10-hour span, 2hr intervals)."""
    TEMPORAL_DIR = SCRIPT_DIR.parent.parent / "results" / "temporal"

    system_files = {
        "Lambda + Redis": "lambda-latency-dist.json",
        "Lambda Durable": "durable-latency-dist.json",
        "Boki": "boki-latency-dist.json",
        "Cloudburst + Anna": "cloudburst-latency-dist.json",
        "Restate": "restate-latency-dist.json",
    }

    fig, axes = plt.subplots(1, 2, figsize=scaled_figsize(14, 5))

    # Left: P50 per round (scatter with lines)
    ax = axes[0]
    for name, fname in system_files.items():
        round_p50s = []
        round_nums = []
        for r in range(1, 6):
            path = TEMPORAL_DIR / f"round_{r}" / fname
            if not path.exists():
                continue
            with open(path) as f:
                data = json.load(f)
            inv = list(list(data.get("_invocations", {}).values())[0].values())
            warm = [i for i in inv if _is_warm(i)]
            if len(warm) < 10:
                continue
            lats = sorted([i["times"]["client"] / 1000 for i in warm])
            p50 = lats[len(lats) // 2]
            round_p50s.append(p50)
            round_nums.append(r)
        if round_p50s:
            ax.plot(round_nums, round_p50s, "o-", color=COLORS[name], label=name,
                    linewidth=2, markersize=8)

    ax.set_xlabel("Round (2-hour intervals)")
    ax.set_ylabel("Client Latency P50 (ms)")
    ax.set_title("P50 Latency Stability Over Time")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["R1\n19:27", "R2\n21:28", "R3\n23:29", "R4\n01:31", "R5\n03:32"])
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Right: Aggregated bar with min-max error bars
    ax2 = axes[1]
    active_systems = []
    means = []
    stds = []
    mins = []
    maxs = []
    colors = []

    for name, fname in system_files.items():
        all_p50s = []
        for r in range(1, 6):
            path = TEMPORAL_DIR / f"round_{r}" / fname
            if not path.exists():
                continue
            with open(path) as f:
                data = json.load(f)
            inv = list(list(data.get("_invocations", {}).values())[0].values())
            warm = [i for i in inv if _is_warm(i)]
            if len(warm) < 10:
                continue
            lats = sorted([i["times"]["client"] / 1000 for i in warm])
            all_p50s.append(lats[len(lats) // 2])

        if len(all_p50s) >= 2:
            active_systems.append(name)
            mean = np.mean(all_p50s)
            means.append(mean)
            stds.append(np.std(all_p50s))
            mins.append(mean - min(all_p50s))
            maxs.append(max(all_p50s) - mean)
            colors.append(COLORS[name])

    x = np.arange(len(active_systems))
    bars = ax2.bar(x, means, color=colors, alpha=0.8, width=0.5)
    ax2.errorbar(x, means, yerr=[mins, maxs], fmt="none", ecolor="black",
                 capsize=6, capthick=2, linewidth=2)

    for i, (bar, m, s) in enumerate(zip(bars, means, stds)):
        ax2.annotate(f"{m:.1f}ms\n\u00b1{s:.1f}", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)

    ax2.set_ylabel("Mean P50 Latency (ms)")
    ax2.set_title("Aggregated P50 with Min-Max Error Bars")
    ax2.set_xticks(x)
    ax2.set_xticklabels([SHORT_NAMES[s] for s in active_systems], fontsize=10)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Temporal Variance — 5 Rounds Over 10 Hours", fontsize=13)
    fig.text(0.5, -0.01,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "24_temporal_variance.png")
    plt.close(fig)
    print("  24_temporal_variance.png")


# ── Plot 25: Temporal Variance without Lambda Durable ──

def plot_temporal_variance_no_durable():
    """Same as plot 24 but excludes Lambda Durable for better Y-axis resolution."""
    TEMPORAL_DIR = SCRIPT_DIR.parent.parent / "results" / "temporal"

    system_files = {
        "Lambda + Redis": "lambda-latency-dist.json",
        "Boki": "boki-latency-dist.json",
        "Cloudburst + Anna": "cloudburst-latency-dist.json",
        "Restate": "restate-latency-dist.json",
    }

    fig, axes = plt.subplots(1, 2, figsize=scaled_figsize(14, 5))

    ax = axes[0]
    for name, fname in system_files.items():
        round_p50s = []
        round_nums = []
        for r in range(1, 6):
            path = TEMPORAL_DIR / f"round_{r}" / fname
            if not path.exists():
                continue
            with open(path) as f:
                data = json.load(f)
            inv = list(list(data.get("_invocations", {}).values())[0].values())
            warm = [i for i in inv if _is_warm(i)]
            if len(warm) < 10:
                continue
            lats = sorted([i["times"]["client"] / 1000 for i in warm])
            p50 = lats[len(lats) // 2]
            round_p50s.append(p50)
            round_nums.append(r)
        if round_p50s:
            ax.plot(round_nums, round_p50s, "o-", color=COLORS[name], label=name,
                    linewidth=2, markersize=8)

    ax.set_xlabel("Round (2-hour intervals)")
    ax.set_ylabel("Client Latency P50 (ms)")
    ax.set_title("P50 Latency Stability Over Time")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["R1\n19:27", "R2\n21:28", "R3\n23:29", "R4\n01:31", "R5\n03:32"])
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax2 = axes[1]
    active_systems = []
    means = []
    stds = []
    mins = []
    maxs = []
    colors = []

    for name, fname in system_files.items():
        all_p50s = []
        for r in range(1, 6):
            path = TEMPORAL_DIR / f"round_{r}" / fname
            if not path.exists():
                continue
            with open(path) as f:
                data = json.load(f)
            inv = list(list(data.get("_invocations", {}).values())[0].values())
            warm = [i for i in inv if _is_warm(i)]
            if len(warm) < 10:
                continue
            lats = sorted([i["times"]["client"] / 1000 for i in warm])
            all_p50s.append(lats[len(lats) // 2])

        if len(all_p50s) >= 2:
            active_systems.append(name)
            mean = np.mean(all_p50s)
            means.append(mean)
            stds.append(np.std(all_p50s))
            mins.append(mean - min(all_p50s))
            maxs.append(max(all_p50s) - mean)
            colors.append(COLORS[name])

    x = np.arange(len(active_systems))
    bars = ax2.bar(x, means, color=colors, alpha=0.8, width=0.5)
    ax2.errorbar(x, means, yerr=[mins, maxs], fmt="none", ecolor="black",
                 capsize=6, capthick=2, linewidth=2)

    for i, (bar, m, s) in enumerate(zip(bars, means, stds)):
        ax2.annotate(f"{m:.1f}ms\n\u00b1{s:.1f}", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)

    ax2.set_ylabel("Mean P50 Latency (ms)")
    ax2.set_title("Aggregated P50 with Min-Max Error Bars")
    ax2.set_xticks(x)
    ax2.set_xticklabels([SHORT_NAMES[s] for s in active_systems], fontsize=10)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Temporal Variance — Excluding Lambda Durable", fontsize=13)
    fig.text(0.5, -0.01,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "25_temporal_variance_no_durable.png")
    plt.close(fig)
    print("  25_temporal_variance_no_durable.png")


# ── Plot 17: Normalized Latency Distribution (KDE) ──

def plot_normalized_distribution():
    fig, ax = plt.subplots(figsize=scaled_figsize(8, 4.5))

    for name in SYSTEMS:
        data = _load(name, "latency-dist.json")
        if not data:
            continue
        results, _ = data
        lats = np.array(extract_client_latencies(results))
        if len(lats) < 2:
            continue

        # Use histogram with density=True to produce a normalized distribution
        bins = np.linspace(lats.min(), np.percentile(lats, 99.5), 200)
        counts, bin_edges = np.histogram(lats, bins=bins, density=True)
        # Normalize peak to 1.0
        if counts.max() > 0:
            counts = counts / counts.max()
        centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        ax.plot(centers, counts, color=COLORS[name], label=name, linewidth=1.5, alpha=0.85)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("Normalized Density (0–1)")
    ax.set_title("Normalized Latency Distribution")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(OUT_DIR / "17_normalized_distribution.png")
    plt.close(fig)
    print("  17_normalized_distribution.png")


# ── Main ──

# ── Plot 20: Detailed Latency Decomposition (Lambda, Boki, Restate) ──

def plot_detailed_decomposition():
    """5-component stacked bar: Network, System Overhead, Write, Read, Compute.
    Lambda/Boki/Restate/Gresse — excludes Durable and Cloudburst (too large, separate plot)."""
    systems = ["Gresse", "Lambda + Redis", "Boki", "Restate"]

    def decompose_detailed(results_dir, system_dir):
        data_path = results_dir / system_dir / "latency-dist.json"
        if not data_path.exists():
            return None
        with open(data_path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            return None
        results = list(invocations[0].values())
        warm = [r for r in results if _is_warm(r)]
        if not warm:
            return None
        n = len(warm)
        pick = lambda vals, pct: sorted(vals)[min(int(pct / 100 * n), n - 1)]

        clients = [r["times"]["client"] / 1000 for r in warm]
        rtts = [r["times"]["http_startup"] * 1000 for r in warm]
        first_bytes = [r["times"]["http_first_byte_return"] * 1000 for r in warm]
        benchmarks = [r["times"]["benchmark"] / 1000 for r in warm]
        writes = [r["output"]["measurement"]["state_write_lat_us"] / 1000 for r in warm]
        reads = [r["output"]["measurement"]["state_read_lat_us"] / 1000 for r in warm]

        c = pick(clients, 50)
        rtt = pick(rtts, 50)
        fb = pick(first_bytes, 50)
        b = pick(benchmarks, 50)
        w = pick(writes, 50)
        rd = pick(reads, 50)

        overhead = max(0, fb - rtt - b)
        compute = max(0, b - w - rd)
        post = max(0, c - fb)

        return {"network": rtt + post, "overhead": overhead, "write": w, "read": rd, "compute": compute, "total": c}

    fig, ax = plt.subplots(figsize=scaled_figsize(10, 5.5))

    bar_labels = []
    net_vals, oh_vals, write_vals, read_vals, compute_vals = [], [], [], [], []
    bar_colors = []

    for name in systems:
        sdir = SYSTEM_DIRS[name]
        d = decompose_detailed(CLOUD_RESULTS_DIR, sdir)
        if d:
            bar_labels.append(SHORT_NAMES[name])
            net_vals.append(d["network"])
            oh_vals.append(d["overhead"])
            write_vals.append(d["write"])
            read_vals.append(d["read"])
            compute_vals.append(d["compute"])
            bar_colors.append(COLORS[name])

    positions = np.arange(len(bar_labels))
    width = 0.7

    # Stack: overhead (bottom) → write → read → compute → network (top)
    ax.bar(positions, oh_vals, width, label="System Overhead",
           color=bar_colors, alpha=0.5, hatch="//", edgecolor="white", linewidth=0.5)
    ax.bar(positions, write_vals, width, bottom=oh_vals, label="State Write",
           color=bar_colors, alpha=0.7, edgecolor="white", linewidth=0.5)
    bottom2 = [o + w for o, w in zip(oh_vals, write_vals)]
    ax.bar(positions, read_vals, width, bottom=bottom2, label="State Read",
           color=bar_colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    bottom3 = [b + r for b, r in zip(bottom2, read_vals)]
    ax.bar(positions, compute_vals, width, bottom=bottom3, label="Compute",
           color=bar_colors, alpha=0.4, edgecolor="white", linewidth=0.5)
    bottom4 = [b + c for b, c in zip(bottom3, compute_vals)]
    ax.bar(positions, net_vals, width, bottom=bottom4, label="Network Latency",
           color=bar_colors, alpha=0.25, hatch="...", edgecolor="white", linewidth=0.5)

    for i, p in enumerate(positions):
        total = net_vals[i] + oh_vals[i] + write_vals[i] + read_vals[i] + compute_vals[i]
        ax.annotate(f"{total:.1f}ms", xy=(p, total), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8, fontweight="bold")

    ax.set_ylabel("Client Latency P50 (ms)")
    ax.set_title("Detailed Latency Decomposition (P50)")
    ax.set_xticks(positions)
    ax.set_xticklabels(bar_labels, fontsize=9)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#888888", alpha=0.4, label="Compute"),
        Patch(facecolor="#888888", alpha=0.7, label="State Write"),
        Patch(facecolor="#888888", alpha=0.9, label="State Read"),
        Patch(facecolor="#888888", alpha=0.5, hatch="//", label="System Overhead"),
        Patch(facecolor="#888888", alpha=0.25, hatch="...", label="Network Latency"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    fig.savefig(OUT_DIR / "20_detailed_decomposition.png")
    plt.close(fig)
    print("  20_detailed_decomposition.png")


# ── Plot 21: Detailed Decomposition (Lambda Durable, Cloudburst) ──

def plot_detailed_decomposition_heavy():
    """Same 5-component decomposition for Durable + Cloudburst (high-overhead systems)."""
    systems = ["Cloudburst + Anna", "Lambda Durable"]

    def decompose_detailed(results_dir, system_dir):
        data_path = results_dir / system_dir / "latency-dist.json"
        if not data_path.exists():
            return None
        with open(data_path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            return None
        results = list(invocations[0].values())
        warm = [r for r in results if _is_warm(r)]
        if not warm:
            return None
        n = len(warm)
        pick = lambda vals, pct: sorted(vals)[min(int(pct / 100 * n), n - 1)]

        clients = [r["times"]["client"] / 1000 for r in warm]
        rtts = [r["times"]["http_startup"] * 1000 for r in warm]
        first_bytes = [r["times"]["http_first_byte_return"] * 1000 for r in warm]
        benchmarks = [r["times"]["benchmark"] / 1000 for r in warm]
        writes = [r["output"]["measurement"]["state_write_lat_us"] / 1000 for r in warm]
        reads = [r["output"]["measurement"]["state_read_lat_us"] / 1000 for r in warm]

        c = pick(clients, 50)
        rtt = pick(rtts, 50)
        fb = pick(first_bytes, 50)
        b = pick(benchmarks, 50)
        w = pick(writes, 50)
        rd = pick(reads, 50)

        overhead = max(0, fb - rtt - b)
        compute = max(0, b - w - rd)
        post = max(0, c - fb)

        return {"network": rtt + post, "overhead": overhead, "write": w, "read": rd, "compute": compute, "total": c}

    fig, ax = plt.subplots(figsize=scaled_figsize(8, 5.5))

    bar_labels = []
    net_vals, oh_vals, write_vals, read_vals, compute_vals = [], [], [], [], []
    bar_colors = []

    for name in systems:
        sdir = SYSTEM_DIRS[name]
        d = decompose_detailed(CLOUD_RESULTS_DIR, sdir)
        if d:
            bar_labels.append(SHORT_NAMES[name])
            net_vals.append(d["network"])
            oh_vals.append(d["overhead"])
            write_vals.append(d["write"])
            read_vals.append(d["read"])
            compute_vals.append(d["compute"])
            bar_colors.append(COLORS[name])

    positions = np.arange(len(bar_labels))
    width = 0.7

    ax.bar(positions, oh_vals, width, label="System Overhead",
           color=bar_colors, alpha=0.5, hatch="//", edgecolor="white", linewidth=0.5)
    ax.bar(positions, write_vals, width, bottom=oh_vals, label="State Write",
           color=bar_colors, alpha=0.7, edgecolor="white", linewidth=0.5)
    bottom2 = [o + w for o, w in zip(oh_vals, write_vals)]
    ax.bar(positions, read_vals, width, bottom=bottom2, label="State Read",
           color=bar_colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    bottom3 = [b + r for b, r in zip(bottom2, read_vals)]
    ax.bar(positions, compute_vals, width, bottom=bottom3, label="Compute",
           color=bar_colors, alpha=0.4, edgecolor="white", linewidth=0.5)
    bottom4 = [b + c for b, c in zip(bottom3, compute_vals)]
    ax.bar(positions, net_vals, width, bottom=bottom4, label="Network Latency",
           color=bar_colors, alpha=0.25, hatch="...", edgecolor="white", linewidth=0.5)

    for i, p in enumerate(positions):
        total = net_vals[i] + oh_vals[i] + write_vals[i] + read_vals[i] + compute_vals[i]
        ax.annotate(f"{total:.1f}ms", xy=(p, total), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8, fontweight="bold")

    ax.set_ylabel("Client Latency P50 (ms)")
    ax.set_title("Detailed Latency Decomposition (P50) — Cloudburst and Lambda Durable")
    ax.set_xticks(positions)
    ax.set_xticklabels(bar_labels, fontsize=9)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#888888", alpha=0.4, label="Compute"),
        Patch(facecolor="#888888", alpha=0.7, label="State Write"),
        Patch(facecolor="#888888", alpha=0.9, label="State Read"),
        Patch(facecolor="#888888", alpha=0.5, hatch="//", label="System Overhead"),
        Patch(facecolor="#888888", alpha=0.25, hatch="...", label="Network Latency"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    fig.savefig(OUT_DIR / "21_detailed_decomposition_heavy.png")
    plt.close(fig)
    print("  21_detailed_decomposition_heavy.png")


def plot_latency_percentiles_no_cloudburst():
    """Plot 26: Latency percentiles excluding Cloudburst for better Y-axis resolution."""
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    percentile_labels = ["P50", "P95", "P99"]
    percentile_vals = [50, 95, 99]
    x = np.arange(len(percentile_labels))

    exclude = {"Cloudburst + Anna"}
    active = []
    for name in SYSTEMS:
        if name in exclude:
            continue
        data = _load(name, "latency-dist.json")
        if not data:
            continue
        active.append((name, data))

    width = 0.8 / max(len(active), 1)
    for i, (name, data) in enumerate(active):
        results, _ = data
        lats = sorted(extract_client_latencies(results))
        n = len(lats)
        vals = [lats[min(int(p / 100 * n), n - 1)] for p in percentile_vals]
        bars = ax.bar(x + i * width, vals, width, label=SHORT_NAMES[name],
                      color=COLORS[name])
        for bar in bars:
            h = bar.get_height()
            ax.annotate(f"{h:.1f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=7)

    ax.set_xlabel("Percentile")
    ax.set_ylabel("Client Latency (ms)")
    ax.set_title("Client Latency Percentiles — Excluding Cloudburst (64KB state)")
    ax.set_xticks(x + width * max(len(active) - 1, 0) / 2)
    ax.set_xticklabels(percentile_labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.savefig(OUT_DIR / "26_latency_percentiles_no_cloudburst.png")
    plt.close(fig)
    print("  26_latency_percentiles_no_cloudburst.png")


def plot_latency_cdf_cloud_no_cloudburst():
    """Plot 27: Cloud CDF excluding Cloudburst for better X-axis resolution."""
    fig, ax = plt.subplots(figsize=scaled_figsize(7, 4.5))
    exclude = {"Cloudburst + Anna"}

    for name in SYSTEMS:
        if name in exclude:
            continue
        sdir = SYSTEM_DIRS[name]
        path = CLOUD_RESULTS_DIR / sdir / "latency-dist.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        invocations = list(data.get("_invocations", {}).values())
        if not invocations:
            continue
        results = list(invocations[0].values())
        lats = sorted(extract_client_latencies(results))
        percentiles = np.arange(1, len(lats) + 1) / len(lats) * 100
        ax.plot(lats, percentiles, color=COLORS[name], label=SHORT_NAMES[name],
                linewidth=1.5)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("Percentile (%)")
    ax.set_title("Latency Distribution (CDF) — Excluding Cloudburst")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, -0.02,
             "Each invocation: fresh 64KB random state blob, unique key (no state reuse across invocations).",
             ha="center", fontsize=8, style="italic", color="#555555")
    fig.savefig(OUT_DIR / "27_latency_cdf_cloud_no_cloudburst.png")
    plt.close(fig)
    print("  27_latency_cdf_cloud_no_cloudburst.png")


if __name__ == "__main__":
    print(f"Generating plots from {CLOUD_RESULTS_DIR}")
    print(f"Output: {OUT_DIR}\n")

    plot_throughput_scaling()
    plot_latency_cdf()
    plot_latency_percentiles()
    plot_write_read_breakdown()
    plot_state_size_impact()
    plot_cold_start()
    plot_cost()
    plot_resource_usage()
    plot_state_placement()
    plot_scaling_timeline_cb()
    plot_latency_decomposition()
    plot_throughput_scaling_cloud()
    plot_latency_cdf_cloud()
    plot_write_read_p95()
    plot_latency_scatter()
    plot_normalized_distribution()
    plot_detailed_decomposition()
    plot_detailed_decomposition_heavy()
    plot_scatter_boki_lambda()
    plot_scatter_others()
    plot_temporal_variance()
    plot_temporal_variance_no_durable()
    plot_latency_percentiles_no_cloudburst()
    plot_latency_cdf_cloud_no_cloudburst()

    print(f"\nDone. {len(list(OUT_DIR.glob('*.png')))} plots generated.")
