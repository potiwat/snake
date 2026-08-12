"""
Hormone Parameter Sensitivity Preliminary Test & Video Renderer (C4, C5, C6).
Evaluates hormone parameter variations (Secretion alpha_h, Diffusion D_h, Hill threshold K_h, Neighbor gain G_N)
and renders 3D HD Split-Screen Demonstration Videos with explicit Y-axis tick markers for hormone levels.
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

from config import SimConfig, RobotConfig, HormoneConfig, CPGConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from controllers.baselines import (
    OracleFaultAwareCPGController,
    AHMNobypassCPGController
)
from analysis.metrics import LocomotionMetrics
from analysis.render_publication_videos import make_controller, render_splitscreen_video, render_all_videos_parallel

OUTPUT_DIR = "results/publication/data/prelim_hormone"
FIG_DIR = "results/publication/prelim_figures"
VIDEO_DIR = "results/publication/videos"

# Representative Hormone Configurations to Sweep
HORMONE_CONFIGS = {
    "Nominal": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.05, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.95},
    "Low_Secretion": {"ALPHA_H": 0.30, "DIFFUSION_DH": 0.05, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.95},
    "High_Secretion": {"ALPHA_H": 0.90, "DIFFUSION_DH": 0.05, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.95},
    "Low_Diffusion": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.01, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.95},
    "High_Diffusion": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.10, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.95},
    "Low_Receptor_Kh": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.05, "KH": 0.40, "GAIN_NEIGHBOR_GN": 0.95},
    "High_Receptor_Kh": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.05, "KH": 0.90, "GAIN_NEIGHBOR_GN": 0.95},
    "Low_Neighbor_Gain": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.05, "KH": 0.65, "GAIN_NEIGHBOR_GN": 0.50},
    "High_Neighbor_Gain": {"ALPHA_H": 0.60, "DIFFUSION_DH": 0.05, "KH": 0.65, "GAIN_NEIGHBOR_GN": 1.40},
}

CTRLS = ["C4", "C5", "C6"]


def run_hormone_prelim():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    print("\n" + "="*95)
    print("  HORMONE PARAMETER PRELIMINARY TEST (C4, C5, C6)")
    print(f"  Fault: Locked Joint {SimConfig.DEFAULT_FAULT_JOINT+1} | "
          f"Fault Time: {SimConfig.DEFAULT_FAULT_TIME}s | Duration: {SimConfig.DEFAULT_DURATION}s")
    print("="*95 + "\n")

    results = {}

    for name, params in HORMONE_CONFIGS.items():
        # Update HormoneConfig parameters dynamically
        HormoneConfig.ALPHA_H = params["ALPHA_H"]
        HormoneConfig.DIFFUSION_DH = params["DIFFUSION_DH"]
        HormoneConfig.KH = params["KH"]
        HormoneConfig.GAIN_NEIGHBOR_GN = params["GAIN_NEIGHBOR_GN"]

        results[name] = {}
        print(f"  -- [Config: {name:<18}] alpha_h={params['ALPHA_H']:.2f}, Dh={params['DIFFUSION_DH']:.2f}, Kh={params['KH']:.2f}, GN={params['GAIN_NEIGHBOR_GN']:.2f} --")

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
                    if ctrl == "C4":
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

            metrics = LocomotionMetrics.calculate_metrics(
                history, fault_time=SimConfig.DEFAULT_FAULT_TIME,
                sim_duration=SimConfig.DEFAULT_DURATION, total_mass=RobotConfig.TOTAL_MASS
            )
            elapsed = time.time() - t0
            results[name][ctrl] = metrics

            print(f"      {ctrl:<4} | v_post={metrics['v_post']:.3f} m/s | R_D={metrics['recovery_ratio']:.3f} | Dist={metrics['distance_traveled']:.2f}m | COT={metrics['cost_of_transport']:.2f} | Success={metrics['recovery_success']}")

    # Restore nominal HormoneConfig parameters
    HormoneConfig.ALPHA_H = 0.60
    HormoneConfig.DIFFUSION_DH = 0.05
    HormoneConfig.KH = 0.65
    HormoneConfig.GAIN_NEIGHBOR_GN = 0.95

    # Save JSON
    out_json = os.path.join(OUTPUT_DIR, "hormone_prelim_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


def render_c4_c5_c6_videos():
    print("\n  Rendering 3D HD Split-Screen Videos for C4, C5, C6 (with Explicit Y-axis Ticks on Hormone Plot)...")
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


def generate_hormone_prelim_plots(results):
    print("\n  Generating Hormone Sensitivity Verification Plot...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    cfg_names = list(results.keys())
    x = np.arange(len(cfg_names))
    width = 0.25

    c4_v = [results[c]["C4"]["v_post"] for c in cfg_names]
    c5_v = [results[c]["C5"]["v_post"] for c in cfg_names]
    c6_v = [results[c]["C6"]["v_post"] for c in cfg_names]

    c4_rd = [results[c]["C4"]["recovery_ratio"] for c in cfg_names]
    c5_rd = [results[c]["C5"]["recovery_ratio"] for c in cfg_names]
    c6_rd = [results[c]["C6"]["recovery_ratio"] for c in cfg_names]

    ax1.bar(x - width, c4_v, width, label='C4 Oracle', color='#9b59b6', alpha=0.85, edgecolor='black')
    ax1.bar(x, c5_v, width, label='C5 Proposed AHM-CPG', color='#27ae60', alpha=0.85, edgecolor='black')
    ax1.bar(x + width, c6_v, width, label='C6 AHM w/o Bypass', color='#2980b9', alpha=0.85, edgecolor='black')

    ax1.set_xticks(x)
    ax1.set_xticklabels(cfg_names, rotation=35, ha='right', fontsize=9)
    ax1.set_ylabel('Sustained Post-Fault Speed $v_{\\mathrm{post}}$ (m/s)', fontsize=10)
    ax1.set_title('Hormone Sensitivity: Post-Fault Speed (C4 vs C5 vs C6)', fontweight='bold', fontsize=11)
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.legend(fontsize=8)

    ax2.bar(x - width, c4_rd, width, label='C4 Oracle', color='#9b59b6', alpha=0.85, edgecolor='black')
    ax2.bar(x, c5_rd, width, label='C5 Proposed AHM-CPG', color='#27ae60', alpha=0.85, edgecolor='black')
    ax2.bar(x + width, c6_rd, width, label='C6 AHM w/o Bypass', color='#2980b9', alpha=0.85, edgecolor='black')
    ax2.axhline(y=0.40, color='red', linestyle='--', label='Success Threshold (40%)')

    ax2.set_xticks(x)
    ax2.set_xticklabels(cfg_names, rotation=35, ha='right', fontsize=9)
    ax2.set_ylabel('Spatial Recovery Ratio $R_D$', fontsize=10)
    ax2.set_title('Hormone Sensitivity: Recovery Ratio $R_D$', fontweight='bold', fontsize=11)
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend(fontsize=8)

    fig_path = os.path.join(FIG_DIR, "prelim_03_hormone_sensitivity.png")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved figure: {fig_path}")


def print_summary_table(results):
    print("\n" + "="*95)
    print("  HORMONE PARAMETER SENSITIVITY SUMMARY TABLE (C4, C5, C6)")
    print("="*95)
    header = f"{'Hormone Config':<20} | {'C4 v_post':>9} | {'C4 R_D':>7} | {'C5 v_post':>9} | {'C5 R_D':>7} | {'C6 v_post':>9} | {'C6 R_D':>7} | {'C5 Success':>10}"
    print(header)
    print("-" * 95)

    for cfg_name, res in results.items():
        c4 = res["C4"]
        c5 = res["C5"]
        c6 = res["C6"]
        print(f"{cfg_name:<20} | {c4['v_post']:>9.3f} | {c4['recovery_ratio']:>7.3f} | "
              f"{c5['v_post']:>9.3f} | {c5['recovery_ratio']:>7.3f} | "
              f"{c6['v_post']:>9.3f} | {c6['recovery_ratio']:>7.3f} | "
              f"{str(c5['recovery_success']):>10}")

    print("="*95 + "\n")


if __name__ == "__main__":
    t_start = time.time()
    results = run_hormone_prelim()
    print_summary_table(results)
    generate_hormone_prelim_plots(results)
    render_c4_c5_c6_videos()
    print(f"Hormone preliminary test complete in {time.time() - t_start:.1f}s.\n")
