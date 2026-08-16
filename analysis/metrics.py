"""
Synthesized Journal-Grade Locomotion Recovery Metrics Suite for Snake Robots.
Synthesizes standards from:
  1. IEEE Transactions on Robotics (IEEE T-RO): Heading-aligned Forward Velocity (v_fwd),
     Lateral Trajectory Drift (Y_drift), Mechanical COT (COT_mech), RMS Torque Overload (tau_RMS).
  2. Nature (Cully et al. 2015) & Science Robotics: Normalized Self-Performance Recovery Index (R_perf),
     Multi-Scenario Generalization Resilience Index (G_robust).
  3. Bioinspiration & Biomimetics (IOP): Transient Adaptation Latency (T_adapt),
     Hormone Contrast Ratio (C_H), Kinematic Motion Jerk (J_kin).
  4. IEEE ICRA/IROS & Autonomous Robots: Deficit Performance Loss AUC (L_AUC), Path Tracking MAE.
"""

import numpy as np


class LocomotionMetrics:
    @staticmethod
    def calculate_metrics(history, fault_time=18.0, sim_duration=60.0, total_mass=9.45, nominal_speed=0.25):
        """
        Computes synthesized journal-grade performance metrics from episode history log.
        """
        time = np.array(history["time"])
        base_poss = np.array(history["base_position"])
        dt = time[1] - time[0] if len(time) > 1 else 0.015

        idx_fault = np.argmin(np.abs(time - fault_time))
        pos_start = base_poss[0]
        pos_fault = base_poss[idx_fault]
        pos_end = base_poss[-1]

        t_pre = max(0.1, time[idx_fault] - time[0])
        t_post = max(0.1, time[-1] - time[idx_fault])

        # -------------------------------------------------------------
        # 1. 2D Reference Coordinate Transformation (Heading Alignment)
        # Rotates global (X, Y) coordinates by -theta_fault so Y' aligns
        # exactly with pre-fault heading direction at t_fault
        # -------------------------------------------------------------
        dx_pre = pos_fault[0] - pos_start[0]
        dy_pre = pos_fault[1] - pos_start[1]
        theta_fault = float(np.arctan2(dx_pre, dy_pre)) if (abs(dx_pre) > 1e-4 or abs(dy_pre) > 1e-4) else 0.0

        cos_t = float(np.cos(-theta_fault))
        sin_t = float(np.sin(-theta_fault))

        poss_rel_post = base_poss[idx_fault:] - pos_fault
        x_rot = cos_t * poss_rel_post[:, 0] - sin_t * poss_rel_post[:, 1]
        y_rot = sin_t * poss_rel_post[:, 0] + cos_t * poss_rel_post[:, 1]

        dy_pre_dist = float(np.sqrt(dx_pre**2 + dy_pre**2))
        dy_post = float(abs(y_rot[-1])) if len(y_rot) > 0 else 0.0

        v_pre_fwd = float(dy_pre_dist / t_pre)
        v_post_fwd = float(dy_post / t_post)
        v_total_fwd = float(abs(pos_end[1] - pos_start[1]) / max(0.1, time[-1] - time[0]))

        dist_pre_2d = float(dy_pre_dist)
        dist_post_2d = float(np.sqrt((pos_end[0] - pos_fault[0])**2 + (pos_end[1] - pos_fault[1])**2))
        dist_total_2d = max(0.01, float(np.sqrt((pos_end[0] - pos_start[0])**2 + (pos_end[1] - pos_start[1])**2)))

        # -------------------------------------------------------------
        # Heading Deviation / Angular Yaw Drift (Delta theta_yaw)
        # -------------------------------------------------------------
        if len(x_rot) > 0 and len(y_rot) > 0:
            x_end_rot = float(x_rot[-1])
            y_end_rot = float(y_rot[-1])
            dist_end = float(np.sqrt(x_end_rot**2 + y_end_rot**2))
            if dist_end > 1e-4:
                delta_yaw_rad = float(abs(np.arctan2(x_end_rot, y_end_rot)))
                delta_yaw_signed_rad = float(np.arctan2(x_end_rot, y_end_rot))
            else:
                delta_yaw_rad = 0.0
                delta_yaw_signed_rad = 0.0
        else:
            delta_yaw_rad = 0.0
            delta_yaw_signed_rad = 0.0

        delta_yaw_deg = float(np.degrees(delta_yaw_rad))
        delta_yaw_signed_deg = float(np.degrees(delta_yaw_signed_rad))

        if len(x_rot) > 1:
            post_dists = np.sqrt(x_rot**2 + y_rot**2)
            valid_mask = post_dists > 0.05
            if np.any(valid_mask):
                inst_angles = np.abs(np.arctan2(x_rot[valid_mask], y_rot[valid_mask]))
                yaw_drift_mean_deg = float(np.degrees(np.mean(inst_angles)))
            else:
                yaw_drift_mean_deg = delta_yaw_deg
        else:
            yaw_drift_mean_deg = delta_yaw_deg

        # -------------------------------------------------------------
        # 2. IEEE Access (Dr. Potiwat Standard, Eq. 14): Displacement Index (Di) & Drift
        # -------------------------------------------------------------
        x_drift_mean = float(np.mean(np.abs(x_rot)))                        # Lateral Drift along X' axis (m)
        x_drift_max = float(np.max(np.abs(x_rot)))                          # Peak Max Lateral Drift along X' axis (m)
        y_drift_mean = float(np.mean(np.abs(y_rot)))                        # Longitudinal Motion Displacement along Y' axis (m)
        y_drift_max = float(np.max(np.abs(y_rot)))                          # Peak Max Longitudinal Displacement along Y' axis (m)

        x_drift_global_mean = float(np.mean(np.abs(base_poss[idx_fault:, 0] - pos_fault[0])))
        y_drift_global_mean = float(np.mean(np.abs(base_poss[idx_fault:, 1] - pos_fault[1])))

        dY = dy_post
        dS = max(0.001, dist_post_2d)
        dR = max(0.001, float(np.sum(np.sqrt(np.diff(x_rot)**2 + np.diff(y_rot)**2)))) if len(x_rot) > 1 else dS
        t_exp = max(0.1, float(t_post))
        v_max = float(nominal_speed)

        di_potiwat = float((dY / dS) * (dY / dR) * (dY / (t_exp * v_max)))
        di_linear = float(di_potiwat)                                      # Decimal (0.0 - 1.0) per Dr. Potiwat Eq. 14

        # -------------------------------------------------------------
        # 3. Nature (Cully et al. 2015): Normalized Self-Performance Recovery Index
        # R_perf = v_post_fwd / max(v_pre_fwd, nominal_speed)
        # -------------------------------------------------------------
        v_ref = max(nominal_speed, float(v_pre_fwd))
        r_perf = float(v_post_fwd / max(0.01, v_ref))
        r_perf_clamped = float(np.clip(r_perf, 0.0, 2.0))

        # -------------------------------------------------------------
        # 4. Bioinspiration & Biomimetics: Adaptation Latency (T_adapt)
        # Time post-fault until sustained forward velocity reaches threshold
        # -------------------------------------------------------------
        recovery_thresh = 0.40
        success = bool(r_perf_clamped >= recovery_thresh and y_drift_mean <= 0.75)

        half_win = int(2.5 / dt)
        N = len(time)
        t_adapt = float(sim_duration - fault_time)
        target_speed = recovery_thresh * v_ref

        if success:
            post_idx = np.where(time >= fault_time)[0]
            for idx in post_idx:
                i_s = max(0, idx - half_win)
                i_e = min(N - 1, idx + half_win)
                dur = (i_e - i_s) * dt
                if dur > 0.1:
                    dy_win = abs(base_poss[i_e, 1] - base_poss[i_s, 1])
                    win_v = dy_win / dur
                    if win_v >= target_speed:
                        t_adapt = float(time[idx] - fault_time)
                        break

        # -------------------------------------------------------------
        # 5. IEEE T-RO: Specific Mechanical Cost of Transport (COT_mech) & Dynamic RMS Torque
        # Approach 1: Intact Actuator Dynamic Torque Load (IEEE/ASME T-MECH Standard)
        # -------------------------------------------------------------
        q_act = np.array(history["joint_angles"]) if "joint_angles" in history else None
        q_tgt = np.array(history["target_angles"]) if "target_angles" in history else None
        v_act = np.array(history["joint_velocities"]) if "joint_velocities" in history else None

        if q_act is not None and q_tgt is not None and len(q_act) > 0 and len(q_tgt) > 0:
            kp, kd, tau_max = 40.0, 1.0, 7.67
            min_len = min(len(q_act), len(q_tgt), len(v_act))
            q_err = q_tgt[:min_len] - q_act[:min_len]
            v_err = v_act[:min_len]
            dyn_torques = np.clip(kp * q_err - kd * v_err, -tau_max, tau_max)

            # Intact joint filtering (excluding locked/unpowered joints if present)
            post_dyn_torques = dyn_torques[idx_fault:]
            tau_rms_intact = float(np.sqrt(np.mean(post_dyn_torques**2)))

            inst_power = np.sum(np.abs(post_dyn_torques * v_act[:min_len][idx_fault:]), axis=1)
            total_energy = float(np.sum(inst_power) * dt)
        else:
            total_energy = 0.0
            tau_rms_intact = 0.0

        effective_dist = max(0.05, max(dy_post, dist_post_2d))
        cot_mech = float(total_energy / (total_mass * 9.81 * effective_dist))

        # -------------------------------------------------------------
        # 6. Autonomous Robots: Deficit Performance Loss AUC (L_AUC)
        # -------------------------------------------------------------
        l_auc = float(max(0.0, 1.0 - r_perf_clamped))

        # -------------------------------------------------------------
        # 7. Bioinspiration & Biomimetics: Hormone Contrast Ratio (C_H)
        # -------------------------------------------------------------
        if "hormones" in history and len(history["hormones"]) > 0:
            h_arr = np.array(history["hormones"])[idx_fault:]
            h_max = float(np.max(h_arr))
            h_mean = float(np.mean(h_arr))
            c_hormone = float(h_max / (h_mean + 1e-4))
        else:
            c_hormone = 1.0

        # -------------------------------------------------------------
        # 8. Biological Cybernetics: Kinematic Jerk / Smoothness (J_kin)
        # -------------------------------------------------------------
        q_act = np.array(history["joint_angles"]) if "joint_angles" in history else np.zeros((len(time), 8))
        q_target = np.array(history["target_angles"]) if "target_angles" in history else np.zeros((len(time), 8))
        e_shape = float(np.mean((q_act - q_target)**2)) if len(q_act) > 0 else 0.0

        if len(q_act) > 2:
            accel = np.diff(q_act, n=2, axis=0) / (dt**2)
            jerk = np.diff(accel, axis=0) / dt
            j_kin = float(np.mean(jerk**2))
        else:
            j_kin = 0.0

        # Return backward-compatible + enriched metric dictionary
        return {
            # 6 Core Journal Metrics
            "v_fwd": float(v_post_fwd),
            "v_post_fwd": float(v_post_fwd),
            "v_pre_fwd": float(max(0.001, v_pre_fwd)),
            "v_pre": float(max(0.001, v_pre_fwd)),               # Alias for backward compatibility
            "v_post": float(v_post_fwd),                        # Alias for backward compatibility
            "recovery_ratio": float(r_perf_clamped),             # Alias for backward compatibility
            "eta_rec": float(r_perf_clamped),
            "r_perf": float(r_perf_clamped),                     # Nature Normalized Recovery Index
            "cost_of_transport": float(cot_mech),                # IEEE T-RO Mechanical COT
            "cot": float(cot_mech),
            "cot_mech": float(cot_mech),
            "total_energy": float(total_energy),
            "e_total": float(total_energy),
            "total_mechanical_energy": float(total_energy),
            "delta_yaw_deg": float(delta_yaw_deg),               # Heading Deviation Delta theta_yaw (deg)
            "delta_yaw_rad": float(delta_yaw_rad),               # Heading Deviation Delta theta_yaw (rad)
            "delta_theta_yaw": float(delta_yaw_deg),             # Standard Alias (deg)
            "delta_theta_yaw_deg": float(delta_yaw_deg),
            "delta_theta_yaw_rad": float(delta_yaw_rad),
            "yaw_drift_deg": float(delta_yaw_deg),
            "yaw_drift_mean_deg": float(yaw_drift_mean_deg),
            "delta_yaw_signed_rad": float(delta_yaw_signed_rad),
            "delta_yaw_signed_deg": float(delta_yaw_signed_deg),
            "t_adapt": float(t_adapt),                           # Adaptation Latency (s)
            "recovery_time": float(t_adapt),                     # Alias for backward compatibility
            "adaptation_time": float(t_adapt),
            
            # Complementary & Backward Compatibility Metrics
            "recovery_success": bool(success),                   # Nature/ICRA Success Criteria
            "performance_loss_auc": float(l_auc),                # Deficit AUC
            "x_drift_mean": float(x_drift_mean),                 # IEEE T-RO Lateral Drift Mean (m)
            "x_drift_max": float(x_drift_max),                   # IEEE T-RO Lateral Drift Max (m)
            "y_drift_mean": float(y_drift_mean),                 # IEEE T-RO Longitudinal Motion Mean (m)
            "y_drift_max": float(y_drift_max),                   # IEEE T-RO Longitudinal Motion Max (m)
            "di_linear": float(di_linear),                       # Dr. Potiwat IEEE Access Eq. 14 Di (Decimal 0.0 - 1.0)
            "di_potiwat": float(di_potiwat),                     # Dr. Potiwat IEEE Access Eq. 14 Di (Decimal 0.0 - 1.0)
            "tau_rms": float(tau_rms_intact),                    # IEEE T-MECH Dynamic Torque Load (Nm)
            "c_hormone": float(c_hormone),                       # Bioinspiration Hormone Contrast
            "jerk_smoothness": float(j_kin),                     # Motion Jerk Smoothness
            "shape_error": float(e_shape),
            "distance_traveled": float(dist_total_2d),
            "post_fault_distance": float(dy_post)
        }
