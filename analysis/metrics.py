"""
Performance Analysis & Evaluation Metrics for Snake Robot Locomotion Recovery.
"""

import numpy as np
from config import RobotConfig

class LocomotionMetrics:
    @staticmethod
    def calculate_metrics(
        history,
        fault_time=15.0,
        sim_duration=60.0,
        total_mass=9.45,
        forward_axis=(0.0, -1.0),
        heading_window_s=0.5,
        fall_height_threshold=0.02,
        fall_vertical_alignment_threshold=0.5,
        torque_saturation_threshold=0.99,
        locked_joint_idx=None,
        locked_angle=None,
        locked_drift_tolerance_rad=1e-3,
        locked_drift_settle_window_s=0.5,
    ):
        """Compute task-level locomotion metrics using an explicit forward axis."""
        time = np.asarray(history["time"], dtype=float)
        base_vels = np.asarray(history["base_velocity"], dtype=float)
        base_poss = np.asarray(history["base_position"], dtype=float)
        base_orns = np.asarray(history["base_orientation"], dtype=float)
        if len(time) < 2:
            raise ValueError("At least two history samples are required")

        axis = np.asarray(forward_axis, dtype=float)
        axis = axis / (np.linalg.norm(axis) + 1e-12)
        lateral_axis = np.array([-axis[1], axis[0]])
        xy_velocity = base_vels[:, :2]
        forward_velocity = xy_velocity @ axis
        lateral_velocity = xy_velocity @ lateral_axis

        pre_idx = np.where((time >= fault_time - 5.0) & (time < fault_time))[0]
        post_idx = np.where(time >= fault_time)[0]
        if len(pre_idx) == 0 or len(post_idx) == 0:
            raise ValueError("Both pre-fault and post-fault samples are required")

        v_pre = float(np.mean(forward_velocity[pre_idx]))
        v_post = float(np.mean(forward_velocity[post_idx]))
        valid_baseline = v_pre > 1e-9
        if valid_baseline:
            velocity_ratio = forward_velocity / v_pre
            recovery_ratio = v_post / v_pre
        else:
            velocity_ratio = np.zeros_like(forward_velocity)
            recovery_ratio = 0.0

        dt = float(np.median(np.diff(time)))
        sustain_steps = max(1, int(round(5.0 / dt)))
        recovery_time = float(sim_duration - fault_time)
        recovery_success = False
        if valid_baseline and len(post_idx) >= sustain_steps:
            for idx in range(len(post_idx) - sustain_steps + 1):
                window = velocity_ratio[post_idx[idx : idx + sustain_steps]]
                if 0.90 <= np.mean(window) <= 1.10:
                    recovery_time = float(time[post_idx[idx]] - fault_time)
                    recovery_success = True
                    break

        post_start = post_idx[0]
        post_displacement = base_poss[-1, :2] - base_poss[post_start, :2]
        forward_progress = float(post_displacement @ axis)
        window_steps = max(1, int(round(heading_window_s / dt)))
        window_heading = []
        lateral_drift = 0.0
        for start in range(post_start, len(base_poss) - window_steps, window_steps):
            end = start + window_steps
            window_displacement = base_poss[end, :2] - base_poss[start, :2]
            window_forward = float(window_displacement @ axis)
            window_lateral = float(window_displacement @ lateral_axis)
            lateral_drift += abs(window_lateral)
            if window_forward > 0.05 * heading_window_s:
                window_heading.append(
                    np.degrees(np.arctan2(abs(window_lateral), window_forward))
                )
        stall_fraction = float(np.mean(forward_velocity[post_idx] < 0.05))
        heading_deviation_deg = float(
            np.mean(window_heading) if window_heading else 90.0
        )

        performance_loss_auc = float(
            np.mean(np.clip(1.0 - velocity_ratio[post_idx], 0.0, 1.0))
        )
        torques = np.asarray(history["joint_torques"], dtype=float)
        j_vels = np.asarray(history["joint_velocities"], dtype=float)
        total_energy = float(np.sum(np.abs(torques * j_vels)) * dt)
        displacement = base_poss[-1, :2] - base_poss[0, :2]
        distance_traveled = max(0.01, float(np.linalg.norm(displacement)))
        cot = total_energy / (total_mass * 9.81 * distance_traveled)
        q_act = np.asarray(history["joint_angles"], dtype=float)
        q_target = np.asarray(history["target_angles"], dtype=float)
        shape_error = float(np.mean((q_act - q_target) ** 2))

        # A fall is defined by low base height or loss of upright alignment.
        # Quaternion order follows PyBullet: x, y, z, w.
        qx, qy, qz, qw = base_orns.T
        vertical_alignment = 1.0 - 2.0 * (qx * qx + qy * qy)
        upright = vertical_alignment >= fall_vertical_alignment_threshold
        above_ground = base_poss[:, 2] >= fall_height_threshold
        no_fall = above_ground & upright & np.isfinite(base_poss[:, 2])
        post_no_fall = no_fall[post_idx]
        survival = bool(np.all(post_no_fall))
        survival_fraction = float(np.mean(post_no_fall))
        fall_fraction = 1.0 - survival_fraction
        torque_saturation_fraction = float(
            np.mean(np.abs(torques[post_idx]) >= torque_saturation_threshold * RobotConfig.MAX_TORQUE)
        )

        locked_joint_drift_max_rad = None
        locked_joint_drift_rms_rad = None
        locked_joint_drift_within_tolerance = None
        locked_joint_drift_steady_max_rad = None
        locked_joint_drift_steady_within_tolerance = None
        if locked_joint_idx is not None and locked_angle is not None:
            locked_angles = q_act[post_idx, int(locked_joint_idx)]
            drift = np.abs(locked_angles - float(locked_angle))
            locked_joint_drift_max_rad = float(np.max(drift))
            locked_joint_drift_rms_rad = float(np.sqrt(np.mean(drift ** 2)))
            locked_joint_drift_within_tolerance = bool(
                locked_joint_drift_max_rad <= locked_drift_tolerance_rad + 1e-12
            )
            steady_idx = np.where(time >= fault_time + locked_drift_settle_window_s)[0]
            if len(steady_idx):
                steady_drift = np.abs(q_act[steady_idx, int(locked_joint_idx)] - float(locked_angle))
                locked_joint_drift_steady_max_rad = float(np.max(steady_drift))
                locked_joint_drift_steady_within_tolerance = bool(
                    locked_joint_drift_steady_max_rad <= locked_drift_tolerance_rad + 1e-12
                )

        return {
            "v_pre": v_pre,
            "v_post": v_post,
            "recovery_ratio": float(recovery_ratio),
            "recovery_time": recovery_time,
            "recovery_success": recovery_success,
            "performance_loss_auc": performance_loss_auc,
            "forward_progress": forward_progress,
            "lateral_drift": lateral_drift,
            "stall_fraction": stall_fraction,
            "heading_deviation_deg": heading_deviation_deg,
            "total_energy": total_energy,
            "cost_of_transport": cot,
            "shape_error": shape_error,
            "distance_traveled": distance_traveled,
            "survival": survival,
            "survival_fraction": survival_fraction,
            "fall_fraction": fall_fraction,
            "torque_saturation_fraction": torque_saturation_fraction,
            "locked_joint_drift_max_rad": locked_joint_drift_max_rad,
            "locked_joint_drift_rms_rad": locked_joint_drift_rms_rad,
            "locked_joint_drift_within_tolerance": locked_joint_drift_within_tolerance,
            "locked_joint_drift_steady_max_rad": locked_joint_drift_steady_max_rad,
            "locked_joint_drift_steady_within_tolerance": locked_joint_drift_steady_within_tolerance,
        }
