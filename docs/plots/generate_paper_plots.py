#!/usr/bin/env python3
"""
Generate paper-specific plots from the selected comparison datasets.

Current figures:
  01_latency_violins.png
  02_throughput_c100.png
  03_throughput_c100_singlecol.png
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CLOUD_RESULTS_DIR = REPO_ROOT / "results" / "cloud"
RUN6_RESULTS_DIR = REPO_ROOT / "results" / "run6"
OUT_DIR = SCRIPT_DIR / "paper_out"
OUT_DIR.mkdir(exist_ok=True)

POINTS_PER_INCH = 72.0
FIGURE_WIDTH_PT = 516.0
FIGURE_WIDTH_IN = FIGURE_WIDTH_PT / POINTS_PER_INCH
SINGLE_COLUMN_WIDTH_PT = 252.0
SINGLE_COLUMN_WIDTH_IN = SINGLE_COLUMN_WIDTH_PT / POINTS_PER_INCH

COLORS = {
    "Gresse": "#795548",
    "Lambda + Redis": "#FF9900",
    "Cloudburst": "#4CAF50",
    "Boki": "#2196F3",
    "Restate": "#9C27B0",
    "Lambda Durable": "#E53935",
}

SYSTEMS = [
    "Gresse",
    "Lambda + Redis",
    "Cloudburst",
    "Boki",
    "Restate",
    "Lambda Durable",
]

SYSTEM_SOURCES = {
    "Gresse": RUN6_RESULTS_DIR / "gresse" / "latency-dist.json",
    "Lambda + Redis": CLOUD_RESULTS_DIR / "lambda" / "latency-dist.json",
    "Cloudburst": CLOUD_RESULTS_DIR / "cloudburst" / "latency-dist.json",
    "Boki": CLOUD_RESULTS_DIR / "boki" / "latency-dist.json",
    "Restate": CLOUD_RESULTS_DIR / "restate" / "latency-dist.json",
    "Lambda Durable": CLOUD_RESULTS_DIR / "lambda-durable" / "latency-dist.json",
}

THROUGHPUT_C100_SOURCES = {
    "Gresse": RUN6_RESULTS_DIR / "gresse" / "throughput-c100.json",
    "Lambda + Redis": CLOUD_RESULTS_DIR / "lambda" / "throughput-c100.json",
    "Cloudburst": CLOUD_RESULTS_DIR / "cloudburst" / "throughput-c100.json",
    "Boki": CLOUD_RESULTS_DIR / "boki" / "throughput-c100.json",
    "Restate": CLOUD_RESULTS_DIR / "restate" / "throughput-c100.json",
    "Lambda Durable": CLOUD_RESULTS_DIR / "lambda-durable" / "throughput-c100.json",
}

LEFT_PANEL = ["Gresse", "Lambda + Redis", "Boki"]
RIGHT_PANEL = ["Cloudburst", "Restate", "Lambda Durable"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 150,
    "figure.constrained_layout.use": True,
    "savefig.bbox": None,
    "savefig.pad_inches": 0.05,
})


def scaled_figsize(width_in: float, height_in: float) -> tuple:
    scale = FIGURE_WIDTH_IN / width_in
    return (FIGURE_WIDTH_IN, height_in * scale)


def scaled_singlecol_figsize(width_in: float, height_in: float) -> tuple:
    scale = SINGLE_COLUMN_WIDTH_IN / width_in
    return (SINGLE_COLUMN_WIDTH_IN, height_in * scale)


def load_invocations(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Missing results file: {path}")
    data = json.loads(path.read_text())
    invocations = list(data.get("_invocations", {}).values())
    if not invocations:
        raise RuntimeError(f"No invocation data in {path}")
    return list(invocations[0].values())


def is_warm_success(result: dict) -> bool:
    if result.get("stats", {}).get("failure"):
        return False
    if result.get("stats", {}).get("cold_start"):
        return False
    if result.get("output", {}).get("is_cold"):
        return False
    return True


def extract_client_latencies_ms(system_name: str) -> list:
    path = SYSTEM_SOURCES[system_name]
    results = load_invocations(path)
    return [
        r["times"]["client"] / 1000.0
        for r in results
        if is_warm_success(r)
    ]


def extract_throughput_ops_per_sec(system_name: str) -> float:
    path = THROUGHPUT_C100_SOURCES[system_name]
    if not path.exists():
        raise FileNotFoundError(f"Missing results file: {path}")
    data = json.loads(path.read_text())
    invocations = list(data.get("_invocations", {}).values())
    if not invocations:
        raise RuntimeError(f"No invocation data in {path}")
    results = list(invocations[0].values())
    duration = data.get("end_time", 0) - data.get("begin_time", 1)
    valid = [r for r in results if not r.get("stats", {}).get("failure")]
    if duration <= 0:
        raise RuntimeError(f"Invalid duration in {path}")
    return len(valid) / duration


def add_violin_panel(ax, systems: list, title: str) -> None:
    rows = []
    for system in systems:
        for latency_ms in extract_client_latencies_ms(system):
            rows.append({"system": system, "latency_ms": latency_ms})
    frame = pd.DataFrame(rows)

    sns.violinplot(
        data=frame,
        x="system",
        y="latency_ms",
        order=systems,
        palette=[COLORS[system] for system in systems],
        inner="quart",
        cut=0,
        linewidth=0.8,
        saturation=0.85,
        ax=ax,
    )

    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("Client latency (ms)")
    ax.grid(True, axis="y", alpha=0.3)


def plot_latency_violins() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=scaled_figsize(12, 3.2))

    add_violin_panel(axes[0], LEFT_PANEL, "")  # "Lower-latency variants"
    add_violin_panel(axes[1], RIGHT_PANEL, "")  # "Higher-latency variants"

    axes[0].set_ylim(bottom=0, top=50)
    axes[1].set_ylim(bottom=0, top=1000)

    out_path = OUT_DIR / "01_latency_violins.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  {out_path.name}")
    return out_path


def add_throughput_panel(ax, systems: list, title: str) -> None:
    values = [extract_throughput_ops_per_sec(system) for system in systems]
    positions = np.arange(len(systems))
    bars = ax.bar(
        positions,
        values,
        color=[COLORS[system] for system in systems],
        width=0.7,
        alpha=0.85,
    )
    ax.set_xticks(positions)
    ax.set_xticklabels(systems)
    ax.set_title(title)
    ax.set_ylabel("Throughput (ops/s)")
    ax.grid(True, axis="y", alpha=0.3)

    for bar, value in zip(bars, values):
        ax.annotate(
            f"{value:.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )


def plot_throughput_c100() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=scaled_figsize(12, 3.2))

    add_throughput_panel(axes[0], LEFT_PANEL, "")
    add_throughput_panel(axes[1], RIGHT_PANEL, "")

    axes[0].set_ylim(bottom=0, top=930)
    axes[1].set_ylim(bottom=0, top=190)

    out_path = OUT_DIR / "02_throughput_c100.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  {out_path.name}")
    return out_path


def plot_throughput_c100_singlecol() -> Path:
    fig, ax = plt.subplots(figsize=scaled_singlecol_figsize(6.2, 3.6))

    values = [extract_throughput_ops_per_sec(system) for system in SYSTEMS]
    positions = np.arange(len(SYSTEMS))
    bars = ax.bar(
        positions,
        values,
        color=[COLORS[system] for system in SYSTEMS],
        width=0.7,
        alpha=0.85,
    )

    ax.set_ylabel("Throughput (ops/s)")
    ax.set_xticks(positions)
    ax.set_xticklabels(SYSTEMS, rotation=35, ha="right")
    ax.grid(True, axis="y", alpha=0.3)

    for bar, value in zip(bars, values):
        ax.annotate(
            f"{value:.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=7,
        )

    out_path = OUT_DIR / "03_throughput_c100_singlecol.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  {out_path.name}")
    return out_path


def main() -> None:
    print(f"Generating paper plots from {CLOUD_RESULTS_DIR} and {RUN6_RESULTS_DIR}")
    print(f"Output: {OUT_DIR}\n")
    plot_latency_violins()
    plot_throughput_c100()
    plot_throughput_c100_singlecol()


if __name__ == "__main__":
    main()
