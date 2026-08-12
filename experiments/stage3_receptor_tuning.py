"""
Standalone Stage 3: Hill Receptor Activation Optimization & Diagnostic Analysis (K_h, m).
Reads optimal stimulus weights & hormone dynamics directly from config.py (updated in Stages 1 & 2).
Optimizes Hill Receptor parameters (K_h, m) to achieve:
  1. Low background receptor activation during normal gait (R_normal < 0.05).
  2. Proportional partial gating for moderate faults (R_free ~ 0.35).
  3. High reconfiguration gating for total lock faults (R_locked ~ 0.70-0.90).

Plots:
  - Time-series curves of Hormone input H_i(t) vs Receptor output R_i(t).
  - Sigmoidal Transfer Function Curve R(H) with operating points marked for Normal, Free, and Locked faults.

Outputs:
  - Directly updates config.py with optimal KH, HILL_M.
  - Saves results to results/publication/data/prelim_4stage/stage3_results.json.
"""

import sys
import os
import json
import time
import re
from pathlib import Path
from multiprocessing import Pool, cpu_count

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import SimConfig, RobotConfig, HormoneConfig, CPGConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController

OUTPUT_DIR = "results/publication/data/prelim_4stage"
FIG_DIR = "results/publication/prelim_figures"


def _stage3_worker(args):
    fault_type, params = args
    KH, HILL_M = params

    # Set parameters locally in worker process
    HormoneConfig.KH = KH
    HormoneConfig.HILL_M = HILL_M

    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
    robot = SnakeRobot(physics_client=env.physics_client)
    np.random.seed(42)
    controller = AHMCPGController(num_joints=robot.num_joints)

    history = {
        "time": [], "base_position": [], "base_velocity": [],
        "joint_angles": [], "target_angles": [], "joint_torques": [],
        "joint_velocities": [], "hormones": [], "receptors": [],
        "stimuli": []
    }

    sim_steps = int(SimConfig.DEFAULT_DURATION / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    target_angles = np.zeros(robot.num_joints)
    fault_injected = False
    fj = SimConfig.DEFAULT_FAULT_JOINT

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        if current_time >= SimConfig.DEFAULT_FAULT_TIME and not fault_injected:
            params_dict = {"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
            robot.inject_fault(joint_idx=fj, fault_type=fault_type, params=params_dict)
            fault_injected = True

        sensory = robot.get_sensory_feedback()

        if step % ctrl_substeps == 0:
            target_angles, ctrl_info = controller.step(sensory)

            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"].tolist())
            history["base_velocity"].append(sensory["base_velocity"].tolist())
            history["joint_angles"].append(sensory["joint_angles"].tolist())
            history["target_angles"].append(target_angles.tolist() if hasattr(target_angles, 'tolist') else list(target_angles))
            history["joint_velocities"].append(sensory["joint_velocities"].tolist())
            history["hormones"].append(ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist())
            history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist())

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(applied_torques)

        env.step()

    env.close()
    return history


def update_config_py_stage3(best_kh, best_m):
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"KH\s*=\s*[\d\.]+", f"KH = {best_kh:.2f}", content)
    content = re.sub(r"HILL_M\s*=\s*[\d\.]+", f"HILL_M = {best_m:.1f}", content)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Updated config.py with Stage 3 Best Receptor: KH={best_kh:.2f}, HILL_M={best_m:.1f}")


