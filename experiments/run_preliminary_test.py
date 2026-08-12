"""
Preliminary Verification Runner (C1-C6 Single Episode Evaluation, Plots & Video Rendering).
All simulation settings strictly reference config.py (SimConfig, RobotConfig, CPGConfig).
Outputs:
  - Numerical metrics summary table (printed & saved as Markdown/JSON)
  - Preliminary comparison figures in results/publication/prelim_figures/
  - HD Split-Screen Demonstration Videos in results/publication/videos/
"""

import sys
import os
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import SimConfig, RobotConfig, CPGConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from controllers.baselines import (
    FixedCPGController,
    ErrorAdaptiveCPGController,
    ShapeBasedRecoveryController,
    OracleFaultAwareCPGController,
    AHMNobypassCPGController
)
from analysis.metrics import LocomotionMetrics
from analysis.render_publication_videos import make_controller, render_splitscreen_video

CTRLS = ["C1", "C2", "C3", "C4", "C5", "C6"]
CTRL_NAMES = {
    "C1": "C1: Fixed CPG",
    "C2": "C2: Error-Adaptive",
    "C3": "C3: Shape Recovery",
    "C4": "C4: Oracle Fault-Aware",
    "C5": "C5: Proposed AHM-CPG",
    "C6": "C6: AHM w/o Bypass"
}
COLORS = {
    'C1': '#e74c3c', 'C2': '#e67e22', 'C3': '#f39c12',
    'C4': '#9b59b6', 'C5': '#27ae60', 'C6': '#2980b9'
}

OUTPUT_DIR = "results/publication/data/prelim"
FIG_DIR = "results/publication/prelim_figures"
VIDEO_DIR = "results/publication/videos"


def run_prelim_episodes():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    print("\n" + "="*80)
    print("  PRELIMINARY TEST: RUNNING 6 REPRESENTATIVE EPISODES (C1-C6)")
    print(f"  Fault: Locked Joint {SimConfig.DEFAULT_FAULT_JOINT+1} | "
          f"Fault Time: {SimConfig.DEFAULT_FAULT_TIME}s | "
          f"Duration: {SimConfig.DEFAULT_DURATION}s")
    print("="*80 + "\n")

    prelim_results = {}
    histories = {}

    for ctrl in CTRLS:
        t0 = time.time()
        env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
        robot = SnakeRobot(physics_client=env.physics_client)

        np.random.seed(42)
        controller = make_controller(ctrl, robot.num_joints)

        history = {
            "time": [], "base_position": [], "base_velocity": [],
            "joint_angles": [], "target_angles": [], "joint_torques": [],
            "joint_velocities": [], "hormones": [], "receptors": []
        }

        sim_steps = int(SimConfig.DEFAULT_DURATION / SimConfig.TIMESTEP)
        ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)

        target_angles = np.zeros(robot.num_joints)
        fault_injected = False

        for step in range(sim_steps):
            current_time = step * SimConfig.TIMESTEP

            if current_time >= SimConfig.DEFAULT_FAULT_TIME and not fault_injected:
                robot.inject_fault(joint_idx=SimConfig.DEFAULT_FAULT_JOINT, fault_type=FaultType.LOCKED)
                fault_injected = True

            sensory = robot.get_sensory_feedback()

            if step % ctrl_substeps == 0:
                if ctrl in ["C4", "oracle"]:
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

            applied_torques = robot.apply_joint_commands(target_angles)
            if step % ctrl_substeps == 0:
                history["joint_torques"].append(
                    applied_torques if isinstance(applied_torques, list) else list(applied_torques)
                )

            env.step()

        env.close()

        # Compute metrics strictly using RobotConfig.TOTAL_MASS and SimConfig settings
        metrics = LocomotionMetrics.calculate_metrics(
            history, fault_time=SimConfig.DEFAULT_FAULT_TIME,
            sim_duration=SimConfig.DEFAULT_DURATION, total_mass=RobotConfig.TOTAL_MASS
        )

        elapsed = time.time() - t0
        prelim_results[ctrl] = metrics
        histories[ctrl] = history

        print(f"  [{ctrl}] {CTRL_NAMES[ctrl]:<30} | "
              f"v_spatial_post={metrics['v_post']:.3f} m/s | "
              f"R_D={metrics['recovery_ratio']:.3f} | "
              f"T_rec={metrics['recovery_time']:.1f}s | "
              f"Dist={metrics['distance_traveled']:.2f}m | "
              f"COT={metrics['cost_of_transport']:.2f} | "
              f"Elapsed={elapsed:.1f}s")

    # Save prelim JSON
    prelim_json_path = os.path.join(OUTPUT_DIR, "prelim_results.json")
    with open(prelim_json_path, "w", encoding="utf-8") as f:
        json.dump(prelim_results, f, indent=2)

    return prelim_results, histories


def render_prelim_videos():
    from analysis.render_publication_videos import render_all_videos_parallel
    render_all_videos_parallel()


