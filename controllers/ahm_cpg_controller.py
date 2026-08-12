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
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.hormone_engine = HormoneEngine(num_joints=num_joints)
        
        self.last_target_angles = np.zeros(num_joints)

    def step(self, feedback):
        """
        Execute 1 control loop step (100 Hz).
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
        
        target_amplitudes = np.zeros(self.num_joints)
        
        for j in range(self.num_joints):
            # Amplitude reduction for damaged joint j
            a_drop = 1.0 - ga * R[j]
            
            # Compensation boost from surrounding damaged joints i
            comp_sum = 0.0
            for i in range(self.num_joints):
                if i != j and R[i] > 0.1:
                    dist = abs(j - i)
                    comp_sum += R[i] * np.exp(-dist / sigma)
                    
            a_boost = 1.0 + gn * comp_sum
            
            # Combined modulated amplitude
            A_j = A0 * a_drop * a_boost
            target_amplitudes[j] = np.clip(A_j, 0.05, RobotConfig.JOINT_LIMIT_MAX)
            
        self.cpg.set_amplitudes(target_amplitudes)
        
        # 4. Calculate Modulated Global Frequency
        gw = HormoneConfig.GAIN_GLOBAL_FREQ_GW
        freq_scale = 1.0 - gw * H_G
        self.cpg.set_global_frequency_scale(freq_scale)
        
        # 5. Construct Normal Coupling Weights & Dynamic Bypass Matrix
        normal_coupling = np.ones(self.num_joints - 1)
        for i in range(self.num_joints - 1):
            # Adjacent coupling decreases as either joint's receptor activation rises
            r_max = max(R[i], R[i+1])
            if r_max > 0.2:
                normal_coupling[i] = 0.001
            else:
                normal_coupling[i] = 1.0 - r_max
            
        # Bypass Matrix: size (num_joints, num_joints)
        bypass_matrix = np.zeros((self.num_joints, self.num_joints))
        kb = CPGConfig.BYPASS_WEIGHT_KB
        
        for i in range(self.num_joints):
            if R[i] > 0.2:
                # Joint i is damaged -> enable bypass between i-1 and i+1
                if i > 0 and i < self.num_joints - 1:
                    bypass_matrix[i-1, i+1] = kb * R[i]
                    bypass_matrix[i+1, i-1] = kb * R[i]
                    
        # 6. Step SO(2) CPG Network with reconfigured topology
        target_angles = self.cpg.step(
            normal_coupling_weights=normal_coupling,
            bypass_matrix=bypass_matrix
        )
        
        self.last_target_angles = target_angles
        return target_angles, {
            "hormones": H,
            "global_hormone": H_G,
            "receptors": R,
            "stimuli": self.hormone_engine.filtered_stimulus,
            "amplitudes": target_amplitudes,
            "freq_scale": freq_scale
        }
