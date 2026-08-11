"""Render a paired XY trajectory and lock-drift diagnostic for one frozen case.

This deterministic C5/flat/joint-3/seed-7 figure is visualization-only.
Population inference remains in the paired benchmark statistics.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import multiprocessing as mp
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType

OUTPUT = Path("results/capability_visuals/c5_flat_locked_xy_lock_drift_seed7.png")
CONTROLLER = "C5"
JOINT = 3
SEED = 7
DURATION = 10.0
FAULT_TIME = 4.0
SETTLE_WINDOW_S = 0.5
TOLERANCE_RAD = 1e-3


def _run_case(fault: str):
    return fault, run_single_episode(
        controller_type=CONTROLLER,
        fault_type=fault,
        fault_joint_idx=JOINT,
        fault_time=FAULT_TIME,
        duration=DURATION,
        gui=False,
        env_type=EnvironmentType.FLAT,
        seed=SEED,
    )


def main(output: Path = OUTPUT):
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as executor:
        cases = dict(executor.map(_run_case, (FaultType.NONE, FaultType.LOCKED)))
    healthy_history, _ = cases[FaultType.NONE]
    locked_history, locked_metrics = cases[FaultType.LOCKED]

    healthy_xy = np.asarray(healthy_history["base_position"], dtype=float)[:, :2]
    locked_xy = np.asarray(locked_history["base_position"], dtype=float)[:, :2]
    time = np.asarray(locked_history["time"], dtype=float)
    locked_angles = np.asarray(locked_history["joint_angles"], dtype=float)
    lock_reference = np.asarray(locked_history["locked_angle_reference"], dtype=float)
    lock_angle = float(lock_reference[np.searchsorted(time, FAULT_TIME, side="left")])
    lock_drift = np.abs(locked_angles[:, JOINT] - lock_angle)
    fault_index = int(np.searchsorted(time, FAULT_TIME, side="left"))
    lock_drift[:fault_index] = np.nan

    fig, (xy_ax, drift_ax) = plt.subplots(1, 2, figsize=(14, 6), dpi=180)
    xy_ax.plot(healthy_xy[:, 0], healthy_xy[:, 1], color="#2980b9", linewidth=1.8, label="healthy")
    xy_ax.plot(locked_xy[: fault_index + 1, 0], locked_xy[: fault_index + 1, 1], color="#34495e", linewidth=1.8, label="LOCKED pre-fault")
    xy_ax.plot(locked_xy[fault_index:, 0], locked_xy[fault_index:, 1], color="#c0392b", linewidth=1.8, label="LOCKED post-fault")
    xy_ax.scatter(*locked_xy[0], color="#27ae60", s=50, zorder=3, label="start")
    xy_ax.scatter(*locked_xy[fault_index], color="#f39c12", marker="X", s=70, zorder=3, label="fault @ 4 s")
    xy_ax.scatter(*locked_xy[-1], color="#8e44ad", marker="s", s=50, zorder=3, label="LOCKED end")
    xy_ax.set_xlabel("World X (m)")
    xy_ax.set_ylabel("World Y (m); nominal forward = -Y")
    xy_ax.set_title("Paired world-frame trajectory")
    xy_ax.set_aspect("equal", adjustable="box")
    xy_ax.grid(alpha=0.3)
    xy_ax.legend(fontsize=8)

    drift_ax.plot(time, lock_drift, color="#c0392b", linewidth=1.5, label="|q_locked − q_fault|")
    drift_ax.axvline(FAULT_TIME, color="#f39c12", linestyle="--", label="fault onset")
    drift_ax.axvline(FAULT_TIME + SETTLE_WINDOW_S, color="#8e44ad", linestyle="--", label="steady window")
    drift_ax.axhline(TOLERANCE_RAD, color="black", linestyle=":", label="tolerance = 1e-3 rad")
    drift_ax.set_xlabel("Time (s)")
    drift_ax.set_ylabel("Absolute joint-angle drift (rad)")
    drift_ax.set_title("Mechanical-lock integrity diagnostic")
    drift_ax.grid(alpha=0.3)
    drift_ax.legend(fontsize=8, loc="upper right")
    drift_ax.text(
        0.02, 0.96,
        "onset max = %.6f rad\nsteady max = %.6f rad\nonset/steady pass = %s / %s" % (
            locked_metrics["locked_joint_drift_max_rad"],
            locked_metrics["locked_joint_drift_steady_max_rad"],
            locked_metrics["locked_joint_drift_within_tolerance"],
            locked_metrics["locked_joint_drift_steady_within_tolerance"],
        ),
        transform=drift_ax.transAxes,
        va="top",
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "0.7"},
        fontsize=8,
    )
    fig.suptitle(
        "C5, flat, joint 3, seed 7; 10 s; LOCKED fault at 4 s\n"
        "Visualization-only diagnostic — do not use a single trajectory for population inference.",
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output}")
    print(f"onset_max_rad={locked_metrics['locked_joint_drift_max_rad']:.9f}")
    print(f"steady_max_rad={locked_metrics['locked_joint_drift_steady_max_rad']:.9f}")


if __name__ == "__main__":
    main()
