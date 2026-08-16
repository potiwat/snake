"""
Proposed Local-Global AHM-Gated SO(2) CPG Controller (Controller C5).
Integrates proprioceptive mismatch, hormone secretion & spatial diffusion,
amplitude/frequency modulation, and dynamic bypass coupling.
"""

import numpy as np
from config import RobotConfig, CPGConfig, HormoneConfig
from controllers.so2_cpg import SO2CPGNetwork
from controllers.hormone_engine import HormoneEngine

class AHMCPGController:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS, dh=None, hill_m=None, kb=None, gw=None, gamma_steer=None, alpha_h=None, kh=None):
        self.num_joints = num_joints
        self._kb_override = float(kb) if kb is not None else None
        self._gw_override = float(gw) if gw is not None else None
        self._gamma_steer_override = float(gamma_steer) if gamma_steer is not None else None
        
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.hormone_engine = HormoneEngine(
            num_joints=num_joints,
            dh=dh,
            alpha_h=alpha_h,
            kh=kh,
            hill_m=hill_m
        )
        
        self.last_target_angles = np.zeros(num_joints)

    @property
    def kb(self):
        return self._kb_override if self._kb_override is not None else CPGConfig.BYPASS_WEIGHT_KB

    @kb.setter
    def kb(self, val):
        self._kb_override = float(val) if val is not None else None

    @property
    def gw(self):
        return self._gw_override if self._gw_override is not None else HormoneConfig.GAIN_GLOBAL_FREQ_GW

    @gw.setter
    def gw(self, val):
        self._gw_override = float(val) if val is not None else None

    @property
    def gamma_steer(self):
        return self._gamma_steer_override if self._gamma_steer_override is not None else -0.18

    @gamma_steer.setter
    def gamma_steer(self, val):
        self._gamma_steer_override = float(val) if val is not None else None

    def step(self, feedback):
        """
        Execute 1 control loop step (100 Hz / 200 Hz).
        feedback: dict from SnakeRobot.get_sensory_feedback()
        """
        actual_q = feedback["joint_angles"]
        actual_v = feedback["joint_velocities"]
        actual_tau = feedback["joint_torques"]
        commanded_tau = feedback.get("commanded_torques", actual_tau)
        
        # 1. Update Hormone Engine with sensory feedback
        self.hormone_engine.update_feedback(
            target_q=self.last_target_angles,
            actual_q=actual_q,
            actual_v=actual_v,
            commanded_tau=commanded_tau,
            actual_tau=actual_tau
        )
        
        # 2. Step Hormone Dynamics ODE & Receptor Activation
        H, H_G, R = self.hormone_engine.step()
        
        # 3. Calculate Modulated Amplitudes
        A0 = CPGConfig.DEFAULT_AMPLITUDE
        ga = HormoneConfig.GAIN_AMP_DROP_GA
        gn = HormoneConfig.GAIN_NEIGHBOR_GN
        sigma = HormoneConfig.NEIGHBOR_SIGMA
        
        target_amplitudes = np.full(self.num_joints, A0)
        
        for j in range(self.num_joints):
            if R[j] > 0.25:
                # Damaged joint amplitude drops cleanly (relieves mechanical torque saturation)
                target_amplitudes[j] = A0 * max(0.08, 1.0 - ga * R[j])
            else:
                # Intact joint: compensation boost from damaged neighbors
                comp_sum = 0.0
                for i in range(self.num_joints):
                    if i != j and R[i] > 0.25:
                        dist = abs(j - i)
                        comp_sum += R[i] * np.exp(-dist / sigma)
                a_boost = 1.0 + gn * comp_sum
                target_amplitudes[j] = np.clip(A0 * a_boost, A0, RobotConfig.JOINT_LIMIT_MAX)
            
        self.cpg.set_amplitudes(target_amplitudes)
        
        # 4. Calculate Modulated Global Frequency
        gw = self.gw
        freq_scale = np.clip(1.0 - gw * H_G, 0.85, 1.15)
        self.cpg.set_global_frequency_scale(freq_scale)
        
        # 5. Construct Normal Coupling Weights & Dynamic Bypass Matrix
        normal_coupling = np.ones(self.num_joints - 1)
        for i in range(self.num_joints - 1):
            r_max = max(R[i], R[i+1])
            if r_max > 0.25:
                normal_coupling[i] = 0.02
            else:
                normal_coupling[i] = 1.0 - r_max
            
        # Dynamic Multi-Hop Bypass Matrix: size (num_joints, num_joints)
        bypass_matrix = np.zeros((self.num_joints, self.num_joints))
        kb = self.kb
        
        # Single-joint 2-hop bypass (i-1 <-> i+1)
        for i in range(self.num_joints):
            if R[i] > 0.25:
                if i > 0 and i < self.num_joints - 1:
                    bypass_matrix[i-1, i+1] = kb * R[i]
                    bypass_matrix[i+1, i-1] = kb * R[i]
                    
        # Dual-consecutive joint bypass (i-1 <-> i+2)
        for i in range(self.num_joints - 1):
            if R[i] > 0.25 and R[i+1] > 0.25:
                if i > 0 and i + 2 < self.num_joints:
                    r_dual = min(R[i], R[i+1])
                    bypass_matrix[i-1, i+2] = kb * r_dual
                    bypass_matrix[i+2, i-1] = kb * r_dual
                    
        # 6. Step SO(2) CPG Network with reconfigured topology
        target_angles = self.cpg.step(
            normal_coupling_weights=normal_coupling,
            bypass_matrix=bypass_matrix
        )
        
        # 7. Neutralize Locked Offset Curvature
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
            "stimuli": self.hormone_engine.filtered_stimulus,
            "amplitudes": target_amplitudes,
            "freq_scale": freq_scale
        }
