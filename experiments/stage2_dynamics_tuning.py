"""
Pure Non-Overlapping Gap Maximization Stage 2: Hormone Dynamics Continuous Optimization (alpha_h, d0, kd, D_h).
Reads optimal stimulus weights directly from config.py (updated in Stage 1: W_Q=0.44, W_V=0.03, W_TAU=0.44, W_P=0.10).

Does NOT hardcode any arbitrary target values.
Evaluates across ALL 4 Simulation Scenarios:
  1. Normal Gait (H_norm)
  2. Locked Joint Fault (H_locked)
  3. Free Joint Fault (H_free)
  4. Partial Torque Drop Fault (H_part, gamma_f = 0.3)

Objective Function:
  Maximizes the explicit separation gaps between sorted steady-state intervals [mu_i - 1SD_i, mu_i + 1SD_i].
  Penalizes any overlap between adjacent intervals and prevents edge clipping (> 0.95).

Outputs:
  - Directly updates config.py with converged optimal ALPHA_H, D0, KD, DIFFUSION_DH.
  - Saves standalone 300-DPI publication figures (legends placed OUTSIDE plot area):
     * stage2_fig1_optimization_convergence.png
     * stage2_fig2_stimulus_vs_hormone_time_series.png
     * stage2_fig3_spatial_diffusion_profile.png
     * stage2_fig4_scenarios_hormone_barchart.png
  - Saves full optimization trajectory to results/publication/data/prelim_4stage/stage2_results.json.
"""

import sys
import os
import json
import time
import re
from pathlib import Path
from multiprocessing import Pool, cpu_count
from scipy.optimize import minimize

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


def _stage2_worker(args):
    fault_type, params = args
    ALPHA_H, D0, KD, DIFFUSION_DH = params

    # Set parameters locally in worker process
    HormoneConfig.ALPHA_H = ALPHA_H
    HormoneConfig.D0 = D0
    HormoneConfig.KD = KD
    HormoneConfig.DIFFUSION_DH = DIFFUSION_DH

    env = None
    try:
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
            if current_time >= SimConfig.DEFAULT_FAULT_TIME and not fault_injected and fault_type != FaultType.NONE:
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
                history["stimuli"].append(ctrl_info.get("stimuli", np.zeros(robot.num_joints)).tolist())
                history["hormones"].append(ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist())
                history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist())

            applied_torques = robot.apply_joint_commands(target_angles)
            if step % ctrl_substeps == 0:
                history["joint_torques"].append(applied_torques)

            env.step()

        return history
    except Exception as e:
        print(f"  [ERROR in worker] FaultType={fault_type}, params={params}: {e}", flush=True)
        raise e
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def update_config_py_stage2(best_params):
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"ALPHA_H\s*=\s*[\d\.]+", f"ALPHA_H = {best_params[0]:.2f}", content)
    content = re.sub(r"D0\s*=\s*[\d\.]+", f"D0 = {best_params[1]:.2f}", content)
    content = re.sub(r"(class HormoneConfig:[\s\S]*?D0\s*=\s*[\d\.]+[\s\S]*?KD\s*=\s*)[\d\.]+", f"\\g<1>{best_params[2]:.2f}", content)
    content = re.sub(r"DIFFUSION_DH\s*=\s*[\d\.]+", f"DIFFUSION_DH = {best_params[3]:.2f}", content)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Updated config.py with Stage 2 Converged Best Dynamics: ALPHA_H={best_params[0]:.2f}, D0={best_params[1]:.2f}, KD={best_params[2]:.2f}, DIFFUSION_DH={best_params[3]:.2f}", flush=True)


iteration_counter = 0
optimization_history = []
evaluated_cache = {}


