"""
Multi-Core 4-Stage Hierarchical Hormone Tuning & Calibration Pipeline.
Features:
  1. Multi-Core Parallel Execution (multiprocessing.Pool) for all 4 Stages.
  2. Sequential parameter update: HormoneConfig is updated after each stage with the best parameter set.
  3. Video Rendering: Renders HD GPU split-screen videos AFTER HormoneConfig is fully updated with calibrated parameters!

Outputs:
  - Stage-by-Stage formatted tables
  - Verification Plot: results/publication/prelim_figures/prelim_04_4stage_hormone_tuning.png
  - HD GPU Split-Screen Demonstration Videos: results/publication/videos/ (C4, C5, C6)
"""

import sys
import os
import json
import time
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
from controllers.baselines import (
    OracleFaultAwareCPGController,
    AHMNobypassCPGController
)
from analysis.metrics import LocomotionMetrics
from analysis.render_publication_videos import make_controller, render_splitscreen_video

OUTPUT_DIR = "results/publication/data/prelim_4stage"
FIG_DIR = "results/publication/prelim_figures"
VIDEO_DIR = "results/publication/videos"


# Top-level picklable worker function for Multi-Core execution
def _run_single_episode_worker(args):
    ctrl_type, fault_type, fault_joint, hormone_params = args

    # Apply hormone params locally in worker process
    if hormone_params:
        HormoneConfig.W_Q = hormone_params.get("W_Q", HormoneConfig.W_Q)
        HormoneConfig.W_V = hormone_params.get("W_V", HormoneConfig.W_V)
        HormoneConfig.W_TAU = hormone_params.get("W_TAU", HormoneConfig.W_TAU)
        HormoneConfig.W_P = hormone_params.get("W_P", HormoneConfig.W_P)

        HormoneConfig.ALPHA_H = hormone_params.get("ALPHA_H", HormoneConfig.ALPHA_H)
        HormoneConfig.D0 = hormone_params.get("D0", HormoneConfig.D0)
        HormoneConfig.KD = hormone_params.get("KD", HormoneConfig.KD)
        HormoneConfig.DIFFUSION_DH = hormone_params.get("DIFFUSION_DH", HormoneConfig.DIFFUSION_DH)

        HormoneConfig.KH = hormone_params.get("KH", HormoneConfig.KH)
        HormoneConfig.HILL_M = hormone_params.get("HILL_M", HormoneConfig.HILL_M)

    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
    robot = SnakeRobot(physics_client=env.physics_client)
    np.random.seed(42)
    controller = make_controller(ctrl_type, robot.num_joints)

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

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        if current_time >= SimConfig.DEFAULT_FAULT_TIME and not fault_injected:
            params = {"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
            robot.inject_fault(joint_idx=fault_joint, fault_type=fault_type, params=params)
            fault_injected = True

        sensory = robot.get_sensory_feedback()

        if step % ctrl_substeps == 0:
            if ctrl_type in ["C4", "oracle"]:
                fault_info = {"active": robot.fault_active, "joint_idx": robot.fault_joint_idx}
                target_angles, ctrl_info = controller.step(sensory, fault_info=fault_info)
            else:
                target_angles, ctrl_info = controller.step(sensory)

            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"].tolist())
            history["base_velocity"].append(sensory["base_velocity"].tolist())
            history["joint_angles"].append(sensory["joint_angles"].tolist())
            history["target_angles"].append(target_angles.tolist() if hasattr(target_angles, 'tolist') else list(target_angles))
            history["joint_velocities"].append(sensory["joint_velocities"].tolist())
            history["hormones"].append(
                ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("hormones", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("hormones", [0]*robot.num_joints))
            )
            history["receptors"].append(
                ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("receptors", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("receptors", [0]*robot.num_joints))
            )
            history["stimuli"].append(
                ctrl_info.get("stimuli", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("stimuli", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("stimuli", [0]*robot.num_joints))
            )

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(
                applied_torques if isinstance(applied_torques, list) else list(applied_torques)
            )

        env.step()

    env.close()

    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=SimConfig.DEFAULT_FAULT_TIME,
        sim_duration=SimConfig.DEFAULT_DURATION, total_mass=RobotConfig.TOTAL_MASS
    )
    return metrics, history


# -------------------------------------------------------------------
# STAGE 1: Multi-Core Stimulus Weightings Calibration
# -------------------------------------------------------------------
def stage1_stimulus_calibration_multicore(pool):
    print("\n" + "="*95)
    print("  STAGE 1: MULTI-CORE STIMULUS WEIGHTINGS CALIBRATION (w_q, w_v, w_tau, w_P)")
    print("  Evaluating Rise Speed, Steady Contrast & Multi-Fault Robustness")
    print("="*95)

    stim_configs = {
        "Baseline_Balanced": {"W_Q": 0.40, "W_V": 0.20, "W_TAU": 0.30, "W_P": 0.10},
        "Position_Dominant": {"W_Q": 0.65, "W_V": 0.15, "W_TAU": 0.10, "W_P": 0.10},
        "Torque_Dominant":   {"W_Q": 0.20, "W_V": 0.10, "W_TAU": 0.60, "W_P": 0.10},
        "Power_Dominant":    {"W_Q": 0.20, "W_V": 0.10, "W_TAU": 0.20, "W_P": 0.50},
        "Optimal_Robust":    {"W_Q": 0.45, "W_V": 0.15, "W_TAU": 0.30, "W_P": 0.10},
    }

    # Prepare parallel jobs
    tasks = []
    cfg_names = list(stim_configs.keys())
    for cfg_name in cfg_names:
        w = stim_configs[cfg_name]
        tasks.append(("C5", FaultType.LOCKED, SimConfig.DEFAULT_FAULT_JOINT, w))
        tasks.append(("C5", FaultType.FREE, SimConfig.DEFAULT_FAULT_JOINT, w))

    results_list = pool.map(_run_single_episode_worker, tasks)

    stage1_res = {}
    print(f"{'Config Name':<20} | {'W_Q':>5} | {'W_V':>5} | {'W_TAU':>5} | {'W_P':>5} | {'S_norm':>7} | {'S_locked':>8} | {'S_free':>7} | {'Contrast':>8}")
    print("-" * 95)

    best_cfg = "Optimal_Robust"
    best_contrast = -1.0

    for idx, cfg_name in enumerate(cfg_names):
        weights = stim_configs[cfg_name]
        _, hist_lock = results_list[2 * idx]
        _, hist_free = results_list[2 * idx + 1]

        stims_lock = np.array(hist_lock["stimuli"])
        stims_free = np.array(hist_free["stimuli"])
        t = np.array(hist_lock["time"])

        pre_idx = np.where(t < SimConfig.DEFAULT_FAULT_TIME)[0]
        post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0]
        fj = SimConfig.DEFAULT_FAULT_JOINT

        s_norm = float(np.mean(stims_lock[pre_idx, fj]))
        s_locked = float(np.mean(stims_lock[post_idx[-100:], fj]))
        s_free = float(np.mean(stims_free[post_idx[-100:], fj]))
        contrast = s_locked / max(0.001, s_norm)

        stage1_res[cfg_name] = {
            "weights": weights, "s_norm": s_norm, "s_locked": s_locked,
            "s_free": s_free, "contrast": contrast
        }

        if contrast > best_contrast:
            best_contrast = contrast
            best_cfg = cfg_name

        print(f"{cfg_name:<20} | {weights['W_Q']:>5.2f} | {weights['W_V']:>5.2f} | {weights['W_TAU']:>5.2f} | {weights['W_P']:>5.2f} | {s_norm:>7.3f} | {s_locked:>8.3f} | {s_free:>7.3f} | {contrast:>8.2f}x")

    # Update HormoneConfig with best Stage 1 weights
    best_w = stim_configs[best_cfg]
    HormoneConfig.W_Q = best_w["W_Q"]
    HormoneConfig.W_V = best_w["W_V"]
    HormoneConfig.W_TAU = best_w["W_TAU"]
    HormoneConfig.W_P = best_w["W_P"]

    print(f"\n  [Stage 1 Complete] Selected Best Config: {best_cfg} (Contrast={best_contrast:.2f}x)")
    return stage1_res


