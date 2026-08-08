"""
Local-Global Artificial Hormone Mechanism (AHM) Engine with Spatial Diffusion
and Hill Receptor Activation.
"""

import numpy as np
from collections import deque
from config import HormoneConfig, RobotConfig, SimConfig

class HormoneEngine:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS):
        self.num_joints = num_joints
        
        # State variables
        self.H = np.zeros(self.num_joints)       # Local hormone concentration
        self.H_G = 0.0                            # Global hormone concentration
        self.R = np.zeros(self.num_joints)       # Hill receptor activation (0 to 1)
        
        # Moving window buffers for 1-cycle averaging
        window_size = int((1.0 / (SimConfig.CONTROL_TIMESTEP * 3.0)))  # W ≈ 67 steps (1 CPG cycle)
        self.window_size = max(10, window_size)
        self.e_q_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        self.e_v_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        self.e_tau_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        self.p_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        
        self.filtered_stimulus = np.zeros(self.num_joints)

    def update_feedback(self, target_q, actual_q, actual_v, commanded_tau, actual_tau):
        """Record sensory feedback mismatch and compute cycle-averaged stimulus S_i."""
        for i in range(self.num_joints):
            # Mismatch calculation
            eq = abs(target_q[i] - actual_q[i])
            ev = abs(0.0 - actual_v[i]) # reference velocity error magnitude
            etau = abs(commanded_tau[i] - actual_tau[i]) / RobotConfig.MAX_TORQUE
            p_mech = abs(actual_tau[i] * actual_v[i]) / (RobotConfig.MAX_TORQUE * RobotConfig.MAX_VELOCITY + 1e-6)
            
            self.e_q_buffers[i].append(eq)
            self.e_v_buffers[i].append(ev)
            self.e_tau_buffers[i].append(etau)
            self.p_buffers[i].append(p_mech)
            
            # Compute cycle-averaged mean errors
            bar_eq = np.mean(self.e_q_buffers[i])
            bar_ev = np.mean(self.e_v_buffers[i])
            bar_etau = np.mean(self.e_tau_buffers[i])
            bar_p = np.mean(self.p_buffers[i])
            
            # Normalize tracking errors against acceptable bounds
            norm_eq = np.clip(bar_eq / (RobotConfig.JOINT_LIMIT_MAX * 0.4), 0.0, 1.0)
            norm_ev = np.clip(bar_ev / (RobotConfig.MAX_VELOCITY * 0.5), 0.0, 1.0)
            norm_etau = np.clip(bar_etau, 0.0, 1.0)
            norm_p = np.clip(bar_p, 0.0, 1.0)
            
            # Weighted stimulus
            S_i = (HormoneConfig.W_Q * norm_eq +
                   HormoneConfig.W_V * norm_ev +
                   HormoneConfig.W_TAU * norm_etau +
                   HormoneConfig.W_P * norm_p)
                   
            self.filtered_stimulus[i] = S_i

    def step(self, dt=SimConfig.CONTROL_TIMESTEP):
        """Integrate Local & Global Hormone ODEs and compute Hill Receptor Activation."""
        dH = np.zeros(self.num_joints)
        alpha = HormoneConfig.ALPHA_H
        d0 = HormoneConfig.D0
        kd = HormoneConfig.KD
        n = HormoneConfig.EXP_N
        Dh = HormoneConfig.DIFFUSION_DH
        
        for i in range(self.num_joints):
            # Secretion and nonlinear decay: alpha * S_i - (d0 + kd * H_i^n) * H_i
            secretion = alpha * self.filtered_stimulus[i]
            decay = (d0 + kd * (self.H[i] ** n)) * self.H[i]
            
            # 1D Spatial Spine Diffusion
            if i == 0:
                diffusion = Dh * (self.H[1] - self.H[0])
            elif i == self.num_joints - 1:
                diffusion = Dh * (self.H[self.num_joints - 2] - self.H[self.num_joints - 1])
            else:
                diffusion = Dh * (self.H[i - 1] + self.H[i + 1] - 2.0 * self.H[i])
                
            dH[i] = secretion - decay + diffusion
            
        # Euler integration
        self.H = np.clip(self.H + dH * dt, 0.0, 5.0)
        
        # Global Hormone Concentration
        self.H_G = np.mean(self.H)
        
        # Hill Receptor Activation R_i = H_i^m / (Kh^m + H_i^m)
        m = HormoneConfig.HILL_M
        Kh = HormoneConfig.KH
        self.R = (self.H ** m) / ((Kh ** m) + (self.H ** m) + 1e-9)
        self.R = np.clip(self.R, 0.0, 1.0)
        
        return self.H, self.H_G, self.R