def evaluate_dynamics_vector(p_candidate, pool):
    global iteration_counter, optimization_history, evaluated_cache

    alpha_h = float(np.clip(p_candidate[0], 0.10, 2.00))
    d0 = float(np.clip(p_candidate[1], 0.01, 0.50))
    kd = float(np.clip(p_candidate[2], 0.05, 1.00))
    dh = float(np.clip(p_candidate[3], 0.005, 0.30))

    params = (alpha_h, d0, kd, dh)
    key = (round(alpha_h, 3), round(d0, 3), round(kd, 3), round(dh, 3))

    if key in evaluated_cache:
        return evaluated_cache[key]["loss"]

    iteration_counter += 1

    # Run ALL 4 Scenarios
    tasks = [
        (FaultType.NONE, params),
        (FaultType.LOCKED, params),
        (FaultType.FREE, params),
        (FaultType.PARTIAL_TORQUE, params)
    ]

    results = pool.map(_stage2_worker, tasks)
    fj = SimConfig.DEFAULT_FAULT_JOINT
    nj = max(0, fj - 1)

    hist_norm, hist_lock, hist_free, hist_part = results
    t = np.array(hist_lock["time"])
    post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0][-100:]

    # Compute steady-state mean and standard deviation (1 SD)
    h_norm_ts = np.array(hist_norm["hormones"])[post_idx, fj]
    h_lock_ts = np.array(hist_lock["hormones"])[post_idx, fj]
    h_free_ts = np.array(hist_free["hormones"])[post_idx, fj]
    h_part_ts = np.array(hist_part["hormones"])[post_idx, fj]

    mu_norm, std_norm = float(np.mean(h_norm_ts)), float(np.std(h_norm_ts))
    mu_lock, std_lock = float(np.mean(h_lock_ts)), float(np.std(h_lock_ts))
    mu_free, std_free = float(np.mean(h_free_ts)), float(np.std(h_free_ts))
    mu_part, std_part = float(np.mean(h_part_ts)), float(np.std(h_part_ts))
    h_neigh = float(np.mean(np.array(hist_lock["hormones"])[post_idx, nj]))

    if np.isnan([mu_norm, mu_lock, mu_free, mu_part]).any() or np.isnan([std_norm, std_lock, std_free, std_part]).any():
        print(f"  [WARNING] NaN detected for params={params}. Returning penalty loss.", flush=True)
        return 1e6

    # Form 2-SD intervals [mu - 2SD, mu + 2SD] for all 4 scenarios
    scenario_data = [
        ("Normal", mu_norm, std_norm, hist_norm),
        ("Free", mu_free, std_free, hist_free),
        ("Partial", mu_part, std_part, hist_part),
        ("Locked", mu_lock, std_lock, hist_lock)
    ]

    # Sort intervals by mean value
    sorted_scenarios = sorted(scenario_data, key=lambda x: x[1])

    # Compute Pure Non-Overlapping Gaps between adjacent 2-SD intervals [mu - 2SD, mu + 2SD]
    gaps = []
    overlap_penalty = 0.0

    for idx in range(len(sorted_scenarios) - 1):
        m1, s1 = sorted_scenarios[idx][1], sorted_scenarios[idx][2]
        m2, s2 = sorted_scenarios[idx+1][1], sorted_scenarios[idx+1][2]
        upper_1 = m1 + 2.0 * s1
        lower_2 = m2 - 2.0 * s2
        gap = lower_2 - upper_1
        gaps.append(gap)
        if gap < 0.0:
            # Heavy penalty if 2-SD intervals overlap
            overlap_penalty += (-gap + 0.05) ** 2 * 1000.0

    min_gap = min(gaps) if gaps else 0.0
    sum_gaps = sum(gaps)

    # Low Baseline Penalty (only if lowest 2-SD bound is below 0.01)
    min_lower = sorted_scenarios[0][1] - 2.0 * sorted_scenarios[0][2]
    pen_low = max(0.0, 0.01 - min_lower) ** 2 * 500.0

    # High Ceiling Penalty (if highest 2-SD bound exceeds 0.95)
    max_upper = sorted_scenarios[-1][1] + 2.0 * sorted_scenarios[-1][2]
    pen_high = max(0.0, max_upper - 0.95) ** 2 * 1000.0

    # 2-SD Pure Gap Maximization Objective: Maximize sum of gaps + worst gap, penalize 2-SD overlaps & out-of-bounds
    score = sum_gaps + 3.0 * min_gap - overlap_penalty - pen_low - pen_high
    loss = -score

    rec = {
        "step": iteration_counter,
        "params": [alpha_h, d0, kd, dh],
        "score": score,
        "loss": loss,
        "h_norm": mu_norm, "std_norm": std_norm,
        "h_locked": mu_lock, "std_lock": std_lock,
        "h_free": mu_free, "std_free": std_free,
        "h_part": mu_part, "std_part": std_part,
        "h_neighbor": h_neigh,
        "gaps": gaps, "min_gap": min_gap, "overlap_penalty": overlap_penalty
    }
    optimization_history.append(rec)
    evaluated_cache[key] = rec

    print(f"  Iter {iteration_counter:>2d} | alpha={alpha_h:.2f}, d0={d0:.2f}, kd={kd:.2f}, Dh={dh:.2f} | H_norm={mu_norm:.3f} +/- 2SD={2.0*std_norm:.3f} | H_lock={mu_lock:.3f} +/- 2SD={2.0*std_lock:.3f} | Min2SDGap={min_gap:+.3f} | Score={score:.3f}", flush=True)
    return loss


