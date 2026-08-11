"""
Fast Publication-Quality HD Split-Screen Video Renderer (C1–C6).
Uses OpenCV fast canvas drawing for real-time graphs side-by-side with 3D PyBullet view.
Resolution: 1920x720 | 30 fps | H.264 (mp4v)
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import cv2
import pybullet as p

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

CTRL_NAMES = {
    "C1": "C1: Fixed CPG Baseline",
    "C2": "C2: Error-Adaptive CPG Baseline",
    "C3": "C3: Shape Recovery Baseline",
    "C4": "C4: Oracle Fault-Aware Baseline",
    "C5": "C5: Proposed Local-Global AHM-CPG",
    "C6": "C6: Ablation AHM-CPG (No Bypass)"
}

VIDEO_DIR = "results/publication/videos"


def make_controller(ctrl_type, num_joints):
    if ctrl_type == "C5":
        return AHMCPGController(num_joints=num_joints)
    elif ctrl_type == "C1":
        return FixedCPGController(num_joints=num_joints)
    elif ctrl_type == "C2":
        return ErrorAdaptiveCPGController(num_joints=num_joints)
    elif ctrl_type == "C3":
        return ShapeBasedRecoveryController(num_joints=num_joints)
    elif ctrl_type == "C4":
        return OracleFaultAwareCPGController(num_joints=num_joints)
    elif ctrl_type == "C6":
        return AHMNobypassCPGController(num_joints=num_joints)
    raise ValueError(f"Unknown controller: {ctrl_type}")


def draw_graph_panel(w, h, time_buf, q_buf, h_buf, v_buf, fault_j, fault_time, current_time, ctrl_name):
    """Draw high-performance, crisp 960x720 right panel with 3 live plot subpanels in OpenCV."""
    panel = np.full((h, w, 3), 250, dtype=np.uint8) # Light background

    margin_x = 70
    plot_w = w - margin_x - 30

    # Subpanel heights
    h1 = 190 # Joint angles
    h2 = 190 # Hormones
    h3 = 180 # Speed

    y1 = 40
    y2 = 270
    y3 = 500

    duration = SimConfig.DEFAULT_DURATION

    def time_to_x(t):
        return int(margin_x + (t / duration) * plot_w)

    # ── Subpanel 1: Joint Oscillations ──
    cv2.rectangle(panel, (margin_x, y1), (margin_x + plot_w, y1 + h1), (255, 255, 255), -1)
    cv2.rectangle(panel, (margin_x, y1), (margin_x + plot_w, y1 + h1), (200, 200, 200), 1)
    cv2.putText(panel, f"Real-Time Joint Oscillations ({ctrl_name})", (margin_x, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2)
    cv2.putText(panel, "Angle (deg)", (10, y1 + h1 // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)

    # Grid & Zero line
    zero_y1 = y1 + h1 // 2
    cv2.line(panel, (margin_x, zero_y1), (margin_x + plot_w, zero_y1), (220, 220, 220), 1)

    # ── Subpanel 2: Local Hormone H_i ──
    cv2.rectangle(panel, (margin_x, y2), (margin_x + plot_w, y2 + h2), (255, 255, 255), -1)
    cv2.rectangle(panel, (margin_x, y2), (margin_x + plot_w, y2 + h2), (200, 200, 200), 1)
    cv2.putText(panel, "Normalized Local Hormone H_i (Spatial Diffusion & Decay)", (margin_x, y2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2)
    cv2.putText(panel, "H_i", (10, y2 + h2 // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)

    # ── Subpanel 3: Forward Speed ──
    cv2.rectangle(panel, (margin_x, y3), (margin_x + plot_w, y3 + h3), (255, 255, 255), -1)
    cv2.rectangle(panel, (margin_x, y3), (margin_x + plot_w, y3 + h3), (200, 200, 200), 1)
    cv2.putText(panel, "Forward Locomotion Speed v_xy (m/s)", (margin_x, y3 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2)
    cv2.putText(panel, "Time (s)", (margin_x + plot_w // 2 - 30, y3 + h3 + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)

    # Fault vertical dashed line
    fx = time_to_x(fault_time)
    for y_start in [y1, y2, y3]:
        h_curr = h1 if y_start == y1 else (h2 if y_start == y2 else h3)
        for y_dash in range(y_start, y_start + h_curr, 8):
            cv2.line(panel, (fx, y_dash), (fx, min(y_start + h_curr, y_dash + 4)), (0, 0, 220), 1)

    cv2.putText(panel, f"Fault @ t={fault_time:.0f}s", (fx + 5, y1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1)

    if len(time_buf) > 1:
        t_arr = np.array(time_buf)
        xs = np.array([time_to_x(t) for t in t_arr])

        # Subpanel 1 lines (deg range: -65 to +65)
        q_arr = np.rad2deg(np.array(q_buf))
        j_prev = max(0, fault_j - 1)
        j_next = min(7, fault_j + 1)

        def q_to_y(q_val):
            q_c = np.clip(q_val, -65.0, 65.0)
            return int(zero_y1 - (q_c / 65.0) * (h1 // 2 - 12))

        # Neighbor lines
        pts_prev = np.column_stack((xs, [q_to_y(val) for val in q_arr[:, j_prev]])).astype(np.int32)
        pts_next = np.column_stack((xs, [q_to_y(val) for val in q_arr[:, j_next]])).astype(np.int32)
        pts_fail = np.column_stack((xs, [q_to_y(val) for val in q_arr[:, fault_j]])).astype(np.int32)

        cv2.polylines(panel, [pts_prev], False, (200, 120, 50), 1, cv2.LINE_AA) # Blueish
        cv2.polylines(panel, [pts_next], False, (50, 180, 50), 1, cv2.LINE_AA) # Greenish
        cv2.polylines(panel, [pts_fail], False, (30, 30, 220), 2, cv2.LINE_AA) # Red failed

        # Subpanel 2 lines (Normalized Hormone range: 0 to 1.0 - Auto-scaled for high visibility)
        h_arr = np.array(h_buf)
        # Dynamic scaling based on actual peak concentration (min 0.50) so variations are prominent & clear
        h_max = max(0.50, float(np.max(h_arr)))
        h_norm_arr = np.clip(h_arr / h_max, 0.0, 1.0)

        def h_to_y(h_val_norm):
            h_c = np.clip(h_val_norm, 0.0, 1.0)
            return int(y2 + h2 - 12 - h_c * (h2 - 24))

        h_prev_pts = np.column_stack((xs, [h_to_y(val) for val in h_norm_arr[:, j_prev]])).astype(np.int32)
        h_fail_pts = np.column_stack((xs, [h_to_y(val) for val in h_norm_arr[:, fault_j]])).astype(np.int32)

        cv2.polylines(panel, [h_prev_pts], False, (180, 50, 180), 1, cv2.LINE_AA) # Purple
        cv2.polylines(panel, [h_fail_pts], False, (0, 120, 240), 2, cv2.LINE_AA) # Orange

        # Subpanel 3 line (Moving Average Window Size = 180)
        v_arr = np.array(v_buf)
        window_size = 180
        if len(v_arr) >= window_size:
            kernel = np.ones(window_size) / window_size
            v_valid = np.convolve(v_arr, kernel, mode='valid')
            initial_pad = [np.mean(v_arr[:idx+1]) for idx in range(window_size - 1)]
            v_smooth = np.concatenate([initial_pad, v_valid])
        elif len(v_arr) > 1:
            v_smooth = np.array([np.mean(v_arr[:idx+1]) for idx in range(len(v_arr))])
        else:
            v_smooth = v_arr

        # Subpanel 3 line (Speed scale range: 0.0 to 1.00 m/s without hard value clipping)
        v_scale_max = 1.10  # ปรับเพิ่มสเกลแกน Y สูงสุดเป็น 1.10 m/s เพื่อให้รองรับค่าที่เกิน 0.65 โดยไม่ต้องตัดค่า
        def v_to_y(v_val):
            return int(y3 + h3 - 12 - (v_val / v_scale_max) * (h3 - 24))

        v_pts = np.column_stack((xs, [v_to_y(val) for val in v_smooth])).astype(np.int32)
        cv2.polylines(panel, [v_pts], False, (40, 160, 40), 2, cv2.LINE_AA) # Green

    # Legends & Live Readouts
    cv2.putText(panel, f"Joint {fault_j+1} (FAILED)", (margin_x + plot_w - 180, y1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 30, 220), 1)
    cv2.putText(panel, f"Hormone H_{fault_j+1}", (margin_x + plot_w - 150, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 120, 240), 1)

    latest_v_ma = v_smooth[-1] if 'v_smooth' in locals() and len(v_smooth) > 0 else 0.0
    cv2.putText(panel, f"v_xy (MA20): {latest_v_ma:.3f} m/s", (margin_x + plot_w - 210, y3 + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 140, 30), 2)

    return panel


def render_splitscreen_video(
    controller_type="C5",
    fault_type=FaultType.LOCKED,
    fault_joint_idx=3,
    fault_time=SimConfig.DEFAULT_FAULT_TIME,
    duration=SimConfig.DEFAULT_DURATION,
    output_filepath=None,
):
    if output_filepath is None:
        output_filepath = os.path.join(
            VIDEO_DIR, f"{controller_type.lower()}_pub_splitscreen.mp4")

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.INCLINE, incline_deg=5.0)
    robot = SnakeRobot(physics_client=env.physics_client)
    controller = make_controller(controller_type, robot.num_joints)

    sim_steps = int(duration / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    frame_skip = 6 # ~33 fps

    vid_w, vid_h = 1920, 720
    cam_w, cam_h = 960, 720
    graph_w, graph_h = 960, 720

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_filepath, fourcc, 30.0, (vid_w, vid_h))

    time_buf = []
    q_act_buf = []
    h_buf = []
    vel_buf = []

    target_angles = np.zeros(robot.num_joints)
    fault_injected = False
    ctrl_name = CTRL_NAMES.get(controller_type, controller_type)

    print(f"  Rendering {controller_type}: {output_filepath} ...", flush=True)

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP

        if not fault_injected and current_time >= fault_time:
            params = {"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
            robot.inject_fault(joint_idx=fault_joint_idx,
                               fault_type=fault_type, params=params)
            fault_injected = True

        sensory = robot.get_sensory_feedback()

        if step % ctrl_substeps == 0:
            if controller_type == "C4":
                fault_info = {"active": robot.fault_active,
                              "joint_idx": robot.fault_joint_idx}
                target_angles, ctrl_info = controller.step(
                    sensory, fault_info=fault_info)
            else:
                target_angles, ctrl_info = controller.step(sensory)

            time_buf.append(current_time)
            q_act_buf.append(sensory["joint_angles"])
            h_buf.append(ctrl_info.get("hormones", np.zeros(8)))
            vx = sensory["base_velocity"][0]
            vy = sensory["base_velocity"][1]
            vel_buf.append(np.sqrt(vx**2 + vy**2))

        robot.apply_joint_commands(target_angles)
        env.step()

        # Render video frame
        if step % frame_skip == 0:
            # Fast 640x480 3D View, upscaled to 960x720
            target_pos = sensory["base_position"]
            v_mat = p.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=target_pos, distance=2.0,
                yaw=45, pitch=-30, roll=0, upAxisIndex=2,
                physicsClientId=env.physics_client
            )
            p_mat = p.computeProjectionMatrixFOV(
                fov=60, aspect=640 / 480, nearVal=0.1, farVal=100.0,
                physicsClientId=env.physics_client
            )
            _, _, rgb_img, _, _ = p.getCameraImage(
                640, 480, v_mat, p_mat,
                physicsClientId=env.physics_client
            )
            rgba = np.reshape(rgb_img, (480, 640, 4)).astype(np.uint8)
            left_bgr_small = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
            left_bgr = cv2.resize(left_bgr_small, (cam_w, cam_h), interpolation=cv2.INTER_CUBIC)

            # Text Overlay
            status = f"LOCKED FAULT (Joint {fault_joint_idx+1})" if fault_injected else "NORMAL LOCOMOTION"
            status_color = (0, 0, 255) if fault_injected else (0, 200, 0)
            cv2.putText(left_bgr, ctrl_name, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(left_bgr, f"Time: {current_time:.1f} s", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2, cv2.LINE_AA)
            cv2.putText(left_bgr, status, (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)
            if len(vel_buf) > 0:
                cv2.putText(left_bgr, f"Speed: {vel_buf[-1]:.3f} m/s", (20, 160),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 2, cv2.LINE_AA)

            # Fast OpenCV Right Panel
            right_panel = draw_graph_panel(
                graph_w, graph_h, time_buf, q_act_buf, h_buf, vel_buf,
                fault_joint_idx, fault_time, current_time, controller_type
            )

            combined = np.hstack((left_bgr, right_panel))
            writer.write(combined)

    writer.release()
    env.close()

    fsize = os.path.getsize(output_filepath) / (1024 * 1024)
    print(f"  [OK] {controller_type} video complete: {output_filepath} ({fsize:.1f} MB)", flush=True)


def render_all_videos():
    print(f"\n{'='*70}", flush=True)
    print(f"  Fast HD Split-Screen Video Renderer (C1–C6)", flush=True)
    print(f"{'='*70}\n", flush=True)

    for ctrl in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        render_splitscreen_video(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            fault_joint_idx=3,
            fault_time=SimConfig.DEFAULT_FAULT_TIME,
            duration=SimConfig.DEFAULT_DURATION
        )

    print(f"\n  All 6 HD videos saved to {VIDEO_DIR}/\n", flush=True)


if __name__ == "__main__":
    render_all_videos()
    #render_splitscreen_video(
    #            controller_type="C5",
    #            fault_type=FaultType.LOCKED,
    #            fault_joint_idx=3,
    #            fault_time=SimConfig.DEFAULT_FAULT_TIME,
     #           duration=SimConfig.DEFAULT_DURATION
    #        )