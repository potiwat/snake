"""
Per-Joint Trajectories Plot Generator & Split-Screen Video Renderer.
Plots 8-joint target vs actual angles, hormone concentration, and receptor activation.
Also renders a synchronized split-screen video with live joint angle graphs alongside 3D simulation.
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import pybullet as p
import cv2

from config import RobotConfig, SimConfig
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

def plot_joint_trajectories(history, fault_time=10.0, fault_joint_idx=3, output_path="results/figures/joint_trajectories.png"):
    """Generate 8-panel publication plot for target vs actual joint angles and hormone levels."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    time = np.array(history["time"])
    q_act = np.array(history["joint_angles"])    # Shape: (T, 8)
    q_target = np.array(history["target_angles"])# Shape: (T, 8)
    hormones = np.array(history["hormones"])    # Shape: (T, 8)
    
    num_joints = q_act.shape[1]
    
    fig, axes = plt.subplots(num_joints, 1, figsize=(12, 14), sharex=True, dpi=300)
    
    for i in range(num_joints):
        ax = axes[i]
        is_failed = (i == fault_joint_idx)
        
        c_target = '#2980b9' if not is_failed else '#e74c3c'
        c_act = '#2ecc71' if not is_failed else '#c0392b'
        
        ax.plot(time, np.rad2deg(q_target[:, i]), label=f'Target $q_{i+1}^d$', color=c_target, linestyle='--', linewidth=1.5)
        ax.plot(time, np.rad2deg(q_act[:, i]), label=f'Actual $q_{i+1}$', color=c_act, linewidth=1.8)
        
        # Secondary Y axis for local hormone H_i
        ax_h = ax.twinx()
        ax_h.plot(time, hormones[:, i], color='#e67e22', linestyle=':', linewidth=1.5, label=f'Hormone $H_{i+1}$')
        ax_h.set_ylabel(f'$H_{i+1}$', color='#e67e22', fontweight='bold')
        ax_h.set_ylim(-0.1, 4.5)
        
        ax.axvline(x=fault_time, color='red', linestyle=':', linewidth=1.2)
        
        title = f'Joint {i+1}' + (' (LOCKED FAILURE)' if is_failed else '')
        ax.set_ylabel(f'Angle (deg)', fontweight='bold')
        ax.set_title(title, fontsize=10, fontweight='bold', loc='left', color='red' if is_failed else 'black')
        ax.set_ylim(-55, 55)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        if i == 0:
            lines_1, labels_1 = ax.get_legend_handles_labels()
            lines_2, labels_2 = ax_h.get_legend_handles_labels()
            ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=8)

    axes[-1].set_xlabel('Time (s)', fontweight='bold', fontsize=12)
    fig.suptitle('Individual Joint Trajectories & Local Hormone Response ($q_1 \\dots q_8$)', fontsize=14, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Joint trajectories plot saved to {output_path}")

def generate_splitscreen_video(
    controller_type="C1",
    fault_type=FaultType.LOCKED,
    fault_joint_idx=3,
    fault_time=10.0,
    duration=20.0,
    output_filepath="results/videos/c1_recovery_with_graphs.mp4"
):
    """Generate split-screen MP4 video: Left=3D PyBullet camera view, Right=Live Joint Trajectory Graphs."""
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    env = SimulationEnvironment(gui=False)
    robot = SnakeRobot(physics_client=env.physics_client)
    
    if controller_type in ["C5", "proposed"]:
        controller = AHMCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C1", "fixed"]:
        controller = FixedCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C2", "error_adaptive"]:
        controller = ErrorAdaptiveCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C3", "shape_recovery"]:
        controller = ShapeBasedRecoveryController(num_joints=robot.num_joints)
    elif controller_type in ["C6", "ahm_nobypass"]:
        controller = AHMNobypassCPGController(num_joints=robot.num_joints)
    else:
        controller = FixedCPGController(num_joints=robot.num_joints)
    
    sim_steps = int(duration / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    frame_skip = 6 # Record 1 frame every 6 sim steps (~33.3 fps)
    
    width, height = 1280, 480
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(output_filepath, fourcc, 30.0, (width, height))
    
    time_buf = []
    q_act_buf = []
    q_target_buf = []
    hormone_buf = []
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.4, 4.8), dpi=100)
    
    line_q_failed, = ax1.plot([], [], label=f'Joint {fault_joint_idx+1} (FAILED)', color='red', linewidth=2.0)
    line_q_prev, = ax1.plot([], [], label=f'Joint {fault_joint_idx}', color='blue', linewidth=1.2)
    line_q_next, = ax1.plot([], [], label=f'Joint {fault_joint_idx+2}', color='green', linewidth=1.2)
    ax1.axvline(x=fault_time, color='red', linestyle='--', label='Fault Onset')
    ax1.set_ylabel('Angle (deg)', fontweight='bold', fontsize=9)
    ax1.set_title(f'Real-Time Joint Oscillations ({controller_type})', fontweight='bold', fontsize=10)
    ax1.set_xlim(0, duration)
    ax1.set_ylim(-55, 55)
    ax1.legend(loc='upper right', fontsize=7)
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    line_h_failed, = ax2.plot([], [], label=f'Hormone $H_{fault_joint_idx+1}$ (Failed)', color='darkorange', linewidth=2.0)
    line_h_prev, = ax2.plot([], [], label=f'Hormone $H_{fault_joint_idx}$', color='purple', linewidth=1.2)
    ax2.axvline(x=fault_time, color='red', linestyle='--')
    ax2.set_xlabel('Time (s)', fontweight='bold', fontsize=9)
    ax2.set_ylabel('Local Hormone $H_i$', fontweight='bold', fontsize=9)
    ax2.set_title('Local Hormone Build-Up & Diffusion', fontweight='bold', fontsize=10)
    ax2.set_xlim(0, duration)
    ax2.set_ylim(-0.1, 4.0)
    ax2.legend(loc='upper left', fontsize=7)
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    
    target_angles = np.zeros(robot.num_joints)
    fault_injected = False
    
    print(f"Generating split-screen video for {controller_type}: {output_filepath} ...", flush=True)
    
    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        
        if not fault_injected and current_time >= fault_time and fault_type != FaultType.NONE:
            robot.inject_fault(joint_idx=fault_joint_idx, fault_type=fault_type)
            fault_injected = True
            
        sensory = robot.get_sensory_feedback()
        if step % ctrl_substeps == 0:
            target_angles, ctrl_info = controller.step(sensory)
            time_buf.append(current_time)
            q_act_buf.append(sensory["joint_angles"])
            q_target_buf.append(target_angles)
            hormone_buf.append(ctrl_info.get("hormones", np.zeros(8)))

        robot.apply_joint_commands(target_angles)
        env.step()
        
        if step % frame_skip == 0 and len(time_buf) > 2:
            target_pos = sensory["base_position"]
            v_mat = p.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=target_pos, distance=2.2, yaw=45, pitch=-35, roll=0, upAxisIndex=2, physicsClientId=env.physics_client
            )
            p_mat = p.computeProjectionMatrixFOV(fov=60, aspect=1.33, nearVal=0.1, farVal=100.0, physicsClientId=env.physics_client)
            _, _, rgb_img, _, _ = p.getCameraImage(640, 480, v_mat, p_mat, physicsClientId=env.physics_client)
            rgba_array = np.reshape(rgb_img, (480, 640, 4)).astype(np.uint8)
            left_bgr = cv2.cvtColor(rgba_array[:, :, :3], cv2.COLOR_RGB2BGR)
            
            t_arr = np.array(time_buf)
            q_arr = np.rad2deg(np.array(q_act_buf))
            h_arr = np.array(hormone_buf)
            
            line_q_failed.set_data(t_arr, q_arr[:, fault_joint_idx])
            line_q_prev.set_data(t_arr, q_arr[:, max(0, fault_joint_idx-1)])
            line_q_next.set_data(t_arr, q_arr[:, min(7, fault_joint_idx+1)])
            ax1.set_title(f'Real-Time Joint Oscillations ({controller_type}, t={current_time:.1f}s)', fontweight='bold', fontsize=10)
            
            line_h_failed.set_data(t_arr, h_arr[:, fault_joint_idx])
            line_h_prev.set_data(t_arr, h_arr[:, max(0, fault_joint_idx-1)])
            
            fig.canvas.draw()
            graph_bgr = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8).reshape((480, 640, 3))
            graph_bgr = cv2.cvtColor(graph_bgr, cv2.COLOR_RGB2BGR)
            
            combined_frame = np.hstack((left_bgr, graph_bgr))
            video_writer.write(combined_frame)

    plt.close(fig)
    video_writer.release()
    env.close()
    print(f"Split-screen video for {controller_type} completed: {output_filepath}", flush=True)

if __name__ == "__main__":
    print("Generating C1 & C2 Split-Screen Baseline Videos...", flush=True)
    generate_splitscreen_video(controller_type="C1", fault_joint_idx=3, duration=20.0, output_filepath="results/videos/c1_recovery_with_graphs.mp4")
    generate_splitscreen_video(controller_type="C2", fault_joint_idx=3, duration=20.0, output_filepath="results/videos/c2_recovery_with_graphs.mp4")
