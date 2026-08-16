"""
Hyperparameter Sensitivity Sweep Runner for AHM-CPG Snake Robot.
Evaluates 2D parameter grids:
  1. Diffusion Coefficient D_h vs Secretion Rate alpha_h
  2. Hill Threshold K_h vs Hill Exponent m

Features:
  - Multi-Core Parallel Execution (multiprocessing.Pool) with safe process lifecycle.
  - Generates both rv_matrix and trec_matrix for complete recovery dynamics characterization.
  - Outputs results/publication/data/sensitivity_results.json.
  - Generates publication figures in results/publication/figures/fig11_sensitivity_analysis.png
    and results/publication/prelim_figures/stage5_sensitivity_heatmaps.png.
"""

import sys
import os
import json
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import SimConfig, RobotConfig, HormoneConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from analysis.metrics import LocomotionMetrics

OUTPUT_PATH = PROJECT_ROOT / "results" / "publication" / "data" / "sensitivity_results.json"
FIG_DIR = PROJECT_ROOT / "results" / "publication" / "prelim_figures"
PUB_FIG_DIR = PROJECT_ROOT / "results" / "publication" / "figures"


def evaluate_episode(dh, alpha_h, kh, hill_m, fault_joint=3, duration=60.0, fault_time=18.0, seed=42):
    """Run episode with specific hormone parameters using clean instance parameter overrides."""
    np.random.seed(seed)
    
    env = None
    try:
        env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
        robot = SnakeRobot(physics_client=env.physics_client)
        controller = AHMCPGController(
            num_joints=robot.num_joints,
            dh=dh,
            alpha_h=alpha_h,
            kh=kh,
            hill_m=hill_m
        )
        
        history = {
            "time": [], "base_position": [], "base_velocity": [],
            "joint_angles": [], "target_angles": [], "joint_torques": [],
            "joint_velocities": [], "hormones": [], "receptors": []
        }
        
        sim_steps = int(duration / SimConfig.TIMESTEP)
        ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
        target_angles = np.zeros(robot.num_joints)
        fault_injected = False
        
        for step in range(sim_steps):
            current_time = step * SimConfig.TIMESTEP
            if not fault_injected and current_time >= fault_time:
                robot.inject_fault(joint_idx=fault_joint, fault_type=FaultType.LOCKED)
                fault_injected = True
                
            sensory = robot.get_sensory_feedback()
            if step % ctrl_substeps == 0:
                target_angles, ctrl_info = controller.step(sensory)
                
            applied_torques = robot.apply_joint_commands(target_angles)
            env.step()
            
            if step % ctrl_substeps == 0:
                history["time"].append(current_time)
                history["base_position"].append(sensory["base_position"].tolist())
                history["base_velocity"].append(sensory["base_velocity"].tolist())
                history["joint_angles"].append(sensory["joint_angles"].tolist())
                history["target_angles"].append(target_angles.tolist() if hasattr(target_angles, 'tolist') else list(target_angles))
                history["joint_velocities"].append(sensory["joint_velocities"].tolist())
                history["joint_torques"].append(applied_torques)
                history["hormones"].append(ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist() if hasattr(ctrl_info.get("hormones", None), 'tolist') else list(ctrl_info.get("hormones", [0]*robot.num_joints)))
                history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist() if hasattr(ctrl_info.get("receptors", None), 'tolist') else list(ctrl_info.get("receptors", [0]*robot.num_joints)))
            
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=fault_time, sim_duration=duration)
        return {
            "recovery_ratio": float(metrics["recovery_ratio"]),
            "recovery_time": float(metrics["recovery_time"]),
            "t_adapt": float(metrics.get("t_adapt", metrics["recovery_time"])),
            "cost_of_transport": float(metrics["cost_of_transport"]),
            "distance_traveled": float(metrics["distance_traveled"])
        }
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def _sensitivity_worker(args):
    dh, alpha_h, kh, hill_m = args
    res = evaluate_episode(dh=dh, alpha_h=alpha_h, kh=kh, hill_m=hill_m)
    return (dh, alpha_h, kh, hill_m, res)


