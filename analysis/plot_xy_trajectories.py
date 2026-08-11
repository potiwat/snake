"""Render representative world-frame XY trajectories for the frozen capability protocol.

The four panels are single-seed visualizations (C5, flat, joint 3, seed 7),
not replacement statistical evidence for the paired 108-record benchmark.
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType

OUTPUT_DIR = Path("results/capability_visuals")
CASES = (FaultType.NONE, FaultType.LOCKED, FaultType.FREE, FaultType.PARTIAL_TORQUE)
TITLES = ("Healthy (no fault)", "LOCKED fault", "FREE fault", "PARTIAL_TORQUE fault")
COLORS = {"pre": "#34495e", "post": "#c0392b"}


def main():
    fault_time = 4.0
    histories = []
    for fault in CASES:
        history, _ = run_single_episode(
            controller_type="C5",
            fault_type=fault,
            fault_joint_idx=3,
            fault_time=fault_time,
            duration=10.0,
            gui=False,
            env_type=EnvironmentType.FLAT,
            seed=7,
        )
        histories.append(history)

    fig, axes = plt.subplots(2, 2, figsize=(11, 9), dpi=180, sharex=True, sharey=True)
    global_x, global_y = [], []
    for history in histories:
        position = np.asarray(history["base_position"], dtype=float)
        global_x.extend(position[:, 0])
        global_y.extend(position[:, 1])
    pad = 0.15
    x_limits = (min(global_x) - pad, max(global_x) + pad)
    y_limits = (min(global_y) - pad, max(global_y) + pad)

    for ax, history, title in zip(axes.flat, histories, TITLES):
        time = np.asarray(history["time"], dtype=float)
        position = np.asarray(history["base_position"], dtype=float)
        fault_index = int(np.searchsorted(time, fault_time))
        ax.plot(position[: fault_index + 1, 0], position[: fault_index + 1, 1],
                color=COLORS["pre"], linewidth=2.0, label="pre-fault")
        ax.plot(position[fault_index:, 0], position[fault_index:, 1],
                color=COLORS["post"], linewidth=2.0, label="post-fault")
        ax.scatter(position[0, 0], position[0, 1], s=55, color="#27ae60", marker="o", label="start", zorder=3)
        ax.scatter(position[fault_index, 0], position[fault_index, 1], s=65, color="#f39c12", marker="X", label="fault time", zorder=4)
        ax.scatter(position[-1, 0], position[-1, 1], s=55, color="#2980b9", marker="s", label="end", zorder=3)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("World x (m)")
        ax.set_ylabel("World y (m); nominal forward = -Y")
        ax.set_xlim(x_limits)
        ax.set_ylim(y_limits)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=0.3)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=True)
    fig.suptitle(
        "Representative XY trajectories: C5, flat terrain, joint 3, seed 7\n"
        "Pre/post split at t=4 s; use paired benchmark for population-level inference",
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "c5_flat_xy_trajectories_seed7.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {path}")


if __name__ == "__main__":
    main()