def run_stage3_optimization():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    print("\n" + "="*95)
    print("  STANDALONE STAGE 3: HILL RECEPTOR ACTIVATION OPTIMIZATION & DIAGNOSTICS")
    print(f"  Using Stage 1 & 2 Parameters from config.py: ALPHA_H={HormoneConfig.ALPHA_H}, D0={HormoneConfig.D0}")
    print("="*95 + "\n")

    kh_list = [0.40, 0.55, 0.65, 0.75, 0.85]
    m_list = [1.2, 2.0, 3.0, 4.0]

    num_workers = min(4, max(1, cpu_count()))
    tasks = []
    combo_keys = []

    for kh in kh_list:
        for m in m_list:
            key = f"Kh_{kh:.2f}_m_{m:.1f}"
            combo_keys.append((kh, m, key))
            tasks.append((FaultType.LOCKED, (kh, m)))
            tasks.append((FaultType.FREE, (kh, m)))

    print(f"  Running {len(tasks)} simulation episodes in parallel across {num_workers} CPU cores...")
    pool = Pool(processes=num_workers)
    try:
        histories = pool.map(_stage3_worker, tasks)
    finally:
        pool.terminate()
        pool.close()

    stage3_results = {}
    best_kh, best_m = 0.65, 2.0
    best_score = -1e9
    fj = SimConfig.DEFAULT_FAULT_JOINT

    print("\n" + "-"*95)
    print(f"{'K_h':<6} | {'m':<4} | {'R_normal':>9} | {'R_free':>8} | {'R_locked':>9} | {'Contrast':>10}")
    print("-" * 95)

    for idx, (kh, m, key) in enumerate(combo_keys):
        hist_lock = histories[2 * idx]
        hist_free = histories[2 * idx + 1]

        r_lock = np.array(hist_lock["receptors"])
        r_free = np.array(hist_free["receptors"])
        t = np.array(hist_lock["time"])

        pre_idx = np.where(t < SimConfig.DEFAULT_FAULT_TIME)[0]
        post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0]

        r_norm = float(np.mean(r_lock[pre_idx, fj]))
        r_locked_ss = float(np.mean(r_lock[post_idx[-100:], fj]))
        r_free_ss = float(np.mean(r_free[post_idx[-100:], fj]))
        r_contrast = r_locked_ss / max(0.001, r_norm)

        # Score receptor: low R_norm (<0.05), R_free ~ 0.35, R_locked ~ 0.70-0.90
        penalty_norm = max(0.0, r_norm - 0.05) * 10.0
        score = (r_locked_ss - r_norm) + (r_locked_ss - r_free_ss) - penalty_norm

        stage3_results[key] = {
            "KH": kh, "HILL_M": m, "r_norm": r_norm,
            "r_locked": r_locked_ss, "r_free": r_free_ss, "r_contrast": r_contrast, "score": score
        }

        if score > best_score:
            best_score = score
            best_kh, best_m = kh, m

        print(f"{kh:<6.2f} | {m:<4.1f} | {r_norm:>9.3f} | {r_free_ss:>8.3f} | {r_locked_ss:>9.3f} | {r_contrast:>10.2f}x")

    print("-" * 95)
    update_config_py_stage3(best_kh, best_m)

    # Plot Input H_i(t) vs Output R_i(t) and Sigmoidal Curve R(H)
    best_combo_idx = [i for i, c in enumerate(combo_keys) if c[0] == best_kh and c[1] == best_m][0]
    best_hist_l = histories[2 * best_combo_idx]
    best_hist_f = histories[2 * best_combo_idx + 1]
    t = np.array(best_hist_l["time"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    h_lock = np.array(best_hist_l["hormones"])[:, fj]
    r_lock = np.array(best_hist_l["receptors"])[:, fj]
    r_free = np.array(best_hist_f["receptors"])[:, fj]

    ax1.plot(t, h_lock, label="Hormone Input $H_4(t)$", color='#e74c3c', linestyle='--', linewidth=1.8)
    ax1.plot(t, r_lock, label="Receptor Output $R_4(t)$ (Locked Fault)", color='#9b59b6', linewidth=2.0)
    ax1.plot(t, r_free, label="Receptor Output $R_4(t)$ (Free Fault)", color='#f39c12', linewidth=1.8)
    ax1.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='black', linestyle='--', label='Fault Time')
    ax1.set_xlabel("Time (s)", fontsize=10)
    ax1.set_ylabel("Level [0, 1]", fontsize=10)
    ax1.set_title(f"Stage 3 Hormone Input $H_4(t)$ vs Receptor Output $R_4(t)$ ($K_h={best_kh}, m={best_m}$)", fontweight='bold', fontsize=10)
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.3)

    # Subpanel 2: Static Sigmoidal Curve R(H)
    h_curve = np.linspace(0.0, 1.0, 200)
    r_curve = (h_curve ** best_m) / (best_kh ** best_m + h_curve ** best_m + 1e-9)

    ax2.plot(h_curve, r_curve, color='#8e44ad', linewidth=2.5, label=f'Hill Function ($K_h={best_kh}, m={best_m}$)')
    
    # Mark operating points
    h_norm_val = float(np.mean(h_lock[:int(SimConfig.DEFAULT_FAULT_TIME/SimConfig.CONTROL_TIMESTEP)]))
    h_locked_val = float(np.mean(h_lock[-100:]))
    h_free_val = float(np.mean(np.array(best_hist_f["hormones"])[-100:, fj]))

    r_norm_val = (h_norm_val ** best_m) / (best_kh ** best_m + h_norm_val ** best_m + 1e-9)
    r_free_val = (h_free_val ** best_m) / (best_kh ** best_m + h_free_val ** best_m + 1e-9)
    r_locked_val = (h_locked_val ** best_m) / (best_kh ** best_m + h_locked_val ** best_m + 1e-9)

    ax2.plot(h_norm_val, r_norm_val, 'go', markersize=8, label=f'Normal Gait ($H={h_norm_val:.2f}, R={r_norm_val:.2f}$)')
    ax2.plot(h_free_val, r_free_val, 'yo', markersize=8, label=f'Free Fault ($H={h_free_val:.2f}, R={r_free_val:.2f}$)')
    ax2.plot(h_locked_val, r_locked_val, 'ro', markersize=8, label=f'Locked Fault ($H={h_locked_val:.2f}, R={r_locked_val:.2f}$)')

    ax2.set_xlabel("Hormone Concentration $H_i$", fontsize=10)
    ax2.set_ylabel("Receptor Activation $R_i$", fontsize=10)
    ax2.set_title("Stage 3 Sigmoidal Hill Transfer Curve $R_i(H_i)$", fontweight='bold', fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle='--', alpha=0.3)

    fig_path = os.path.join(FIG_DIR, "stage3_receptor_diagnostics.png")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved Stage 3 Diagnostic Figure: {fig_path}")

    # Save results JSON
    with open(os.path.join(OUTPUT_DIR, "stage3_results.json"), "w", encoding="utf-8") as f:
        json.dump(stage3_results, f, indent=2)

    print("\nStage 3 Optimization Complete.\n")


if __name__ == "__main__":
    run_stage3_optimization()