def main():
    print("\n" + "="*90)
    print("  HYPERPARAMETER SENSITIVITY SWEEP & 2D HEATMAP DIAGNOSTICS")
    print(f"  Baseline Config: ALPHA_H={HormoneConfig.ALPHA_H}, D0={HormoneConfig.D0}, DH={HormoneConfig.DIFFUSION_DH}, KH={HormoneConfig.KH}, HILL_M={HormoneConfig.HILL_M}")
    print("="*90 + "\n")

    dh_grid = [0.01, 0.03, 0.06, 0.12, 0.20, 0.35]
    alpha_grid = [0.10, 0.20, 0.30, 0.37, 0.50, 0.70, 0.90]
    
    kh_grid = [0.35, 0.50, 0.65, 0.75, 0.85]
    m_grid = [1.2, 2.0, 3.0, 4.0, 5.0]

    # Build tasks for Grid 1: D_h vs alpha_h (using baseline KH=0.65, HILL_M=4.0)
    base_kh = HormoneConfig.KH
    base_m = HormoneConfig.HILL_M
    base_dh = HormoneConfig.DIFFUSION_DH
    base_alpha = HormoneConfig.ALPHA_H

    tasks_1 = []
    for dh in dh_grid:
        for alpha_h in alpha_grid:
            tasks_1.append((dh, alpha_h, base_kh, base_m))

    # Build tasks for Grid 2: K_h vs m (using baseline D_h=0.06, alpha_h=0.37)
    tasks_2 = []
    for kh in kh_grid:
        for m_val in m_grid:
            tasks_2.append((base_dh, base_alpha, kh, m_val))

    all_tasks = tasks_1 + tasks_2
    num_workers = min(6, max(1, cpu_count()))

    print(f"  Running {len(all_tasks)} sensitivity episodes across {num_workers} parallel CPU cores...")
    pool = Pool(processes=num_workers)
    try:
        results_list = pool.map(_sensitivity_worker, all_tasks)
    finally:
        pool.terminate()
        pool.close()

    # Parse Grid 1: D_h vs alpha_h
    rv_dh_alpha = np.zeros((len(dh_grid), len(alpha_grid)))
    trec_dh_alpha = np.zeros((len(dh_grid), len(alpha_grid)))
    for dh, alpha_h, kh, hill_m, res in results_list[:len(tasks_1)]:
        r_i = dh_grid.index(dh)
        c_i = alpha_grid.index(alpha_h)
        rv_dh_alpha[r_i, c_i] = res["recovery_ratio"]
        trec_dh_alpha[r_i, c_i] = res["recovery_time"]

    # Parse Grid 2: K_h vs m
    rv_kh_m = np.zeros((len(kh_grid), len(m_grid)))
    trec_kh_m = np.zeros((len(kh_grid), len(m_grid)))
    for dh, alpha_h, kh, hill_m, res in results_list[len(tasks_1):]:
        r_i = kh_grid.index(kh)
        c_i = m_grid.index(hill_m)
        rv_kh_m[r_i, c_i] = res["recovery_ratio"]
        trec_kh_m[r_i, c_i] = res["recovery_time"]

    # Save JSON results with both rv_matrix and trec_matrix
    json_results = {
        "dh_alpha_grid": {
            "dh_values": dh_grid,
            "alpha_values": alpha_grid,
            "rv_matrix": rv_dh_alpha.tolist(),
            "trec_matrix": trec_dh_alpha.tolist()
        },
        "kh_m_grid": {
            "kh_values": kh_grid,
            "m_values": m_grid,
            "rv_matrix": rv_kh_m.tolist(),
            "trec_matrix": trec_kh_m.tolist()
        }
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(json_results, f, indent=2)
    print(f"  [OK] Saved Sensitivity Data JSON: {OUTPUT_PATH}")

    # Generate 300-DPI Publication 2D Heatmap Figure (Prelim)
    print("  Generating 300-DPI 2D Sensitivity Heatmap Figure...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    # Heatmap 1: D_h vs alpha_h
    im1 = ax1.imshow(rv_dh_alpha, cmap='viridis', aspect='auto', origin='lower')
    ax1.set_xticks(range(len(alpha_grid)))
    ax1.set_yticks(range(len(dh_grid)))
    ax1.set_xticklabels([f"{v:.2f}" for v in alpha_grid])
    ax1.set_yticklabels([f"{v:.2f}" for v in dh_grid])
    ax1.set_xlabel("Hormone Secretion Rate $\\alpha_h$", fontsize=10, fontweight='bold')
    ax1.set_ylabel("1D Spine Diffusion Coefficient $D_h$", fontsize=10, fontweight='bold')
    ax1.set_title("(A) Locomotion Recovery $R_D$: $D_h$ vs $\\alpha_h$", fontsize=11, fontweight='bold')

    for r in range(len(dh_grid)):
        for c in range(len(alpha_grid)):
            val = rv_dh_alpha[r, c]
            col = "black" if val > 0.60 else "white"
            ax1.text(c, r, f"{val:.2f}", ha='center', va='center', color=col, fontsize=8, fontweight='bold')

    fig.colorbar(im1, ax=ax1, label="Recovery Ratio $R_D$")

    # Heatmap 2: K_h vs m
    im2 = ax2.imshow(rv_kh_m, cmap='plasma', aspect='auto', origin='lower')
    ax2.set_xticks(range(len(m_grid)))
    ax2.set_yticks(range(len(kh_grid)))
    ax2.set_xticklabels([f"{v:.1f}" for v in m_grid])
    ax2.set_yticklabels([f"{v:.2f}" for v in kh_grid])
    ax2.set_xlabel("Hill Steepness Exponent $m$", fontsize=10, fontweight='bold')
    ax2.set_ylabel("Receptor Half-Activation Threshold $K_h$", fontsize=10, fontweight='bold')
    ax2.set_title("(B) Locomotion Recovery $R_D$: $K_h$ vs $m$", fontsize=11, fontweight='bold')

    for r in range(len(kh_grid)):
        for c in range(len(m_grid)):
            val = rv_kh_m[r, c]
            col = "black" if val > 0.60 else "white"
            ax2.text(c, r, f"{val:.2f}", ha='center', va='center', color=col, fontsize=8, fontweight='bold')

    fig.colorbar(im2, ax=ax2, label="Recovery Ratio $R_D$")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = FIG_DIR / "stage5_sensitivity_heatmaps.png"
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved Sensitivity Heatmap Figure: {fig_path}")

    # Generate 4-panel publication figure via analysis.plot_sensitivity
    try:
        from analysis.plot_sensitivity import plot_sensitivity
        plot_sensitivity()
    except Exception as e:
        print(f"  [Info] plot_sensitivity call: {e}")

    print("\nHyperparameter Sensitivity Analysis Complete.\n")


if __name__ == "__main__":
    main()