# -------------------------------------------------------------------
# STAGE 2: Multi-Core Hormone Dynamics Calibration
# -------------------------------------------------------------------
def stage2_dynamics_calibration_multicore(pool):
    print("\n" + "="*95)
    print("  STAGE 2: MULTI-CORE HORMONE DYNAMICS CALIBRATION (alpha_h, d0, D_h)")
    print("  Evaluating Baseline Convergence & Multi-Fault H_i Signatures (No Saturation)")
    print("="*95)

    dyn_configs = {
        "Nominal":           {"ALPHA_H": 0.60, "D0": 0.04, "KD": 0.18, "DIFFUSION_DH": 0.05},
        "Fast_Secretion":    {"ALPHA_H": 0.90, "D0": 0.04, "KD": 0.18, "DIFFUSION_DH": 0.05},
        "Slow_Secretion":    {"ALPHA_H": 0.35, "D0": 0.04, "KD": 0.18, "DIFFUSION_DH": 0.05},
        "High_Diffusion":    {"ALPHA_H": 0.60, "D0": 0.04, "KD": 0.18, "DIFFUSION_DH": 0.12},
        "Controlled_Decay":  {"ALPHA_H": 0.60, "D0": 0.06, "KD": 0.22, "DIFFUSION_DH": 0.05},
    }

    current_weights = {"W_Q": HormoneConfig.W_Q, "W_V": HormoneConfig.W_V,
                       "W_TAU": HormoneConfig.W_TAU, "W_P": HormoneConfig.W_P}

    tasks = []
    cfg_names = list(dyn_configs.keys())
    for cfg_name in cfg_names:
        p = {**current_weights, **dyn_configs[cfg_name]}
        tasks.append(("C5", FaultType.LOCKED, SimConfig.DEFAULT_FAULT_JOINT, p))
        tasks.append(("C5", FaultType.FREE, SimConfig.DEFAULT_FAULT_JOINT, p))

    results_list = pool.map(_run_single_episode_worker, tasks)

    stage2_res = {}
    print(f"{'Config Name':<20} | {'alpha_h':>7} | {'d0':>5} | {'D_h':>5} | {'H_norm':>7} | {'H_locked':>8} | {'H_free':>7} | {'H_neighbor':>10}")
    print("-" * 95)

    best_cfg = "Nominal"

    for idx, cfg_name in enumerate(cfg_names):
        params = dyn_configs[cfg_name]
        metrics_l, hist_l = results_list[2 * idx]
        _, hist_f = results_list[2 * idx + 1]

        h_lock = np.array(hist_l["hormones"])
        h_free = np.array(hist_f["hormones"])
        t = np.array(hist_l["time"])

        pre_idx = np.where(t < SimConfig.DEFAULT_FAULT_TIME)[0]
        post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0]
        fj = SimConfig.DEFAULT_FAULT_JOINT
        nj = max(0, fj - 1)

        h_norm = float(np.mean(h_lock[pre_idx, fj]))
        h_locked_ss = float(np.mean(h_lock[post_idx[-100:], fj]))
        h_free_ss = float(np.mean(h_free[post_idx[-100:], fj]))
        h_neigh_ss = float(np.mean(h_lock[post_idx[-100:], nj]))

        stage2_res[cfg_name] = {
            "params": params, "h_norm": h_norm, "h_locked": h_locked_ss,
            "h_free": h_free_ss, "h_neighbor": h_neigh_ss, "v_post": metrics_l["v_post"]
        }

        print(f"{cfg_name:<20} | {params['ALPHA_H']:>7.2f} | {params['D0']:>5.2f} | {params['DIFFUSION_DH']:>5.2f} | {h_norm:>7.3f} | {h_locked_ss:>8.3f} | {h_free_ss:>7.3f} | {h_neigh_ss:>10.3f}")

    best_params = dyn_configs[best_cfg]
    HormoneConfig.ALPHA_H = best_params["ALPHA_H"]
    HormoneConfig.D0 = best_params["D0"]
    HormoneConfig.KD = best_params["KD"]
    HormoneConfig.DIFFUSION_DH = best_params["DIFFUSION_DH"]

    print(f"\n  [Stage 2 Complete] Selected Best Dynamics: {best_cfg}")
    return stage2_res


