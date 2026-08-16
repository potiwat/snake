"""
Baseline & Ablation Controllers (C1, C2, C3, C4, C6) for Comparative Analysis.
"""

import numpy as np
from config import RobotConfig, CPGConfig, HormoneConfig
from controllers.so2_cpg import SO2CPGNetwork
from controllers.hormone_engine import HormoneEngine

class FixedCPGController:
    """Controller C1: Fixed SO(2) CPG with no online adaptation."""
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)

    def step(self, feedback):
        target_angles = self.cpg.step()
        return target_angles, {}

class ErrorAdaptiveCPGController:
    """Controller C2: Adaptive CPG using tracking error directly without hormone/bypass dynamics."""
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.last_target = np.zeros(num_joints)
        self.filtered_errors = np.zeros(num_joints)

    def step(self, feedback):
        actual_q = feedback["joint_angles"]
        raw_errors = np.abs(self.last_target - actual_q)
        self.filtered_errors = 0.92 * self.filtered_errors + 0.08 * raw_errors
        
        A0 = CPGConfig.DEFAULT_AMPLITUDE
        target_amps = np.zeros(self.num_joints)
        for i in range(self.num_joints):
            if self.filtered_errors[i] > 0.15:
                target_amps[i] = A0 * 0.2  # drop failed joint
            else:
                target_amps[i] = A0 * 1.25 # slight general boost
                
        self.cpg.set_amplitudes(target_amps)
        target_angles = self.cpg.step()
        self.last_target = target_angles
        return target_angles, {"errors": self.filtered_errors}

class ShapeBasedRecoveryController:
    """Controller C3: Rule-based shape recovery (Elsayed et al. baseline)."""
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.last_target = np.zeros(num_joints)
        self.filtered_errors = np.zeros(num_joints)

    def step(self, feedback):
        actual_q = feedback["joint_angles"]
        raw_errors = np.abs(self.last_target - actual_q)
        self.filtered_errors = 0.992 * self.filtered_errors + 0.008 * raw_errors
        
        A0 = CPGConfig.DEFAULT_AMPLITUDE
        target_amps = np.full(self.num_joints, A0)
        
        for i in range(self.num_joints):
            if self.filtered_errors[i] > 0.25:
                target_amps[i] = A0 * 0.1 # freeze/reduce failed joint
                if i > 0:
                    target_amps[i-1] = min(A0 * 1.5, RobotConfig.JOINT_LIMIT_MAX)
                if i < self.num_joints - 1:
                    target_amps[i+1] = min(A0 * 1.5, RobotConfig.JOINT_LIMIT_MAX)
                    
        self.cpg.set_amplitudes(target_amps)
        target_angles = self.cpg.step()
        self.last_target = target_angles
        return target_angles, {}

class OracleFaultAwareCPGController:
    """Controller C4: Oracle controller with explicit ground-truth fault label access."""
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)

    def step(self, feedback, fault_info=None):
        A0 = CPGConfig.DEFAULT_AMPLITUDE
        target_amps = np.full(self.num_joints, A0)
        normal_coupling = np.ones(self.num_joints - 1)
        bypass_matrix = np.zeros((self.num_joints, self.num_joints))
        
        if fault_info and fault_info.get("active", False):
            f_idx = fault_info["joint_idx"]
            target_amps[f_idx] = A0 * 0.1
            if f_idx > 0:
                target_amps[f_idx - 1] = min(A0 * 1.45, RobotConfig.JOINT_LIMIT_MAX)
            if f_idx < self.num_joints - 1:
                target_amps[f_idx + 1] = min(A0 * 1.45, RobotConfig.JOINT_LIMIT_MAX)
                
            if f_idx > 0 and f_idx < self.num_joints - 1:
                normal_coupling[f_idx - 1] = 0.05
                normal_coupling[f_idx] = 0.05
                bypass_matrix[f_idx - 1, f_idx + 1] = CPGConfig.BYPASS_WEIGHT_KB
                bypass_matrix[f_idx + 1, f_idx - 1] = CPGConfig.BYPASS_WEIGHT_KB
                
        self.cpg.set_amplitudes(target_amps)
        target_angles = self.cpg.step(
            normal_coupling_weights=normal_coupling,
            bypass_matrix=bypass_matrix
        )
        return target_angles, {}

class AHMNobypassCPGController:
    """Controller C6: Ablation variant of C5 (AHM-CPG without Dynamic Bypass Coupling)."""
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.hormone_engine = HormoneEngine(num_joints=num_joints)
        self.last_target_angles = np.zeros(num_joints)

    def step(self, feedback):
        actual_q = feedback["joint_angles"]
        actual_v = feedback["joint_velocities"]
        actual_tau = feedback["joint_torques"]
        commanded_tau = feedback.get("commanded_torques", actual_tau)
        
        self.hormone_engine.update_feedback(
            target_q=self.last_target_angles,
            actual_q=actual_q,
            actual_v=actual_v,
            commanded_tau=commanded_tau,
            actual_tau=actual_tau
        )
        
        H, H_G, R = self.hormone_engine.step()
        
        A0 = CPGConfig.DEFAULT_AMPLITUDE
        ga = HormoneConfig.GAIN_AMP_DROP_GA
        gn = HormoneConfig.GAIN_NEIGHBOR_GN
        sigma = HormoneConfig.NEIGHBOR_SIGMA
        
        target_amplitudes = np.full(self.num_joints, A0)
        for j in range(self.num_joints):
            if R[j] > 0.25:
                target_amplitudes[j] = A0 * max(0.08, 1.0 - ga * R[j])
            else:
                comp_sum = 0.0
                for i in range(self.num_joints):
                    if i != j and R[i] > 0.25:
                        dist = abs(j - i)
                        comp_sum += R[i] * np.exp(-dist / sigma)
                a_boost = 1.0 + gn * comp_sum
                target_amplitudes[j] = np.clip(A0 * a_boost, A0, RobotConfig.JOINT_LIMIT_MAX)
            
        self.cpg.set_amplitudes(target_amplitudes)
        freq_scale = np.clip(1.0 - HormoneConfig.GAIN_GLOBAL_FREQ_GW * H_G, 0.85, 1.15)
        self.cpg.set_global_frequency_scale(freq_scale)
        
        # Standard adjacent coupling with decoupling at lesion, but NO bypass matrix
        normal_coupling = np.ones(self.num_joints - 1)
        for i in range(self.num_joints - 1):
            r_max = max(R[i], R[i+1])
            if r_max > 0.25:
                normal_coupling[i] = 0.02
            else:
                normal_coupling[i] = 1.0 - r_max
                
        target_angles = self.cpg.step(normal_coupling_weights=normal_coupling, bypass_matrix=None)
        
        # Neutralize Locked Offset Curvature
        mean_q = getattr(self.hormone_engine, 'mean_q_act', np.zeros(self.num_joints))
        offset_sum = np.sum(R * mean_q)
        healthy_mask = (R < 0.25)
        num_healthy = np.sum(healthy_mask)
        if abs(offset_sum) > 0.04 and num_healthy > 0:
            c_bias = -offset_sum / num_healthy
            for j in range(self.num_joints):
                if healthy_mask[j]:
                    target_angles[j] += c_bias
            target_angles = np.clip(target_angles, -RobotConfig.JOINT_LIMIT_MAX, RobotConfig.JOINT_LIMIT_MAX)
            
        self.last_target_angles = target_angles
        return target_angles, {
            "hormones": H,
            "global_hormone": H_G,
            "receptors": R,
            "amplitudes": target_amplitudes
        }
