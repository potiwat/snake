"""Render representative XY trajectories for robustness runtime verification.

This is a single-seed visual diagnostic: C5, joint 3, seed 7, 10 s,
fault at 4 s. It is not a substitute for the paired statistical benchmark.
"""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType

OUTPUT_DIR = Path("results/capability_visuals")
DURATION = 10.0
FAULT_TIME = 4.0
CONTROLLER = "C5"
JOINT = 3
SEED = 7
ENVIRONMENTS = (
    (EnvironmentType.LOW_FRICTION, "LOW FRICTION"),
    (EnvironmentType.VARIABLE_FRICTION, "VARIABLE FRICTION"),
    (EnvironmentType.INCLINE, "INCLINE 10°"),
)
CONDITIONS = (
    (FaultType.NONE, "HEALTHY"),
    (FaultType.LOCKED, "LOCKED"),
    (FaultType.FREE, "FREE"),
    (FaultType.PARTIAL_TORQUE, "PARTIAL TORQUE"),
)


def _trajectory(env_type: EnvironmentType, fault: FaultType):
    history, _ = run_single_episode(
        controller_type=CONTROLLER,
        fault_type=fault,
        fault_joint_idx=JOINT,
        fault_time=FAULT_TIME,
        duration=DURATION,
        gui=False,
        env_type=env_type,
        incline_deg=10.0,
        seed=SEED,
    )
    points = np.asarray(history["base_position"], dtype=float)[:, :2]
    times = np.asarray(history["time"], dtype=float)
    return times, points


def main():
    trajectories = {
        (environment, fault): _trajectory(environment, fault)
        for environment, _ in ENVIRONMENTS
        for fault, _ in CONDITIONS
    }
    all_points = np.concatenate([points for _, points in trajectories.values()])
    minima, maxima = all_points.min(axis=0), all_points.max(axis=0)
    margin = max(0.15, 0.06 * float(np.max(maxima - minima)))
    xlim = (minima[0] - margin, maxima[0] + margin)
    ylim = (minima[1] - margin, maxima[1] + margin)

    fig, axes = plt.subplots(3, 4, figsize=(16, 12), dpi=180, sharex=True, sharey=True)
    for row, (environment, environment_label) in enumerate(ENVIRONMENTS):
        for col, (fault, condition_label) in enumerate(CONDITIONS):
            ax = axes[row, col]
            times, points = trajectories[(environment, fault)]
            pre = times < FAULT_TIME
            fault_index = int(np.searchsorted(times, FAULT_TIME, side="left"))
            fault_index = min(fault_index, len(points) - 1)
            ax.plot(points[pre, 0], points[pre, 1], color="black", linewidth=1.5, label="pre-fault")
            ax.plot(points[~pre, 0], points[~pre, 1], color="#c0392b", linewidth=1.5, label="post-fault")
            ax.scatter(*points[0], s=42, color="#27ae60", marker="o", zorder=4, label="start")
            ax.scatter(*points[fault_index], s=54, color="#f39c12", marker="X", zorder=4, label="fault @ 4 s")
            ax.scatter(*points[-1], s=48, color="#2980b9", marker="s", zorder=4, label="end")
            ax.axhline(0, color="0.8", linewidth=0.7)
            ax.axvline(0, color="0.8", linewidth=0.7)
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.set_aspect("equal", adjustable="box")
            ax.grid(alpha=0.25)
            if row == 0:
                ax.set_title(condition_label, fontweight="bold")
            if col == 0:
                ax.set_ylabel(f"{environment_label}\nY (m); forward = -Y")
            if row == len(ENVIRONMENTS) - 1:
                ax.set_xlabel("X (m)")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.94))
    fig.suptitle(
        "Robustness runtime verification: XY trajectories (C5, joint 3, seed 7; 10 s; fault at 4 s)\n"
        "Representative visualization only — infer population effects from paired statistics, not these traces.",
        fontweight="bold",
        y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "robustness_xy_trajectories_slope10.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output}")


if __name__ == "__main__":
    main()
