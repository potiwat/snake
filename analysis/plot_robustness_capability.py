"""Plot environment-stratified paired capability effects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

STATS_PATH = Path("results/paired_capability_robustness_statistics.json")
OUTPUT_DIR = Path("results/capability_visuals")
ENVIRONMENTS = ("low_friction", "variable_friction", "incline")
ENV_LABELS = ("LOW FRICTION", "VARIABLE FRICTION", "INCLINE")
FAULTS = ("locked", "free", "partial_torque")
FAULT_LABELS = ("LOCKED", "FREE", "PARTIAL TORQUE")
COLORS = ("#c0392b", "#e67e22", "#2980b9")
METRICS = (
    ("forward_progress_delta", "Forward progress Δ (m)"),
    ("stall_fraction_delta", "Stall fraction Δ"),
    ("lateral_drift_delta", "Lateral drift Δ (m)"),
)


def main(stats_path: Path = STATS_PATH, output: Path | None = None):
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    lookup = {(row["environment"], row["fault"], row["metric"]): row for row in stats["tests"]}
    fig, axes = plt.subplots(3, 3, figsize=(14, 12), dpi=180)
    for row_index, (environment, environment_label) in enumerate(zip(ENVIRONMENTS, ENV_LABELS)):
        for col_index, (metric, ylabel) in enumerate(METRICS):
            ax = axes[row_index, col_index]
            rows = [lookup[(environment, fault, metric)] for fault in FAULTS]
            means = np.array([row["mean_difference"] for row in rows])
            ci_low = np.array([row["bootstrap_ci_95"][0] for row in rows])
            ci_high = np.array([row["bootstrap_ci_95"][1] for row in rows])
            x = np.arange(len(FAULTS))
            errors = np.vstack((means - ci_low, ci_high - means))
            ax.errorbar(x, means, yerr=errors, fmt="none", ecolor="black", capsize=4, zorder=3)
            bars = ax.bar(x, means, color=COLORS, edgecolor="black", linewidth=0.6)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_xticks(x, FAULT_LABELS, rotation=15, ha="right")
            ax.set_ylabel(ylabel)
            ax.set_title(environment_label if col_index == 0 else ylabel)
            ax.grid(axis="y", alpha=0.25)
            for bar, entry in zip(bars, rows):
                value = entry["mean_difference"]
                marker = "*" if entry["significant_after_bonferroni"] else "ns"
                ax.text(bar.get_x() + bar.get_width() / 2, value, marker,
                        ha="center", va="bottom" if value >= 0 else "top", fontweight="bold")
    fig.suptitle(
        "Robustness benchmark: fault − matched healthy by terrain (mean Δ, bootstrap 95% CI; n=36/fault/terrain)\n"
        "* permutation p < Bonferroni α=0.05/63; ns = not significant after correction",
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = output or OUTPUT_DIR / "robustness_capability_effects.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default=str(STATS_PATH))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    main(Path(args.stats), Path(args.output) if args.output else None)
