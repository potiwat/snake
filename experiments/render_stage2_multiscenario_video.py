"""
Refined Sequential Multi-Scenario 3D HD Video Renderer with Centered (0,0) Dynamic 2D Trajectory (x, y) & Auto-Scaled Plots.
100% Stable Main-Thread Sequential Execution.

Features:
  1. Subpanel 1: 2D Spatial Trajectory (x, y) with Origin (0,0) DEAD CENTER in the middle of the plot.
     Symmetric dynamic auto-scaling bounds [-R_max, +R_max] on both X and Y axes.
  2. Subpanel 2: Normalized Local Hormone Level H_4(t) across scenarios (ticks 0.00 to 1.00).
  3. Subpanel 3: Auto-Scaled Forward Locomotion Speed v_xy(t) across scenarios (ticks 0.00 to 1.50+ m/s).

Resolution: 2560 x 1080 HD @ 30 FPS
Output: results/publication/videos/stage2_4scenarios_trajectory_hd.mp4
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import cv2
import pybullet as p

from config import SimConfig, RobotConfig, HormoneConfig, CPGConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController

VIDEO_DIR = "results/publication/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(VIDEO_DIR, "stage2_4scenarios_trajectory_hd.mp4")

SCENARIOS = [
    {"name": "1. Normal Gait", "fault": FaultType.NONE, "color": (46, 204, 113)},       # Green (BGR)
    {"name": "2. Locked Joint", "fault": FaultType.LOCKED, "color": (231, 76, 60)},      # Red (BGR)
    {"name": "3. Free Joint", "fault": FaultType.FREE, "color": (243, 156, 18)},        # Orange (BGR)
    {"name": "4. Partial Drop", "fault": FaultType.PARTIAL_TORQUE, "color": (155, 89, 182)} # Purple (BGR)
]


def _run_single_scenario_simulation(sc_idx):
    sc = SCENARIOS[sc_idx]
    fault_type = sc["fault"]
    fj = SimConfig.DEFAULT_FAULT_JOINT

    print(f"  Simulating & Capturing 3D Motion Frames for Scenario {sc['name']}...", flush=True)

    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
    robot = SnakeRobot(physics_client=env.physics_client)
    np.random.seed(42)
    controller = AHMCPGController(num_joints=robot.num_joints)

    sim_steps = int(SimConfig.DEFAULT_DURATION / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    record_substeps = int(1.0 / (30.0 * SimConfig.TIMESTEP))

    w_sub3d, h_sub3d = 640, 540

    frames_bgr = []
    times = []
    pos_x = []
    pos_y = []
    h_4 = []
    speeds = []

    target_angles = np.zeros(robot.num_joints)
    fault_injected = False

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP

        if current_time >= SimConfig.DEFAULT_FAULT_TIME and not fault_injected and fault_type != FaultType.NONE:
            params_dict = {"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
            robot.inject_fault(joint_idx=fj, fault_type=fault_type, params=params_dict)
            fault_injected = True

        sensory = robot.get_sensory_feedback()

        if step % ctrl_substeps == 0:
            target_angles, ctrl_info = controller.step(sensory)

        robot.apply_joint_commands(target_angles)

        if step % record_substeps == 0:
            times.append(current_time)
            px, py_val, _ = sensory["base_position"]
            pos_x.append(px)
            pos_y.append(py_val)
            h_val = float(np.nan_to_num(ctrl_info.get("hormones", np.zeros(8))[fj]))
            h_4.append(h_val)
            sp = float(np.nan_to_num(np.linalg.norm(sensory["base_velocity"][:2])))
            speeds.append(sp)

            # Capture 3D Camera Frame
            cam_x, cam_y = px, py_val
            view_matrix = p.computeViewMatrix(
                cameraEyePosition=[cam_x - 1.4, cam_y - 1.4, 1.5],
                cameraTargetPosition=[cam_x, cam_y, 0.1],
                cameraUpVector=[0, 0, 1],
                physicsClientId=env.physics_client
            )
            proj_matrix = p.computeProjectionMatrixFOV(
                fov=60, aspect=w_sub3d / h_sub3d, nearVal=0.1, farVal=100.0,
                physicsClientId=env.physics_client
            )

            img_tuple = p.getCameraImage(
                width=w_sub3d, height=h_sub3d,
                viewMatrix=view_matrix, projectionMatrix=proj_matrix,
                renderer=p.ER_BULLET_HARDWARE_OPENGL,
                physicsClientId=env.physics_client
            )
            rgba = np.reshape(img_tuple[2], (h_sub3d, w_sub3d, 4)).astype(np.uint8)
            sub_bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)

            # Overlay Subpanel Label
            cv2.rectangle(sub_bgr, (0, 0), (w_sub3d, 35), (20, 20, 20), -1)
            cv2.putText(sub_bgr, sc["name"], (15, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, sc["color"], 2)

            if fault_injected:
                cv2.putText(sub_bgr, "FAULT ACTIVE", (w_sub3d - 160, 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
            else:
                cv2.putText(sub_bgr, "NORMAL", (w_sub3d - 120, 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            frames_bgr.append(sub_bgr)

        env.step()

    env.close()
    return {
        "frames": frames_bgr,
        "times": times,
        "pos_x": pos_x,
        "pos_y": pos_y,
        "h_4": h_4,
        "speeds": speeds
    }


def render_multi_scenario_video():
    print(f"\n{'='*90}")
    print("  RENDERING MULTI-SCENARIO 3D HD VIDEO WITH CENTERED (0,0) DYNAMIC 2D TRAJECTORY")
    print(f"  Target File: {OUTPUT_PATH}")
    print(f"{'='*90}\n")

    # 1. Run 4 Simulations Sequentially in Main Thread (100% Stable)
    results = []
    for sc_i in range(4):
        res = _run_single_scenario_simulation(sc_i)
        results.append(res)

    print("  [OK] Collected 3D Motion Frames & Trajectories for all 4 Scenarios.")

    # 2. Compute Global Dynamic Auto-Scaling Speed Bound
    all_v = []
    for r in results:
        all_v.extend(r["speeds"])
    max_v_val = max(1.50, float(np.max(all_v)) * 1.20)

    # 3. Setup OpenCV Video Writer (2560 x 1080)
    w_total, h_total = 2560, 1080
    w_3d, h_3d = 1280, 1080
    w_plot, h_plot = 1280, 1080
    w_sub3d, h_sub3d = 640, 540

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, 30.0, (w_total, h_total))

    total_frames = len(results[0]["frames"])

    print("  Stitching Quad-3D Grid and Auto-Scaled Plots into 2560x1080 HD Video...", flush=True)

    for f_idx in range(total_frames):
        # Composite 2x2 3D View Grid (1280 x 1080)
        img_3d_grid = np.zeros((h_3d, w_3d, 3), dtype=np.uint8)

        for i in range(4):
            sub_bgr = results[i]["frames"][f_idx]
            row, col = i // 2, i % 2
            y_st, x_st = row * h_sub3d, col * w_sub3d
            img_3d_grid[y_st:y_st+h_sub3d, x_st:x_st+w_sub3d] = sub_bgr

        # Center Grid Separators
        cv2.line(img_3d_grid, (640, 0), (640, 1080), (200, 200, 200), 2)
        cv2.line(img_3d_grid, (0, 540), (1280, 540), (200, 200, 200), 2)

        # Composite Right Plot Panel (1280 x 1080)
        plot_panel = np.full((h_plot, w_plot, 3), 250, dtype=np.uint8)
        margin_x = 85
        pw = w_plot - margin_x - 40

        h1, h2, h3 = 300, 280, 260
        y1, y2, y3 = 50, 410, 750

        # -----------------------------------------------------------------
        # SUBPANEL 1: Centered (0,0) Dynamic Auto-Scaled 2D Trajectory (x, y)
        # -----------------------------------------------------------------
        cv2.rectangle(plot_panel, (margin_x, y1), (margin_x + pw, y1 + h1), (255, 255, 255), -1)
        cv2.rectangle(plot_panel, (margin_x, y1), (margin_x + pw, y1 + h1), (180, 180, 180), 1)
        cv2.putText(plot_panel, "Subpanel 1: Centered (0,0) Dynamic Auto-Scaled 2D Spatial Trajectory (x, y)", (margin_x, y1 - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 2)

        # Calculate symmetric dynamic radius R_max at current frame f_idx
        cur_max_r = 2.0
        for i in range(4):
            x_curr = results[i]["pos_x"][:f_idx+1]
            y_curr = results[i]["pos_y"][:f_idx+1]
            if len(x_curr) > 0:
                max_x_sub = np.max(np.abs(x_curr))
                max_y_sub = np.max(np.abs(y_curr))
                cur_max_r = max(cur_max_r, float(max(max_x_sub, max_y_sub)) * 1.20)

        # Geometric Center Pixel of Subpanel 1
        cx = margin_x + pw // 2
        cy = y1 + h1 // 2

        def xy_to_pixel(x_m, y_m):
            px = int(cx + (float(x_m) / cur_max_r) * (pw // 2 - 25))
            py = int(cy - (float(y_m) / cur_max_r) * (h1 // 2 - 25))
            return px, py

        # Draw Center Origin Crosshairs through (0,0)
        cv2.line(plot_panel, (margin_x, cy), (margin_x + pw, cy), (210, 210, 210), 1) # X-axis
        cv2.line(plot_panel, (cx, y1), (cx, y1 + h1), (210, 210, 210), 1)             # Y-axis
        cv2.circle(plot_panel, (cx, cy), 4, (0, 0, 0), -1)                             # Origin Dot (0,0)
        cv2.putText(plot_panel, "(0,0)", (cx + 6, cy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)

        # Draw Grid Ticks around Centered Origin
        half_r = cur_max_r * 0.5
        for sign in [-1, 1]:
            # X Ticks
            px_val, _ = xy_to_pixel(sign * half_r, 0)
            if margin_x <= px_val <= margin_x + pw:
                cv2.line(plot_panel, (px_val, y1), (px_val, y1 + h1), (240, 240, 240), 1)
                cv2.putText(plot_panel, f"{sign*half_r:+.1f}m", (px_val - 18, y1 + h1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)

            # Y Ticks
            _, py_val = xy_to_pixel(0, sign * half_r)
            if y1 <= py_val <= y1 + h1:
                cv2.line(plot_panel, (margin_x, py_val), (margin_x + pw, py_val), (240, 240, 240), 1)
                cv2.putText(plot_panel, f"{sign*half_r:+.1f}m", (margin_x - 68, py_val + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 100), 1)

        cv2.putText(plot_panel, "Forward Distance x (m)", (margin_x + pw // 2 - 60, y1 + h1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 60), 1)
        cv2.putText(plot_panel, "Lateral y (m)", (8, y1 + h1 // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 60), 1)

        # Draw Trajectories up to current frame f_idx
        for i in range(4):
            x_arr = results[i]["pos_x"][:f_idx+1]
            y_arr = results[i]["pos_y"][:f_idx+1]
            if len(x_arr) > 1:
                pts = [xy_to_pixel(xm, ym) for xm, ym in zip(x_arr, y_arr)]
                for k in range(len(pts) - 1):
                    cv2.line(plot_panel, pts[k], pts[k+1], SCENARIOS[i]["color"], 2)

        # Legend inside Trajectory panel
        for i in range(4):
            lx = margin_x + 15 + (i % 2) * 220
            ly = y1 + 22 + (i // 2) * 22
            cv2.line(plot_panel, (lx, ly), (lx + 25, ly), SCENARIOS[i]["color"], 3)
            cv2.putText(plot_panel, SCENARIOS[i]["name"], (lx + 32, ly + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 30, 30), 1)

        # -----------------------------------------------------------------
        # SUBPANEL 2: Local Hormone Level H_4(t)
        # -----------------------------------------------------------------
        cv2.rectangle(plot_panel, (margin_x, y2), (margin_x + pw, y2 + h2), (255, 255, 255), -1)
        cv2.rectangle(plot_panel, (margin_x, y2), (margin_x + pw, y2 + h2), (180, 180, 180), 1)
        cv2.putText(plot_panel, "Subpanel 2: Normalized Local Hormone Concentration H_4(t) across Scenarios", (margin_x, y2 - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (20, 20, 20), 2)

        h_ticks = [1.00, 0.75, 0.50, 0.25, 0.00]
        for h_val in h_ticks:
            yp = int(y2 + h2 - 15 - h_val * (h2 - 30))
            cv2.line(plot_panel, (margin_x, yp), (margin_x + pw, yp), (235, 235, 235), 1)
            cv2.putText(plot_panel, f"{h_val:.2f}", (margin_x - 55, yp + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (80, 80, 80), 1)

        def time_to_px(t_val):
            return int(margin_x + (t_val / SimConfig.DEFAULT_DURATION) * pw)

        # Fault vertical line at t = 18s
        fx = time_to_px(SimConfig.DEFAULT_FAULT_TIME)
        for y_sec in [y2, y3]:
            h_sec = h2 if y_sec == y2 else h3
            for yd in range(y_sec, y_sec + h_sec, 8):
                cv2.line(plot_panel, (fx, yd), (fx, min(y_sec + h_sec, yd + 4)), (0, 0, 220), 1)

        cv2.putText(plot_panel, "Fault @ 18s", (fx + 5, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 220), 1)

        t_sub = results[0]["times"][:f_idx+1]
        for i in range(4):
            h_sub = results[i]["h_4"][:f_idx+1]
            if len(t_sub) > 1:
                pts = [(time_to_px(tv), int(y2 + h2 - 15 - float(np.nan_to_num(hv)) * (h2 - 30))) for tv, hv in zip(t_sub, h_sub)]
                for k in range(len(pts) - 1):
                    cv2.line(plot_panel, pts[k], pts[k+1], SCENARIOS[i]["color"], 2)

        # -----------------------------------------------------------------
        # SUBPANEL 3: Auto-Scaled Forward Locomotion Speed v_xy(t)
        # -----------------------------------------------------------------
        cv2.rectangle(plot_panel, (margin_x, y3), (margin_x + pw, y3 + h3), (255, 255, 255), -1)
        cv2.rectangle(plot_panel, (margin_x, y3), (margin_x + pw, y3 + h3), (180, 180, 180), 1)
        cv2.putText(plot_panel, "Subpanel 3: Auto-Scaled Forward Speed v_xy (m/s) across Scenarios", (margin_x, y3 - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (20, 20, 20), 2)
        cv2.putText(plot_panel, "Time (s)", (margin_x + pw // 2 - 30, y3 + h3 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 60), 1)

        v_ticks = np.linspace(0.0, max_v_val, 6)
        for v_val in v_ticks:
            yp = int(y3 + h3 - 15 - (v_val / max_v_val) * (h3 - 30))
            cv2.line(plot_panel, (margin_x, yp), (margin_x + pw, yp), (235, 235, 235), 1)
            cv2.putText(plot_panel, f"{v_val:.2f}", (margin_x - 55, yp + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (80, 80, 80), 1)

        for i in range(4):
            v_sub = results[i]["speeds"][:f_idx+1]
            if len(t_sub) > 1:
                pts = [(time_to_px(tv), int(y3 + h3 - 15 - (float(np.nan_to_num(vv)) / max_v_val) * (h3 - 30))) for tv, vv in zip(t_sub, v_sub)]
                for k in range(len(pts) - 1):
                    cv2.line(plot_panel, pts[k], pts[k+1], SCENARIOS[i]["color"], 2)

        # Merge Left Grid + Right Plot Panel
        full_frame = np.hstack((img_3d_grid, plot_panel))
        writer.write(full_frame)

        if f_idx % 300 == 0 or f_idx == total_frames - 1:
            print(f"  Stitched Frame {f_idx+1} / {total_frames} ({results[0]['times'][f_idx]:.1f}s)", flush=True)

    writer.release()
    fsize = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n  [OK GPU] Refined Multi-Scenario Centered Video Completed: {OUTPUT_PATH} ({fsize:.1f} MB)\n", flush=True)


if __name__ == "__main__":
    render_multi_scenario_video()
