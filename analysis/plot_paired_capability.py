"""Render graphs for the frozen paired capability benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path("results")
RAW_PATH = RESULTS_DIR / "paired_capability_benchmark.json"
STATS_PATH = RESULTS_DIR / "paired_capability_statistics.json"
OUTPUT_DIR = RESULTS_DIR / "capability_visuals"
FAULTS = ("locked", "free", "partial_torque")
FAULT_LABELS = ("LOCKED", "FREE", "PARTIAL TORQUE")
COLORS = ("#c0392b", "#e67e22", "#2980b9")


def load_data():
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    return raw["records"], stats


def _stat_lookup(stats):
    return {(row["fault"], row["metric"]): row for row in stats["tests"]}


def plot_effects(records, stats):
    metrics = (
        ("forward_progress_delta", "Forward progress Δ (m)", "lower = worse"),
        ("lateral_drift_delta", "Lateral drift Δ (m)", "higher = worse"),
        ("stall_fraction_delta", "Stall fraction Δ", "higher = worse"),
        ("heading_deviation_deg_delta", "Heading deviation Δ (deg)", "higher = worse"),
        ("fall_fraction_delta", "Fall fraction Δ", "higher = worse"),
        ("torque_saturation_fraction_delta", "Torque saturation Δ", "interpret with fault semantics"),
        ("survival_delta", "Survival Δ", "lower = worse"),
    )
    lookup = _stat_lookup(stats)
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), dpi=180)
    for ax, (metric, ylabel, note) in zip(axes.flat, metrics):
        means, lows, highs, significant = [], [], [], []
        for fault in FAULTS:
            row = lookup[(fault, metric)]
            means.append(row["mean_difference"])
            lows.append(row["bootstrap_ci_95"][0])
            highs.append(row["bootstrap_ci_95"][1])
            significant.append(row["significant_after_bonferroni"])
        x = np.arange(len(FAULTS))
        errors = np.array([np.array(means) - np.array(lows), np.array(highs) - np.array(means)])
        ax.errorbar(x, means, yerr=errors, fmt="none", ecolor="black", capsize=5, zorder=3)
        bars = ax.bar(x, means, color=COLORS, edgecolor="black", linewidth=0.6, zorder=2)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(x, FAULT_LABELS, rotation=15, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(note, fontsize=9)
        ax.grid(axis="y", alpha=0.25)
        for bar, mean, sig in zip(bars, means, significant):
            ax.text(bar.get_x() + bar.get_width() / 2, mean, "*" if sig else "ns",
                    ha="center", va="bottom" if mean >= 0 else "top", fontweight="bold")
    axes.flat[-1].axis("off")
    fig.suptitle(
        "Fault effect versus matched healthy episode (mean Δ, bootstrap 95% CI; n=36/fault)\n"
        "* permutation p < Bonferroni α=0.05/21; ns = not significant after correction",
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    path = OUTPUT_DIR / "paired_capability_effects.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_distributions(records):
    metrics = (
        ("forward_progress_delta", "Forward progress Δ (m)"),
        ("lateral_drift_delta", "Lateral drift Δ (m)"),
        ("stall_fraction_delta", "Stall fraction Δ"),
        ("heading_deviation_deg_delta", "Heading deviation Δ (deg)"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=180)
    rng = np.random.default_rng(0)
    for ax, (metric, label) in zip(axes.flat, metrics):
        groups = [[record["paired_delta"][metric] for record in records if record["fault"] == fault] for fault in FAULTS]
        box = ax.boxplot(groups, tick_labels=FAULT_LABELS, patch_artist=True, widths=0.55, showfliers=True)
        for patch, color in zip(box["boxes"], COLORS):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)
        for index, values in enumerate(groups, start=1):
            jitter = rng.uniform(-0.09, 0.09, len(values))
            ax.scatter(np.full(len(values), index) + jitter, values, s=14, alpha=0.65, color="black", zorder=3)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_ylabel(label)
        ax.set_title("Raw paired differences: fault − healthy")
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Paired capability distributions (36 matched episodes per fault)", fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    path = OUTPUT_DIR / "paired_capability_distributions.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records, stats = load_data()
    effects = plot_effects(records, stats)
    distributions = plot_distributions(records)
    print(f"saved {effects}")
    print(f"saved {distributions}")


if __name__ == "__main__":
    main()
