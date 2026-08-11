"""Generate verified configuration and healthy-capability validation plots."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pybullet as p

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType, SimulationEnvironment
from simulation.snake_robot import FaultType, SnakeRobot

OUTPUT_DIR = Path("results/validation")
CONTROLLERS = ["C1", "C2", "C3", "C4", "C5", "C6"]
ENVIRONMENTS = [
    EnvironmentType.FLAT,
    EnvironmentType.LOW_FRICTION,
    EnvironmentType.VARIABLE_FRICTION,
    EnvironmentType.INCLINE,
]
FAULTS = [FaultType.NONE, FaultType.LOCKED, FaultType.FREE, FaultType.PARTIAL_TORQUE]


def healthy_calibration():
    records = []
    for controller in CONTROLLERS:
        _, metrics = run_single_episode(
            controller_type=controller,
            fault_type=FaultType.NONE,
            fault_time=4.0,
            duration=10.0,
            gui=False,
            record_video=False,
            seed=1,
        )
        records.append({
            "controller": controller,
            "metrics": {
                key: float(metrics[key])
                for key in (
                    "v_pre", "forward_progress", "lateral_drift",
                    "stall_fraction", "heading_deviation_deg",
                )
            },
        })
    return records


def configuration_matrix():
    rows = []
    expected = {
        FaultType.NONE: 8.0,
        FaultType.LOCKED: 0.0,
        FaultType.FREE: 0.0,
        FaultType.PARTIAL_TORQUE: 2.4,
    }
    for environment in ENVIRONMENTS:
        for fault in FAULTS:
            env = SimulationEnvironment(
                gui=False,
                env_type=environment,
                incline_deg=10.0,
            )
            try:
                robot = SnakeRobot(env.physics_client)
                params = {"gamma_f": 0.3} if fault == FaultType.PARTIAL_TORQUE else {}
                if fault != FaultType.NONE:
                    robot.inject_fault(3, fault, params)
                commands = robot.apply_joint_commands([0.2] * robot.num_joints)
                for _ in range(3):
                    p.stepSimulation(physicsClientId=env.physics_client)
                passed = abs(commands[3] - expected[fault]) < 1e-9
                rows.append({
                    "environment": environment,
                    "fault": fault,
                    "passed": bool(passed),
                    "commanded_torque": float(commands[3]),
                    "surface_count": len(env.surface_ids),
                })
            finally:
                env.close()
    return rows


def plot_healthy(records):
    labels = [r["controller"] for r in records]
    metrics = [
        ("forward_progress", "Forward progress (m)", "higher is better"),
        ("lateral_drift", "Windowed lateral drift (m)", "lower is better"),
        ("stall_fraction", "Stall fraction", "lower is better"),
        ("heading_deviation_deg", "Windowed heading deviation (deg)", "lower is better"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=180)
    colors = ["#e74c3c", "#e67e22", "#f39c12", "#9b59b6", "#27ae60", "#2980b9"]
    for ax, (key, ylabel, direction) in zip(axes.flat, metrics):
        values = [r["metrics"][key] for r in records]
        bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.5)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} ({direction})")
        ax.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle("Healthy calibration: task-level capability metrics", fontsize=14, fontweight="bold")
    fig.text(0.5, 0.01, "One real PyBullet episode per controller; seed=1, duration=10 s, no fault", ha="center")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    path = OUTPUT_DIR / "healthy_capability_metrics.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_matrix(rows):
    env_labels = ["flat", "low_friction", "variable_friction", "incline"]
    fault_labels = ["none", "locked", "free", "partial_torque"]
    values = np.zeros((len(env_labels), len(fault_labels)))
    for row in rows:
        values[env_labels.index(row["environment"]), fault_labels.index(row["fault"])] = row["passed"]
    fig, ax = plt.subplots(figsize=(9, 5), dpi=180)
    im = ax.imshow(values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(fault_labels)), fault_labels, rotation=20, ha="right")
    ax.set_yticks(range(len(env_labels)), env_labels)
    ax.set_xlabel("Fault type")
    ax.set_ylabel("Environment")
    ax.set_title("Environment × fault configuration validation")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, "PASS" if values[i, j] else "FAIL", ha="center", va="center", fontweight="bold")
    fig.colorbar(im, ax=ax, ticks=[0, 1], label="Validation status")
    fig.tight_layout()
    path = OUTPUT_DIR / "environment_fault_validation.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    healthy = healthy_calibration()
    matrix = configuration_matrix()
    payload = {"healthy_calibration": healthy, "configuration_matrix": matrix}
    json_path = OUTPUT_DIR / "validation_metrics.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    healthy_path = plot_healthy(healthy)
    matrix_path = plot_matrix(matrix)
    print(f"saved {json_path}")
    print(f"saved {healthy_path}")
    print(f"saved {matrix_path}")
    print(f"configuration_pass={sum(row['passed'] for row in matrix)}/{len(matrix)}")


if __name__ == "__main__":
    main()
