"""
Standalone Stage 4: Reconfiguration Gains Optimization, Locomotion Metrics & Video Rendering.
Reads fully-calibrated parameters directly from config.py (updated in Stages 1, 2, 3).
Evaluates locomotion performance across C4 (Oracle), C5 (Proposed AHM-CPG), and C6 (AHM w/o Bypass):
  - Sustained Post-Fault Speed (v_post_sustained)
  - Scale-Invariant Sustained Recovery Ratio (R_D = v_post / max(0.25, v_pre))
  - Recovery Success Criterion (R_D >= 0.40)
  - Mechanical Cost of Transport (COT)

Combined Execution Requirement:
  - Generates 3-subpanel comparison figures AND renders 3D HD GPU split-screen videos (C4, C5, C6) TOGETHER in the SAME run!

Outputs:
  - Formatted Stage 4 Performance Table
  - Diagnostic Figure: results/publication/prelim_figures/stage4_metrics_diagnostics.png
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
from analysis.render_publication_videos import make_controller, render_all_videos_parallel

OUTPUT_DIR = "results/publication/data/prelim_4stage"
FIG_DIR = "results/publication/prelim_figures"
VIDEO_DIR = "results/publication/videos"


def _stage4_worker(args):
    ctrl_type, fault_type, fault_joint = args

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
            history["hormones"].append(ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist())
            history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist())
            history["stimuli"].append(ctrl_info.get("stimuli", np.zeros(robot.num_joints)).tolist())

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(applied_torques)

        env.step()

    env.close()

    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=SimConfig.DEFAULT_FAULT_TIME,
        sim_duration=SimConfig.DEFAULT_DURATION, total_mass=RobotConfig.TOTAL_MASS
    )
    return ctrl_type, metrics, history


def run_stage4_evaluation_and_rendering():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    print("\n" + "="*95)
    print("  STANDALONE STAGE 4: LOCOMOTION METRICS & COMBINED HD VIDEO RENDERING")
    print(f"  Using Calibrated Config: W_Q={HormoneConfig.W_Q}, ALPHA_H={HormoneConfig.ALPHA_H}, KH={HormoneConfig.KH}, HILL_M={HormoneConfig.HILL_M}")
    print("="*95 + "\n")

    ctrls = ["C4", "C5", "C6"]
    tasks = [(c, FaultType.LOCKED, SimConfig.DEFAULT_FAULT_JOINT) for c in ctrls]

    num_workers = min(3, len(tasks))
    print(f"  Running C4, C5, C6 simulations in parallel ({num_workers} workers)...")
    pool = Pool(processes=num_workers)
    try:
        results_list = pool.map(_stage4_worker, tasks)
    finally:
        pool.terminate()
        pool.close()

    stage4_results = {}
    print("\n" + "-"*95)
    print(f"{'Ctrl':<6} | {'v_pre (m/s)':>11} | {'v_post (m/s)':>12} | {'R_D (Ratio)':>11} | {'T_rec (s)':>9} | {'Dist (m)':>9} | {'COT':>7} | {'Success':>7}")
    print("-" * 95)

    for ctrl_type, metrics, history in results_list:
        stage4_results[ctrl_type] = metrics
        tag = " <- PROPOSED" if ctrl_type == "C5" else ""
        print(f"{ctrl_type:<6} | {metrics['v_pre']:>11.3f} | {metrics['v_post']:>12.3f} | {metrics['recovery_ratio']:>11.3f} | "
              f"{metrics['recovery_time']:>9.1f} | {metrics['distance_traveled']:>9.2f} | {metrics['cost_of_transport']:>7.2f} | "
              f"{str(metrics['recovery_success']):>7}{tag}")

    print("-" * 95)

    # Save results JSON
    with open(os.path.join(OUTPUT_DIR, "stage4_results.json"), "w", encoding="utf-8") as f:
        json.dump(stage4_results, f, indent=2)

    # Generate Stage 4 Metrics Diagnostic Figure
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5))

    ctrl_names = list(stage4_results.keys())
    v_posts = [stage4_results[c]["v_post"] for c in ctrl_names]
    r_ds = [stage4_results[c]["recovery_ratio"] for c in ctrl_names]
    cots = [stage4_results[c]["cost_of_transport"] for c in ctrl_names]
    colors = ['#e74c3c', '#2ecc71', '#3498db']

    ax1.bar(ctrl_names, v_posts, color=colors, alpha=0.85, edgecolor='black')
    ax1.set_title("Sustained Post-Fault Speed $v_{\\mathrm{post}}$ (m/s)", fontweight='bold', fontsize=10)
    ax1.set_ylabel("Speed (m/s)")
    ax1.grid(True, linestyle='--', alpha=0.3)

    ax2.bar(ctrl_names, r_ds, color=colors, alpha=0.85, edgecolor='black')
    ax2.axhline(y=0.40, color='red', linestyle='--', label='Success Threshold (40%)')
    ax2.set_title("Sustained Recovery Ratio $R_D$", fontweight='bold', fontsize=10)
    ax2.set_ylabel("Ratio $R_D$")
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle='--', alpha=0.3)

    ax3.bar(ctrl_names, cots, color=colors, alpha=0.85, edgecolor='black')
    ax3.set_title("Mechanical Cost of Transport (COT)", fontweight='bold', fontsize=10)
    ax3.set_ylabel("COT (Dimensionless)")
    ax3.grid(True, linestyle='--', alpha=0.3)

    fig_path = os.path.join(FIG_DIR, "stage4_metrics_diagnostics.png")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"  [OK] Saved Stage 4 Diagnostic Figure: {fig_path}")

    # COMBINED REQUIREMENT: Render HD Videos TOGETHER in the SAME script execution!
    print("\n  [Combined Execution] Rendering 3D HD GPU-Accelerated Split-Screen Videos for C4, C5, C6...")
    render_all_videos_parallel()
    print("\nStage 4 Evaluation & Video Rendering Complete.\n")


if __name__ == "__main__":
    run_stage4_evaluation_and_rendering()
