"""
Performance Analysis & Evaluation Metrics for Snake Robot Locomotion Recovery.
"""

import numpy as np
from config import RobotConfig

class LocomotionMetrics:
    @staticmethod
    def calculate_metrics(history, fault_time=15.0, sim_duration=60.0, total_mass=9.45):
        """
        Computes standard metrics from episode history log.
        history dict contains:
            - time: array of timestamps
            - base_position: array of (x, y, z)
            - base_velocity: array of (vx, vy, vz)
            - joint_angles: array of joint positions (N, 8)
            - target_angles: array of target angles (N, 8)
            - joint_torques: array of applied torques (N, 8)
            - joint_velocities: array of joint speeds (N, 8)
        """
        time = np.array(history["time"])
        base_vels = np.array(history["base_velocity"])
        base_poss = np.array(history["base_position"])
        
        # Planar 2D forward speed v_planar = sqrt(vx^2 + vy^2)
        #v_speed = np.sqrt(base_vels[:, 0]**2 + base_vels[:, 1]**2)
        v_speed = np.sqrt(base_vels[:, 0]**2 )
        
        # Pre-fault mean velocity (window t in [fault_time - 5.0, fault_time])
        pre_idx = np.where((time >= fault_time - 5.0) & (time < fault_time))[0]
        v_pre = np.mean(v_speed[pre_idx]) if len(pre_idx) > 0 else 0.35
        #v_pre = max(0.05, v_pre) # avoid division by zero
        v_pre = np.mean(v_pre) # avoid division by zero
        #print(f"Pre-fault mean velocity: {v_pre:.3f} m/s")
        #print(f"Post-fault mean velocity: {np.mean(v_speed[np.where(time >= fault_time)[0]]):.3f} m/s")
        # Normalized velocity ratio R_v(t)
        R_v = v_speed / v_pre
        print(f"position: {base_poss[-1, 0]:.3f}, {base_poss[-1, 1]:.3f}, {base_poss[-1, 2]:.3f}")
        
        # Recovery time T_rec (first time R_v >= 0.90, <1.1 sustained for 5 seconds after fault_time)
        post_idx = np.where(time >= fault_time)[0]
        t_rec = None
        sustain_steps = int(5.0 / (time[1] - time[0]))
        
        for idx in range(len(post_idx) - sustain_steps):
            window_r = R_v[post_idx[idx : idx + sustain_steps]]
            #print(f"Checking recovery window at t={time[post_idx[idx]]:.3f}s: R_v={np.mean(window_r):.3f}")
            #if np.all(window_r >= 0.40):
            if np.mean(window_r) >= 0.90:
                if np.mean(window_r) <= 1.10:
                    t_rec = float(time[post_idx[idx]] - fault_time)
                    break
                
        if t_rec is None:
            t_rec = float(sim_duration - fault_time) # Censored / Unsuccessful
            success = False
        else:
            success = True
            
        # Post-fault mean velocity
        v_post = np.mean(v_speed[post_idx])
        v_recovery_ratio = v_post / v_pre
        #print(f"Recovery time: {t_rec:.3f} s, Recovery ratio: {v_recovery_ratio:.3f}, v_pre: {v_pre:.3f}, v_post: {v_post:.3f}")
        
        # Performance Loss AUC (L_AUC)
        l_auc = np.mean(np.maximum(0.0, 1.0 - R_v[post_idx]))
        
        # Mechanical Energy & Cost of Transport (COT)
        torques = np.array(history["joint_torques"])
        j_vels = np.array(history["joint_velocities"])
        dt = time[1] - time[0]
        
        inst_power = np.sum(np.abs(torques * j_vels), axis=1)
        total_energy = np.sum(inst_power) * dt
        
        dx = base_poss[-1, 0] - base_poss[0, 0]
        dy = base_poss[-1, 1] - base_poss[0, 1]
        distance_traveled = max(0.01, np.sqrt(dx**2 + dy**2))
        cot = total_energy / (total_mass * 9.81 * distance_traveled)
        
        # Body Wave Shape Error E_shape = mean( (q_act - q_d)^2 )
        q_act = np.array(history["joint_angles"])
        q_target = np.array(history["target_angles"])
        e_shape = np.mean((q_act - q_target) ** 2)
        
        return {
            "v_pre": v_pre,
            "v_post": v_post,
            "recovery_ratio": v_recovery_ratio,
            "recovery_time": t_rec,
            "recovery_success": success,
            "performance_loss_auc": l_auc,
            "total_energy": total_energy,
            "cost_of_transport": cot,
            "shape_error": e_shape,
            "distance_traveled": distance_traveled
        }