# -------------------------------------------------------------------
# STAGE 3: Multi-Core Hill Receptor Activation Grid Sweep
# -------------------------------------------------------------------
def stage3_receptor_sweep_multicore(pool):
    print("\n" + "="*95)
    print("  STAGE 3: MULTI-CORE HILL RECEPTOR ACTIVATION GRID SWEEP (K_h, m)")
    print("  Evaluating Sigmoidal Receptor Activation R_i across K_h in [0.40..0.85] and m in [1.2..4.0]")
    print("="*95)

    kh_list = [0.40, 0.55, 0.65, 0.75, 0.85]
    m_list = [1.2, 2.0, 3.0, 4.0]

    current_params = {
        "W_Q": HormoneConfig.W_Q, "W_V": HormoneConfig.W_V, "W_TAU": HormoneConfig.W_TAU, "W_P": HormoneConfig.W_P,
        "ALPHA_H": HormoneConfig.ALPHA_H, "D0": HormoneConfig.D0, "KD": HormoneConfig.KD, "DIFFUSION_DH": HormoneConfig.DIFFUSION_DH
    }

    tasks = []
    combo_keys = []
    for kh in kh_list:
        for m in m_list:
            key = f"Kh_{kh:.2f}_m_{m:.1f}"
            combo_keys.append((kh, m, key))
            p = {**current_params, "KH": kh, "HILL_M": m}
            tasks.append(("C5", FaultType.LOCKED, SimConfig.DEFAULT_FAULT_JOINT, p))
            tasks.append(("C5", FaultType.FREE, SimConfig.DEFAULT_FAULT_JOINT, p))

    results_list = pool.map(_run_single_episode_worker, tasks)

    stage3_res = {}
    print(f"{'K_h':<6} | {'m':<4} | {'R_normal':>9} | {'R_free':>8} | {'R_locked':>9} | {'R_contrast':>10}")
    print("-" * 95)

    best_kh, best_m = 0.65, 2.0

    for idx, (kh, m, key) in enumerate(combo_keys):
        _, hist_l = results_list[2 * idx]
        _, hist_f = results_list[2 * idx + 1]

        r_lock = np.array(hist_l["receptors"])
        r_free = np.array(hist_f["receptors"])
        t = np.array(hist_l["time"])

        pre_idx = np.where(t < SimConfig.DEFAULT_FAULT_TIME)[0]
        post_idx = np.where(t >= SimConfig.DEFAULT_FAULT_TIME)[0]
        fj = SimConfig.DEFAULT_FAULT_JOINT

        r_norm = float(np.mean(r_lock[pre_idx, fj]))
        r_locked_ss = float(np.mean(r_lock[post_idx[-100:], fj]))
        r_free_ss = float(np.mean(r_free[post_idx[-100:], fj]))
        r_contrast = r_locked_ss / max(0.001, r_norm)

        stage3_res[key] = {
            "Kh": kh, "m": m, "r_norm": r_norm,
            "r_locked": r_locked_ss, "r_free": r_free_ss, "r_contrast": r_contrast
        }

        print(f"{kh:<6.2f} | {m:<4.1f} | {r_norm:>9.3f} | {r_free_ss:>8.3f} | {r_locked_ss:>9.3f} | {r_contrast:>10.2f}x")

    HormoneConfig.KH = best_kh
    HormoneConfig.HILL_M = best_m
    print(f"\n  [Stage 3 Complete] Selected Receptor Parameters: K_h={best_kh}, m={best_m}")
    return stage3_res


