"""
Dr. Poramate Manoonpong's Continuous-Time SO(2) Limit-Cycle Oscillator CPG Network
with Dynamic Inter-Modular Phase Coupling and Bypass Coupling Topology.
"""

import numpy as np
from config import CPGConfig, RobotConfig, SimConfig

class SO2CPGNetwork:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        
        # SO(2) Neuron States for each module i: x[i, 0] and x[i, 1]
        self.x = np.zeros((self.num_joints, 2))
        
        # Initialize with unit amplitude and desired phase offsets along the snake body
        for i in range(self.num_joints):
            angle = i * CPGConfig.DESIRED_PHASE_DIFF
            self.x[i, 0] = np.cos(angle)
            self.x[i, 1] = np.sin(angle)
            
        # Module Amplitudes and Frequency Modulators
        self.amplitudes = np.full(self.num_joints, CPGConfig.DEFAULT_AMPLITUDE)
        self.biases = np.zeros(self.num_joints)
        self.global_freq_scale = 1.0

    def set_amplitudes(self, target_amps):
        """Rate-limited update of module amplitudes."""
        self.amplitudes = np.clip(target_amps, 0.05, RobotConfig.JOINT_LIMIT_MAX)

    def set_global_frequency_scale(self, scale):
        """Scale SO(2) phase velocity (frequency modulation)."""
        self.global_freq_scale = np.clip(scale, 0.3, 1.5)

    def step(self, dt=SimConfig.CONTROL_TIMESTEP, normal_coupling_weights=None, bypass_matrix=None):
        """
        Integrate continuous SO(2) limit-cycle ODEs by 1 step (dt).
        dx1/dt = -omega * x2 + alpha * (1 - r^2) * x1 + coupling_x1
        dx2/dt =  omega * x1 + alpha * (1 - r^2) * x2 + coupling_x2
        """
        d_phi = CPGConfig.DESIRED_PHASE_DIFF
        k0 = CPGConfig.COUPLING_WEIGHT_K0
        alpha = CPGConfig.SO2_LIMIT_CYCLE_ALPHA
        omega = CPGConfig.SO2_OMEGA * self.global_freq_scale
        
        if normal_coupling_weights is None:
            normal_coupling_weights = np.ones(self.num_joints - 1)
            
        dx = np.zeros_like(self.x)
        
        for i in range(self.num_joints):
            r2 = self.x[i, 0]**2 + self.x[i, 1]**2
            
            # SO(2) intrinsic limit cycle dynamics
            dx[i, 0] = -omega * self.x[i, 1] + alpha * (1.0 - r2) * self.x[i, 0]
            dx[i, 1] =  omega * self.x[i, 0] + alpha * (1.0 - r2) * self.x[i, 1]
            
            # 1. Forward adjacent phase coupling: (i-1) -> i (phase shift d_phi)
            if i > 0:
                k_fw = k0 * normal_coupling_weights[i - 1]
                c_cos = np.cos(d_phi)
                c_sin = np.sin(d_phi)
                target_x1 = c_cos * self.x[i-1, 0] - c_sin * self.x[i-1, 1]
                target_x2 = c_sin * self.x[i-1, 0] + c_cos * self.x[i-1, 1]
                dx[i, 0] += k_fw * (target_x1 - self.x[i, 0])
                dx[i, 1] += k_fw * (target_x2 - self.x[i, 1])
                
            # 2. Backward adjacent phase coupling: (i+1) -> i (phase shift -d_phi)
            if i < self.num_joints - 1:
                k_bw = k0 * normal_coupling_weights[i]
                c_cos = np.cos(-d_phi)
                c_sin = np.sin(-d_phi)
                target_x1 = c_cos * self.x[i+1, 0] - c_sin * self.x[i+1, 1]
                target_x2 = c_sin * self.x[i+1, 0] + c_cos * self.x[i+1, 1]
                dx[i, 0] += k_bw * (target_x1 - self.x[i, 0])
                dx[i, 1] += k_bw * (target_x2 - self.x[i, 1])
                
            # 3. Dynamic Bypass Coupling: (j) -> i where j = i - 2 or i + 2
            if bypass_matrix is not None:
                # Forward bypass: i-2 -> i (phase shift = 2 * d_phi)
                if i >= 2 and bypass_matrix[i-2, i] > 0.0:
                    kb_fw = bypass_matrix[i-2, i]
                    b_cos = np.cos(2.0 * d_phi)
                    b_sin = np.sin(2.0 * d_phi)
                    target_x1 = b_cos * self.x[i-2, 0] - b_sin * self.x[i-2, 1]
                    target_x2 = b_sin * self.x[i-2, 0] + b_cos * self.x[i-2, 1]
                    dx[i, 0] += kb_fw * (target_x1 - self.x[i, 0])
                    dx[i, 1] += kb_fw * (target_x2 - self.x[i, 1])
                    
                # Backward bypass: i+2 -> i (phase shift = -2 * d_phi)
                if i <= self.num_joints - 3 and bypass_matrix[i+2, i] > 0.0:
                    kb_bw = bypass_matrix[i+2, i]
                    b_cos = np.cos(-2.0 * d_phi)
                    b_sin = np.sin(-2.0 * d_phi)
                    target_x1 = b_cos * self.x[i+2, 0] - b_sin * self.x[i+2, 1]
                    target_x2 = b_sin * self.x[i+2, 0] + b_cos * self.x[i+2, 1]
                    dx[i, 0] += kb_bw * (target_x1 - self.x[i, 0])
                    dx[i, 1] += kb_bw * (target_x2 - self.x[i, 1])

        # Euler integration
        self.x += dx * dt
        
        # Target joint angles q_d = A * x1 + b
        target_angles = self.amplitudes * self.x[:, 0] + self.biases
        return target_angles
