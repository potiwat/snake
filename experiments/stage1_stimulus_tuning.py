"""
Formal Gradient-Free Optimization Stage 1: Nelder-Mead Simplex Search on Continuous Weight Space.
Uses scipy.optimize.minimize (method='Nelder-Mead' on Simplex sum(w) = 1.0, w_i >= 0.05) to:
  1. Explore continuous weight space w = (w_q, w_v, w_tau, w_P) without getting trapped by noisy physics gradients.
  2. Maximize multi-fault contrast across ALL 4 Scenarios:
     - Scenario 1: Normal Gait (S_norm)
     - Scenario 2: Locked Joint Fault (S_lock)
     - Scenario 3: Free Joint Fault (S_free)
     - Scenario 4: Partial Torque Drop Fault (S_part)
  3. Track and plot the formal Optimization Convergence Trajectory J(w^(k)) vs Iteration Step k.

Outputs:
  - Directly updates config.py with converged optimal weights W_Q*, W_V*, W_TAU*, W_P*.
  - Saves standalone 300-DPI publication figures (legends placed OUTSIDE plot area):
     * stage1_fig1_optimization_convergence.png
     * stage1_fig2_raw_error_components.png
     * stage1_fig3_optimal_stimulus_time_series.png
     * stage1_fig4_scenarios_contrast_barchart.png
  - Saves full iteration trajectory to results/publication/data/prelim_4stage/stage1_results.json.
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


def _evaluate_single_episode(args):
    fault_type, weights = args
    W_Q, W_V, W_TAU, W_P = weights

    # Apply weights locally in worker process
    HormoneConfig.W_Q = W_Q
    HormoneConfig.W_V = W_V
    HormoneConfig.W_TAU = W_TAU
    HormoneConfig.W_P = W_P

    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
    robot = SnakeRobot(physics_client=env.physics_client)
    np.random.seed(42)
    controller = AHMCPGController(num_joints=robot.num_joints)

    history = {
        "time": [], "base_position": [], "base_velocity": [],
        "joint_angles": [], "target_angles": [], "joint_torques": [],
        "joint_velocities": [], "hormones": [], "receptors": [],
        "stimuli": [], "errors_q": [], "errors_v": [], "errors_tau": [], "power": []
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

            eq = np.mean(controller.hormone_engine.e_q_buffers[fj]) if len(controller.hormone_engine.e_q_buffers[fj]) > 0 else 0.0
            ev = np.mean(controller.hormone_engine.e_v_buffers[fj]) if len(controller.hormone_engine.e_v_buffers[fj]) > 0 else 0.0
            etau = np.mean(controller.hormone_engine.e_tau_buffers[fj]) if len(controller.hormone_engine.e_tau_buffers[fj]) > 0 else 0.0
            p_mech = np.mean(controller.hormone_engine.p_buffers[fj]) if len(controller.hormone_engine.p_buffers[fj]) > 0 else 0.0

            history["errors_q"].append(eq)
            history["errors_v"].append(ev)
            history["errors_tau"].append(etau)
            history["power"].append(p_mech)

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(applied_torques)

        env.step()

    env.close()
    return history


def update_config_py_stage1(best_weights):
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"W_Q\s*=\s*[\d\.]+", f"W_Q = {best_weights[0]:.2f}", content)
    content = re.sub(r"W_V\s*=\s*[\d\.]+", f"W_V = {best_weights[1]:.2f}", content)
    content = re.sub(r"W_TAU\s*=\s*[\d\.]+", f"W_TAU = {best_weights[2]:.2f}", content)
    content = re.sub(r"W_P\s*=\s*[\d\.]+", f"W_P = {best_weights[3]:.2f}", content)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Updated config.py with Converged Optimal Weights: W_Q={best_weights[0]:.2f}, W_V={best_weights[1]:.2f}, W_TAU={best_weights[2]:.2f}, W_P={best_weights[3]:.2f}")


iteration_counter = 0
optimization_history = []
evaluated_cache = {}


def evaluate_weight_vector(w_candidate, pool):
    global iteration_counter, optimization_history, evaluated_cache

    # Project & normalize candidate weight vector onto 4-simplex sum(w) = 1.0, w_i >= 0.05
    w_norm = np.clip(w_candidate, 0.05, 0.85)
    w_norm = w_norm / np.sum(w_norm)
    key = tuple(np.round(w_norm, 3))

    if key in evaluated_cache:
        return evaluated_cache[key]["loss"]

    iteration_counter += 1

    tasks = [
        (FaultType.NONE, w_norm),
        (FaultType.LOCKED, w_norm),
        (FaultType.FREE, w_norm),
        (FaultType.PARTIAL_TORQUE, w_norm)
    ]

    results = pool.map(_evaluate_single_episode, tasks)
    fj = SimConfig.DEFAULT_FAULT_JOINT

    hist_norm, hist_lock, hist_free, hist_part = results
    t = np.array(hist_lock["time"])
    post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0]

    s_norm = float(np.mean(np.array(hist_norm["stimuli"])[post_idx[-100:], fj]))
    s_locked = float(np.mean(np.array(hist_lock["stimuli"])[post_idx[-100:], fj]))
    s_free = float(np.mean(np.array(hist_free["stimuli"])[post_idx[-100:], fj]))
    s_part = float(np.mean(np.array(hist_part["stimuli"])[post_idx[-100:], fj]))

    c_locked = s_locked / max(0.001, s_norm)
    c_free = s_free / max(0.001, s_norm)
    c_part = s_part / max(0.001, s_norm)

    score = (c_locked * 0.45) + (c_free * 0.35) + (c_part * 0.20)
    loss = -score # Minimize negative score

    rec = {
        "step": iteration_counter,
        "weights": w_norm.tolist(),
        "score": score,
        "loss": loss,
        "s_norm": s_norm, "s_locked": s_locked, "s_free": s_free, "s_part": s_part,
        "c_locked": c_locked, "c_free": c_free, "c_part": c_part,
        "histories": {"norm": hist_norm, "lock": hist_lock, "free": hist_free, "part": hist_part}
    }
    optimization_history.append(rec)
    evaluated_cache[key] = rec

    print(f"  Iter {iteration_counter:>2d} | w=({w_norm[0]:.2f}, {w_norm[1]:.2f}, {w_norm[2]:.2f}, {w_norm[3]:.2f}) | S_norm={s_norm:.3f} | S_lock={s_locked:.3f} | S_free={s_free:.3f} | S_part={s_part:.3f} | Score={score:.2f}")
    return loss


def run_stage1_formal_optimization():
    global iteration_counter, optimization_history, evaluated_cache
    iteration_counter = 0
    optimization_history = []
    evaluated_cache = {}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    print("\n" + "="*115)
    print("  FORMAL GRADIENT-FREE OPTIMIZATION STAGE 1: NELDER-MEAD SIMPLEX SEARCH")
    print("  Algorithm: Scipy Nelder-Mead on Simplex sum(w) = 1.0 across ALL 4 Scenarios")
    print("="*115 + "\n")

    num_workers = min(4, max(1, cpu_count()))

    with Pool(processes=num_workers) as pool:
        def obj_func(w):
            return evaluate_weight_vector(w, pool)

        # Initial Simplex spanning dominant basis directions:
        # Vertex 0: Position Dominant
        # Vertex 1: Velocity Dominant
        # Vertex 2: Torque Dominant
        # Vertex 3: Power Dominant
        initial_simplex = np.array([
            [0.60, 0.20, 0.10, 0.10],
            [0.20, 0.60, 0.10, 0.10],
            [0.20, 0.10, 0.60, 0.10],
            [0.20, 0.10, 0.10, 0.60],
            [0.25, 0.25, 0.25, 0.25]
        ])

        print("  Starting Nelder-Mead Simplex Optimization Solver across 5 basis vertices...")
        res = minimize(
            obj_func,
            x0=[0.25, 0.25, 0.25, 0.25],
            method='Nelder-Mead',
            options={'initial_simplex': initial_simplex, 'maxiter': 30, 'xatol': 1e-2, 'fatol': 1e-2, 'disp': True}
        )

    # Extract best normalized simplex weight vector from optimization trajectory
    best_rec = max(optimization_history, key=lambda x: x["score"])
    w_opt = np.array(best_rec["weights"])
    print("\n" + "="*115)
    print(f"  [CONVERGED] Mathematically Optimal Weight Vector w*: W_Q={w_opt[0]:.2f}, W_V={w_opt[1]:.2f}, W_TAU={w_opt[2]:.2f}, W_P={w_opt[3]:.2f} (Score={best_rec['score']:.2f})")
    print("="*115 + "\n")

    update_config_py_stage1(w_opt)

    best_rec = max(optimization_history, key=lambda x: x["score"])

    # -------------------------------------------------------------------
    # GENERATE 4 STANDALONE 300-DPI PUBLICATION FIGURES
    # -------------------------------------------------------------------
    print("\n  Generating 4 Standalone 300-DPI Publication Figures (Legends placed OUTSIDE plot area)...")

    # --- Figure 1: Optimization Convergence Trajectory ---
    fig1, ax1_1 = plt.subplots(figsize=(8.5, 4.8))
    steps = [r["step"] for r in optimization_history]
    scores = [r["score"] for r in optimization_history]
    w_q_trajectory = [r["weights"][0] for r in optimization_history]
    w_v_trajectory = [r["weights"][1] for r in optimization_history]
    w_tau_trajectory = [r["weights"][2] for r in optimization_history]
    w_p_trajectory = [r["weights"][3] for r in optimization_history]

    ax1_1.plot(steps, scores, 'o-', color='#27ae60', linewidth=2.5, markersize=6, label='Objective Score $J(\\mathbf{w}^{(k)})$')
    ax1_1.set_xlabel("Nelder-Mead Iteration Step $k$", fontsize=10)
    ax1_1.set_ylabel("Multi-Fault Contrast Score", fontsize=10, color='#27ae60')
    ax1_1.tick_params(axis='y', labelcolor='#27ae60')
    ax1_1.grid(True, linestyle='--', alpha=0.3)

    ax1_2 = ax1_1.twinx()
    ax1_2.plot(steps, w_q_trajectory, 's--', color='#e74c3c', label='$W_Q$ (Position)')
    ax1_2.plot(steps, w_v_trajectory, '^--', color='#3498db', label='$W_V$ (Velocity)')
    ax1_2.plot(steps, w_tau_trajectory, 'd--', color='#9b59b6', label='$W_{\\tau}$ (Torque Sat)')
    ax1_2.plot(steps, w_p_trajectory, 'x--', color='#f39c12', label='$W_P$ (Power)')
    ax1_2.set_ylabel("Weight Component Magnitude", fontsize=10)

    lines1, labels1 = ax1_1.get_legend_handles_labels()
    lines2, labels2 = ax1_2.get_legend_handles_labels()
    ax1_1.legend(lines1 + lines2, labels1 + labels2, bbox_to_anchor=(1.12, 1.0), loc='upper left', fontsize=9, frameon=True)

    plt.title("Figure 1: Stage 1 Nelder-Mead Optimization Convergence Trajectory", fontweight='bold', fontsize=11)
    fig1_path = os.path.join(FIG_DIR, "stage1_fig1_optimization_convergence.png")
    plt.savefig(fig1_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 1: {fig1_path}")

    # --- Figure 2: Raw Error Components ---
    best_hist_lock = best_rec["histories"]["lock"]
    t = np.array(best_hist_lock["time"])

    fig2, ax2 = plt.subplots(figsize=(8, 4.5))
    ax2.plot(t, best_hist_lock["errors_q"], label="$e_q$ (Position Tracking Error)", color='#e74c3c', linewidth=2.0)
    ax2.plot(t, best_hist_lock["errors_v"], label="$e_v$ (Velocity Error)", color='#3498db', linewidth=2.0)
    ax2.plot(t, best_hist_lock["errors_tau"], label="$e_{\\tau}$ (Torque Saturation Error)", color='#9b59b6', linewidth=2.0)
    ax2.plot(t, best_hist_lock["power"], label="$P_{\\mathrm{mech}}$ (Mechanical Power)", color='#f39c12', linewidth=2.0)
    ax2.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='black', linestyle='--', label='Fault Injection Time (18s)')
    ax2.set_title("Figure 2: Raw Error Signal Components ($e_q, e_v, e_{\\tau}, P_{\\mathrm{mech}}$)", fontweight='bold', fontsize=11)
    ax2.set_xlabel("Time (s)", fontsize=10)
    ax2.set_ylabel("Error Component Magnitude", fontsize=10)
    ax2.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9, frameon=True)
    ax2.grid(True, linestyle='--', alpha=0.3)
    fig2_path = os.path.join(FIG_DIR, "stage1_fig2_raw_error_components.png")
    plt.savefig(fig2_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 2: {fig2_path}")

    # --- Figure 3: Optimal Stimulus Time Series across ALL 4 Scenarios ---
    fj = SimConfig.DEFAULT_FAULT_JOINT
    s_norm_t = np.array(best_rec["histories"]["norm"]["stimuli"])[:, fj]
    s_lock_t = np.array(best_rec["histories"]["lock"]["stimuli"])[:, fj]
    s_free_t = np.array(best_rec["histories"]["free"]["stimuli"])[:, fj]
    s_part_t = np.array(best_rec["histories"]["part"]["stimuli"])[:, fj]

    fig3, ax3 = plt.subplots(figsize=(8, 4.5))
    ax3.plot(t, s_norm_t, label="1. Normal Gait $S_4(t)$", color='#2ecc71', linewidth=1.8)
    ax3.plot(t, s_lock_t, label="2. Locked Joint Fault $S_4(t)$", color='#e74c3c', linewidth=2.2)
    ax3.plot(t, s_free_t, label="3. Free Joint Fault $S_4(t)$", color='#f39c12', linewidth=2.0)
    ax3.plot(t, s_part_t, label="4. Partial Torque Drop $S_4(t)$", color='#9b59b6', linewidth=2.0)
    ax3.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='black', linestyle='--', label='Fault Time (18s)')
    ax3.set_title(f"Figure 3: Converged Optimal Stimulus $S_4^*(t)$ across ALL 4 Scenarios", fontweight='bold', fontsize=11)
    ax3.set_xlabel("Time (s)", fontsize=10)
    ax3.set_ylabel("Stimulus Magnitude $S_4(t)$", fontsize=10)
    ax3.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9, frameon=True)
    ax3.grid(True, linestyle='--', alpha=0.3)
    fig3_path = os.path.join(FIG_DIR, "stage1_fig3_optimal_stimulus_time_series.png")
    plt.savefig(fig3_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 3: {fig3_path}")

    # --- Figure 4: Scenarios Contrast Bar Chart ---
    fig4, ax4 = plt.subplots(figsize=(8, 4.5))
    scenarios = ['1. Normal Gait', '2. Locked Fault', '3. Free Fault', '4. Partial Torque']
    s_vals = [best_rec["s_norm"], best_rec["s_locked"], best_rec["s_free"], best_rec["s_part"]]
    c_ratios = [1.0, best_rec["c_locked"], best_rec["c_free"], best_rec["c_part"]]
    bars_cols = ['#2ecc71', '#e74c3c', '#f39c12', '#9b59b6']

    bars = ax4.bar(scenarios, s_vals, color=bars_cols, alpha=0.85, edgecolor='black', width=0.5)

    for idx, bar in enumerate(bars):
        yval = bar.get_height()
        c_txt = f"{c_ratios[idx]:.2f}x" if idx > 0 else "Baseline"
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + 0.02, f"{yval:.3f}\n({c_txt})", ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax4.set_title("Figure 4: Converged Steady-State Stimulus $S_i$ & Contrast Ratios across Scenarios", fontweight='bold', fontsize=11)
    ax4.set_ylabel("Stimulus Magnitude $S_i$", fontsize=10)
    ax4.set_ylim(0, max(s_vals)*1.25)
    ax4.grid(True, linestyle='--', alpha=0.3)
    fig4_path = os.path.join(FIG_DIR, "stage1_fig4_scenarios_contrast_barchart.png")
    plt.savefig(fig4_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Saved Figure 4: {fig4_path}")

    clean_history = []
    for r in optimization_history:
        clean_history.append({
            "step": r["step"], "weights": r["weights"], "score": r["score"], "loss": r["loss"],
            "s_norm": r["s_norm"], "s_locked": r["s_locked"], "s_free": r["s_free"], "s_part": r["s_part"],
            "c_locked": r["c_locked"], "c_free": r["c_free"], "c_part": r["c_part"]
        })

    with open(os.path.join(OUTPUT_DIR, "stage1_results.json"), "w", encoding="utf-8") as f:
        json.dump({"converged_weights": w_opt.tolist(), "history": clean_history}, f, indent=2)

    print(f"\nFormal Stage 1 Optimization Complete. Converged Weight Vector: w* = {w_opt.round(2)}\n")


if __name__ == "__main__":
    run_stage1_formal_optimization()