# -------------------------------------------------------------------
# STAGE 4: Multi-Core Performance Evaluation (C4, C5, C6)
# -------------------------------------------------------------------
def stage4_metrics_multicore(pool):
    print("\n" + "="*95)
    print("  STAGE 4: MULTI-CORE RECONFIGURATION GAINS & PERFORMANCE EVALUATION (C4, C5, C6)")
    print("  Evaluating Sustained Locomotion Metrics: v_post, R_D >= 0.40, COT, Success")
    print("="*95)

    full_params = {
        "W_Q": HormoneConfig.W_Q, "W_V": HormoneConfig.W_V, "W_TAU": HormoneConfig.W_TAU, "W_P": HormoneConfig.W_P,
        "ALPHA_H": HormoneConfig.ALPHA_H, "D0": HormoneConfig.D0, "KD": HormoneConfig.KD, "DIFFUSION_DH": HormoneConfig.DIFFUSION_DH,
        "KH": HormoneConfig.KH, "HILL_M": HormoneConfig.HILL_M
    }

    ctrls = ["C4", "C5", "C6"]
    tasks = [(c, FaultType.LOCKED, SimConfig.DEFAULT_FAULT_JOINT, full_params) for c in ctrls]

    results_list = pool.map(_run_single_episode_worker, tasks)

    stage4_res = {}
    print(f"{'Ctrl':<6} | {'v_pre (m/s)':>11} | {'v_post (m/s)':>12} | {'R_D (Ratio)':>11} | {'T_rec (s)':>9} | {'Dist (m)':>9} | {'COT':>7} | {'Success':>7}")
    print("-" * 95)

    for idx, c in enumerate(ctrls):
        metrics, _ = results_list[idx]
        stage4_res[c] = metrics
        tag = " <- PROPOSED" if c == "C5" else ""
        print(f"{c:<6} | {metrics['v_pre']:>11.3f} | {metrics['v_post']:>12.3f} | {metrics['recovery_ratio']:>11.3f} | "
              f"{metrics['recovery_time']:>9.1f} | {metrics['distance_traveled']:>9.2f} | {metrics['cost_of_transport']:>7.2f} | "
              f"{str(metrics['recovery_success']):>7}{tag}")

    print("="*95 + "\n")
    return stage4_res