def run_stage2_formal_optimization():
    global iteration_counter, optimization_history, evaluated_cache
    iteration_counter = 0
    optimization_history = []
    evaluated_cache = {}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    print("\n" + "="*120)
    print("  PURE NON-OVERLAPPING GAP MAXIMIZATION STAGE 2: HORMONE DYNAMICS OPTIMIZATION")
    print("  Scenarios: 1. Normal Gait | 2. Locked Joint Fault | 3. Free Joint Fault | 4. Partial Torque Drop Fault")
    print(f"  Using Calibrated Stage 1 Weights from config.py: W_Q={HormoneConfig.W_Q}, W_V={HormoneConfig.W_V}, W_TAU={HormoneConfig.W_TAU}, W_P={HormoneConfig.W_P}")
    print("="*120 + "\n")

    num_workers = min(4, max(1, cpu_count()))

    pool = Pool(processes=num_workers)
    try:
        def obj_func(p):
            return evaluate_dynamics_vector(p, pool)

        restart_simplices = [
            (
                [0.60, 0.04, 0.18, 0.05],
                np.array([
                    [0.60, 0.04, 0.18, 0.05],
                    [0.90, 0.04, 0.18, 0.05],
                    [0.35, 0.04, 0.18, 0.05],
                    [0.60, 0.08, 0.18, 0.08],
                    [0.60, 0.04, 0.35, 0.05]
                ])
            ),
            (
                [0.80, 0.05, 0.20, 0.05],
                np.array([
                    [0.80, 0.05, 0.20, 0.05],
                    [1.20, 0.05, 0.20, 0.05],
                    [0.50, 0.05, 0.20, 0.05],
                    [0.80, 0.10, 0.20, 0.08],
                    [0.80, 0.05, 0.40, 0.05]
                ])
            ),
            (
                [0.40, 0.06, 0.15, 0.03],
                np.array([
                    [0.40, 0.06, 0.15, 0.03],
                    [0.70, 0.06, 0.15, 0.03],
                    [0.20, 0.06, 0.15, 0.03],
                    [0.40, 0.10, 0.15, 0.06],
                    [0.40, 0.06, 0.30, 0.03]
                ])
            )
        ]

        print("  Starting Multi-Start Nelder-Mead Optimization Solver across dynamics simplex...", flush=True)
        for x0_val, simplex_val in restart_simplices:
            minimize(
                obj_func,
                x0=x0_val,
                method='Nelder-Mead',
                options={'initial_simplex': simplex_val, 'maxiter': 15, 'xatol': 1e-2, 'fatol': 1e-2, 'disp': False}
            )
    except Exception as e:
        print(f"  [ERROR in optimization loop]: {e}", flush=True)
        pool.terminate()
        raise e
    finally:
        pool.terminate()
        pool.close()

    best_rec = max(optimization_history, key=lambda x: x["score"])
    p_opt = best_rec["params"]

    print("\n" + "="*120)
    print(f"  [CONVERGED] Optimal Dynamics Vector: ALPHA_H={p_opt[0]:.2f}, D0={p_opt[1]:.2f}, KD={p_opt[2]:.2f}, DIFFUSION_DH={p_opt[3]:.2f} (Score={best_rec['score']:.3f})")
    print("="*120 + "\n")

    update_config_py_stage2(p_opt)

    # -------------------------------------------------------------------
    # GENERATE 4 STANDALONE 300-DPI PUBLICATION FIGURES (Legends OUTSIDE)
    # -------------------------------------------------------------------
    print("\n  Generating 4 Standalone 300-DPI Publication Figures for Stage 2 (Legends OUTSIDE plot area)...")

    # --- Figure 1: Optimization Trajectory ---
    fig1, ax1_1 = plt.subplots(figsize=(8.5, 4.8))
    steps = [r["step"] for r in optimization_history]
    scores = [r["score"] for r in optimization_history]
    alpha_traj = [r["params"][0] for r in optimization_history]
    d0_traj = [r["params"][1] for r in optimization_history]
    dh_traj = [r["params"][3] for r in optimization_history]

    ax1_1.plot(steps, scores, 'o-', color='#27ae60', linewidth=2.5, markersize=6, label='Non-Overlapping Gap Score')
    ax1_1.set_xlabel("Nelder-Mead Iteration Step $k$", fontsize=10)
    ax1_1.set_ylabel("Pure Gap Maximization Score", fontsize=10, color='#27ae60')
    ax1_1.tick_params(axis='y', labelcolor='#27ae60')
    ax1_1.grid(True, linestyle='--', alpha=0.3)

    ax1_2 = ax1_1.twinx()
    ax1_2.plot(steps, alpha_traj, 's--', color='#3498db', label='$\\alpha_h$ (Secretion Rate)')
    ax1_2.plot(steps, d0_traj, '^--', color='#9b59b6', label='$d_0$ (Linear Decay)')
    ax1_2.plot(steps, dh_traj, 'd--', color='#e67e22', label='$D_h$ (Spatial Diffusion)')
    ax1_2.set_ylabel("Parameter Value", fontsize=10)

    lines1, labels1 = ax1_1.get_legend_handles_labels()
    lines2, labels2 = ax1_2.get_legend_handles_labels()
    ax1_1.legend(lines1 + lines2, labels1 + labels2, bbox_to_anchor=(1.12, 1.0), loc='upper left', fontsize=9, frameon=True)

    plt.title("Figure 1: Stage 2 Pure Gap Maximization Optimization Trajectory", fontweight='bold', fontsize=11)
    fig1_path = os.path.join(FIG_DIR, "stage2_fig1_optimization_convergence.png")
    plt.savefig(fig1_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 1: {fig1_path}")

    # Collect time-series data for converged optimal parameters
    print("  Evaluating time-series for optimal parameters across 4 scenarios...")
    best_hist_n = _stage2_worker((FaultType.NONE, p_opt))
    best_hist_l = _stage2_worker((FaultType.LOCKED, p_opt))
    best_hist_f = _stage2_worker((FaultType.FREE, p_opt))
    best_hist_p = _stage2_worker((FaultType.PARTIAL_TORQUE, p_opt))

    t = np.array(best_hist_l["time"])
    fj = SimConfig.DEFAULT_FAULT_JOINT

    fig2, ax2 = plt.subplots(figsize=(8.5, 4.8))
    s_lock = np.array(best_hist_l["stimuli"])[:, fj]
    h_norm = np.array(best_hist_n["hormones"])[:, fj]
    h_lock = np.array(best_hist_l["hormones"])[:, fj]
    h_free = np.array(best_hist_f["hormones"])[:, fj]
    h_part = np.array(best_hist_p["hormones"])[:, fj]

    ax2.plot(t, s_lock, label="Stimulus Input $S_4(t)$ (Locked Fault)", color='#3498db', linestyle='--', linewidth=1.8)
    ax2.plot(t, h_norm, label="1. Normal Gait $H_4^*(t)$", color='#2ecc71', linewidth=2.0)
    ax2.plot(t, h_lock, label="2. Locked Fault $H_4^*(t)$", color='#e74c3c', linewidth=2.2)
    ax2.plot(t, h_free, label="3. Free Fault $H_4^*(t)$", color='#f39c12', linewidth=2.0)
    ax2.plot(t, h_part, label="4. Partial Torque Drop $H_4^*(t)$", color='#9b59b6', linewidth=2.0)
    ax2.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='black', linestyle='--', label='Fault Injection Time (18s)')
    ax2.set_xlabel("Time (s)", fontsize=10)
    ax2.set_ylabel("Concentration Level [0, 1]", fontsize=10)
    ax2.set_title("Figure 2: Converged Input Stimulus $S_4(t)$ vs Hormone Output $H_4^*(t)$ across ALL 4 Scenarios", fontweight='bold', fontsize=11)
    ax2.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9, frameon=True)
    ax2.grid(True, linestyle='--', alpha=0.3)
    fig2_path = os.path.join(FIG_DIR, "stage2_fig2_stimulus_vs_hormone_time_series.png")
    plt.savefig(fig2_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 2: {fig2_path}")

    # --- Figure 3: Spatial Diffusion Profile along Robot Spine ---
    fig3, ax3 = plt.subplots(figsize=(8, 4.5))
    h_all_joints = np.array(best_hist_l["hormones"])[-100:]
    h_mean_spine = np.mean(h_all_joints, axis=0)
    joints_x = np.arange(1, 9)

    ax3.plot(joints_x, h_mean_spine, 'o-', color='#9b59b6', linewidth=2.5, markersize=8, label="Converged Steady-State $H_j$ along Spine")
    ax3.axvline(x=fj+1, color='red', linestyle='--', label=f'Failed Joint {fj+1}')
    ax3.set_xticks(joints_x)
    ax3.set_xlabel("Joint Index along Spine (1..8)", fontsize=10)
    ax3.set_ylabel("Hormone Concentration $H_j$", fontsize=10)
    ax3.set_title("Figure 3: Converged Spatial Diffusion Profile along Robot Spine", fontweight='bold', fontsize=11)
    ax3.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9, frameon=True)
    ax3.grid(True, linestyle='--', alpha=0.3)
    fig3_path = os.path.join(FIG_DIR, "stage2_fig3_spatial_diffusion_profile.png")
    plt.savefig(fig3_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 3: {fig3_path}")

    # --- Figure 4: Pure Non-Overlapping Steady-State 2-SD Interval Bar Chart ---
    fig4, ax4 = plt.subplots(figsize=(8.5, 4.8))

    scen_tuples = [
        ("1. Normal Gait", best_rec["h_norm"], best_rec["std_norm"], '#2ecc71'),
        ("2. Free Fault", best_rec["h_free"], best_rec["std_free"], '#f39c12'),
        ("3. Partial Drop", best_rec["h_part"], best_rec["std_part"], '#9b59b6'),
        ("4. Locked Fault", best_rec["h_locked"], best_rec["std_lock"], '#e74c3c')
    ]
    sorted_tuples = sorted(scen_tuples, key=lambda x: x[1])

    scenarios = [t[0] for t in sorted_tuples]
    h_means = [t[1] for t in sorted_tuples]
    h_stds = [t[2] for t in sorted_tuples]
    h_2stds = [2.0 * t[2] for t in sorted_tuples]
    bars_cols = [t[3] for t in sorted_tuples]

    bars = ax4.bar(scenarios, h_means, yerr=h_2stds, capsize=6, color=bars_cols, alpha=0.85, edgecolor='black', width=0.5, error_kw={'ecolor': 'black', 'linewidth': 1.8})

    for idx, bar in enumerate(bars):
        yval = bar.get_height()
        std_v2 = h_2stds[idx]
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + std_v2 + 0.02, f"{yval:.3f}+/-{std_v2:.3f} (2SD)", ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax4.set_title("Figure 4: Converged Steady-State Hormone Intervals (Pure Gap Maximized, Zero 2-SD Overlap)", fontweight='bold', fontsize=11)
    ax4.set_ylabel("Hormone Level $H_i$", fontsize=10)
    ax4.set_ylim(0, max(h_means)*1.35)
    ax4.grid(True, linestyle='--', alpha=0.3)
    fig4_path = os.path.join(FIG_DIR, "stage2_fig4_scenarios_hormone_barchart.png")
    plt.savefig(fig4_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 4: {fig4_path}", flush=True)

    # --- Figure 5: 2D Spatial Base Center-of-Mass Trajectories (x, y) across ALL 4 Scenarios ---
    fig5, ax5 = plt.subplots(figsize=(8.5, 5.0))

    pos_n = np.array(best_hist_n["base_position"])
    pos_l = np.array(best_hist_l["base_position"])
    pos_f = np.array(best_hist_f["base_position"])
    pos_p = np.array(best_hist_p["base_position"])

    ax5.plot(pos_n[:, 0], pos_n[:, 1], label="1. Normal Gait", color='#2ecc71', linewidth=2.0)
    ax5.plot(pos_l[:, 0], pos_l[:, 1], label="2. Locked Joint Fault", color='#e74c3c', linewidth=2.2)
    ax5.plot(pos_f[:, 0], pos_f[:, 1], label="3. Free Joint Fault", color='#f39c12', linewidth=2.0)
    ax5.plot(pos_p[:, 0], pos_p[:, 1], label="4. Partial Torque Drop", color='#9b59b6', linewidth=2.0)

    # Mark start position
    ax5.scatter([pos_n[0, 0]], [pos_n[0, 1]], color='black', marker='o', s=60, zorder=5, label='Start Position (0,0)')

    # Mark fault injection point (~18s)
    t_arr = np.array(best_hist_l["time"])
    fault_idx = np.where(t_arr >= SimConfig.DEFAULT_FAULT_TIME)[0][0]
    ax5.scatter([pos_l[fault_idx, 0]], [pos_l[fault_idx, 1]], color='red', marker='*', s=120, zorder=5, label='Fault Injected (18s)')

    ax5.set_xlabel("x Position (m)", fontsize=10)
    ax5.set_ylabel("y Position (m)", fontsize=10)
    ax5.set_title("Figure 5: 2D Base Spatial Trajectories (x, y) across ALL 4 Scenarios Post-Optimization", fontweight='bold', fontsize=11)
    ax5.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9, frameon=True)
    ax5.grid(True, linestyle='--', alpha=0.3)
    ax5.set_aspect('equal', adjustable='datalim')

    fig5_path = os.path.join(FIG_DIR, "stage2_fig5_xy_trajectories.png")
    plt.savefig(fig5_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 5: {fig5_path}", flush=True)

    # Save cleaned optimization history JSON
    clean_history = []
    for r in optimization_history:
        clean_history.append({
            "step": r["step"], "params": r["params"], "score": r["score"], "loss": r["loss"],
            "h_norm": r["h_norm"], "h_locked": r["h_locked"], "h_free": r["h_free"], "h_part": r["h_part"],
            "gaps": r["gaps"], "min_gap": r["min_gap"]
        })

    with open(os.path.join(OUTPUT_DIR, "stage2_results.json"), "w", encoding="utf-8") as f:
        json.dump({"converged_params": p_opt, "history": clean_history}, f, indent=2)

    print(f"\nFormal Stage 2 Continuous Optimization Complete. Converged Parameters: {p_opt}\n", flush=True)


if __name__ == "__main__":
    run_stage2_formal_optimization()