def generate_prelim_plots(histories, prelim_results):
    print("\n  Generating Preliminary Verification Plots...")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    fault_time = SimConfig.DEFAULT_FAULT_TIME

    for ctrl in CTRLS:
        hist = histories[ctrl]
        t = np.array(hist["time"])
        poss = np.array(hist["base_position"])
        vels = np.array(hist["base_velocity"])

        dist = np.sqrt((poss[:, 0] - poss[0, 0])**2 + (poss[:, 1] - poss[0, 1])**2)
        v_2d = np.sqrt(vels[:, 0]**2 + vels[:, 1]**2)

        w = 30
        v_smooth = np.convolve(v_2d, np.ones(w)/w, mode='same')

        lw = 2.5 if ctrl == "C5" else 1.5
        alpha = 1.0 if ctrl == "C5" else 0.7

        ax1.plot(t, dist, label=CTRL_NAMES[ctrl], color=COLORS[ctrl], linewidth=lw, alpha=alpha)
        ax2.plot(t, v_smooth, label=CTRL_NAMES[ctrl], color=COLORS[ctrl], linewidth=lw, alpha=alpha)

    ax1.axvline(x=fault_time, color='black', linestyle='--', label=f'Fault Injection (J{SimConfig.DEFAULT_FAULT_JOINT+1})')
    ax2.axvline(x=fault_time, color='black', linestyle='--')

    ax1.set_ylabel('Planar Displacement (m)', fontsize=11)
    ax1.set_title('Preliminary Trajectory Evaluation: Spatial Displacement & 2D Speed', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2, fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.4)

    ax2.set_xlabel('Time (s)', fontsize=11)
    ax2.set_ylabel('2D Planar Speed (m/s)', fontsize=11)
    ax2.set_xlim(0, SimConfig.DEFAULT_DURATION)
    ax2.grid(True, linestyle='--', alpha=0.4)

    fig1_path = os.path.join(FIG_DIR, "prelim_01_trajectory_and_speed.png")
    plt.tight_layout()
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved figure: {fig1_path}")

    # Plot 2: Bar Comparison of R_D, Distance, and COT
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12, 4))
    x_indices = np.arange(len(CTRLS))

    r_d_vals = [prelim_results[c]["recovery_ratio"] for c in CTRLS]
    dist_vals = [prelim_results[c]["distance_traveled"] for c in CTRLS]
    cot_vals = [prelim_results[c]["cost_of_transport"] for c in CTRLS]
    bar_colors = [COLORS[c] for c in CTRLS]

    ax1.bar(x_indices, r_d_vals, color=bar_colors, alpha=0.85, edgecolor='black')
    ax1.axhline(y=1.0, color='red', linestyle='--', label='Baseline 1.0 (100%)')
    ax1.set_xticks(x_indices)
    ax1.set_xticklabels(CTRLS)
    ax1.set_ylabel('Spatial Recovery Ratio $R_D$')
    ax1.set_title('Spatial Displacement Ratio $R_D$', fontweight='bold')
    ax1.legend(fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.3)

    ax2.bar(x_indices, dist_vals, color=bar_colors, alpha=0.85, edgecolor='black')
    ax2.set_xticks(x_indices)
    ax2.set_xticklabels(CTRLS)
    ax2.set_ylabel('Forward Distance (m)')
    ax2.set_title('Distance Traveled $D_{\\mathrm{forward}}$', fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.3)

    ax3.bar(x_indices, cot_vals, color=bar_colors, alpha=0.85, edgecolor='black')
    ax3.set_xticks(x_indices)
    ax3.set_xticklabels(CTRLS)
    ax3.set_ylabel('Cost of Transport (COT)')
    ax3.set_title('Energy Efficiency COT (Lower=Better)', fontweight='bold')
    ax3.grid(True, linestyle='--', alpha=0.3)

    fig2_path = os.path.join(FIG_DIR, "prelim_02_metrics_bars.png")
    plt.tight_layout()
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved figure: {fig2_path}")


def print_summary_table(prelim_results):
    print("\n" + "="*95)
    print("  PRELIMINARY TEST RESULTS SUMMARY (CONFIG-CONSISTENT SPATIAL METRICS)")
    print("="*95)
    header = f"{'Ctrl':<6} | {'v_pre (m/s)':>11} | {'v_post (m/s)':>12} | {'R_D (Ratio)':>11} | {'T_rec (s)':>9} | {'Dist (m)':>9} | {'COT':>7} | {'Success':>7}"
    print(header)
    print("-" * 95)

    for c in CTRLS:
        res = prelim_results[c]
        tag = " <- PROPOSED" if c == "C5" else ""
        print(f"{c:<6} | {res['v_pre']:>11.3f} | {res['v_post']:>12.3f} | {res['recovery_ratio']:>11.3f} | "
              f"{res['recovery_time']:>9.1f} | {res['distance_traveled']:>9.2f} | {res['cost_of_transport']:>7.2f} | "
              f"{str(res['recovery_success']):>7}{tag}")

    print("="*95 + "\n")


if __name__ == "__main__":
    t_start = time.time()
    prelim_results, histories = run_prelim_episodes()
    print_summary_table(prelim_results)
    generate_prelim_plots(histories, prelim_results)
    render_prelim_videos()
    print(f"Preliminary test complete with video rendering in {time.time() - t_start:.1f}s.\n")