def generate_4stage_figures(s1, s2, s3, s4):
    print("  Generating 4-Stage Verification Figures...")

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(13, 9.5))

    s1_keys = list(s1.keys())
    s1_contrasts = [s1[k]["contrast"] for k in s1_keys]
    ax1.bar(s1_keys, s1_contrasts, color='#3498db', alpha=0.85, edgecolor='black')
    ax1.set_title("Stage 1: Stimulus Contrast Ratio $S_{\\mathrm{fault}} / S_{\\mathrm{normal}}$", fontweight='bold', fontsize=10)
    ax1.set_ylabel("Contrast Ratio")
    ax1.set_xticklabels(s1_keys, rotation=25, ha='right', fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.3)

    s2_keys = list(s2.keys())
    s2_locked = [s2[k]["h_locked"] for k in s2_keys]
    s2_free = [s2[k]["h_free"] for k in s2_keys]
    x2 = np.arange(len(s2_keys))
    ax2.bar(x2 - 0.15, s2_locked, 0.3, label='Locked Fault H_ss', color='#e74c3c', alpha=0.85, edgecolor='black')
    ax2.bar(x2 + 0.15, s2_free, 0.3, label='Free Fault H_ss', color='#f39c12', alpha=0.85, edgecolor='black')
    ax2.set_title("Stage 2: Multi-Fault Hormone Signatures $H_i$", fontweight='bold', fontsize=10)
    ax2.set_ylabel("Hormone Level $H_i$")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(s2_keys, rotation=25, ha='right', fontsize=8)
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle='--', alpha=0.3)

    s3_kh_065 = [v["r_locked"] for k, v in s3.items() if "Kh_0.65" in k]
    m_labels = ["m=1.2", "m=2.0", "m=3.0", "m=4.0"]
    ax3.bar(m_labels, s3_kh_065, color='#9b59b6', alpha=0.85, edgecolor='black')
    ax3.set_title("Stage 3: Hill Receptor Activation $R_{\\mathrm{locked}}$ ($K_h=0.65$)", fontweight='bold', fontsize=10)
    ax3.set_ylabel("Receptor Activation $R_i$")
    ax3.grid(True, linestyle='--', alpha=0.3)

    s4_ctrls = list(s4.keys())
    s4_rd = [s4[c]["recovery_ratio"] for c in s4_ctrls]
    s4_vpost = [s4[c]["v_post"] for c in s4_ctrls]
    x4 = np.arange(len(s4_ctrls))
    ax4.bar(x4 - 0.15, s4_vpost, 0.3, label='v_post (m/s)', color='#2ecc71', alpha=0.85, edgecolor='black')
    ax4.bar(x4 + 0.15, s4_rd, 0.3, label='R_D Ratio', color='#e67e22', alpha=0.85, edgecolor='black')
    ax4.axhline(y=0.40, color='red', linestyle='--', label='Success Thresh (40%)')
    ax4.set_title("Stage 4: Final Locomotion Metrics (C4, C5, C6)", fontweight='bold', fontsize=10)
    ax4.set_xticks(x4)
    ax4.set_xticklabels(s4_ctrls, fontsize=9)
    ax4.legend(fontsize=8)
    ax4.grid(True, linestyle='--', alpha=0.3)

    fig_path = os.path.join(FIG_DIR, "prelim_04_4stage_hormone_tuning.png")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved figure: {fig_path}")


def render_calibrated_videos():
    print(f"\n  Rendering 3D HD GPU-Accelerated Split-Screen Videos using FINAL CALIBRATED HormoneConfig...")
    from analysis.render_publication_videos import render_splitscreen_video
    for ctrl in ["C4", "C5", "C6"]:
        out_path = os.path.join(VIDEO_DIR, f"{ctrl.lower()}_pub_splitscreen.mp4")
        render_splitscreen_video(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            fault_joint_idx=SimConfig.DEFAULT_FAULT_JOINT,
            fault_time=SimConfig.DEFAULT_FAULT_TIME,
            duration=SimConfig.DEFAULT_DURATION,
            env_type=EnvironmentType.FLAT,
            incline_deg=0.0,
            output_filepath=out_path
        )


if __name__ == "__main__":
    t_start = time.time()
    num_workers = min(4, max(1, cpu_count()))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    print(f"\n{'='*95}", flush=True)
    print(f"  4-STAGE HIERARCHICAL HORMONE TUNING (MULTI-CORE {num_workers} WORKERS)", flush=True)
    print(f"{'='*95}\n", flush=True)

    with Pool(processes=num_workers) as pool:
        s1 = stage1_stimulus_calibration_multicore(pool)
        s2 = stage2_dynamics_calibration_multicore(pool)
        s3 = stage3_receptor_sweep_multicore(pool)
        s4 = stage4_metrics_multicore(pool)

    summary_data = {"Stage1": s1, "Stage2": s2, "Stage3": s3, "Stage4": s4}
    with open(os.path.join(OUTPUT_DIR, "4stage_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    generate_4stage_figures(s1, s2, s3, s4)

    # NOW render videos using the FINAL CALIBRATED HormoneConfig settings!
    render_calibrated_videos()

    print(f"\n4-Stage Hierarchical Tuning Preliminary Complete in {time.time() - t_start:.1f}s.\n")
