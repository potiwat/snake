"""
Local-Global Artificial Hormone Mechanism (AHM) Engine with Spatial Diffusion
and Hill Receptor Activation.
"""

import numpy as np
from collections import deque
from config import HormoneConfig, RobotConfig, SimConfig

class HormoneEngine:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS, dh=None, alpha_h=None, kh=None, hill_m=None):
        self.num_joints = num_joints
        self._dh_override = float(dh) if dh is not None else None
        self._alpha_h_override = float(alpha_h) if alpha_h is not None else None
        self._kh_override = float(kh) if kh is not None else None
        self._hill_m_override = float(hill_m) if hill_m is not None else None
        
        # State variables
        self.H = np.zeros(self.num_joints)       # Local hormone concentration
        self.H_G = 0.0                            # Global hormone concentration
        self.R = np.zeros(self.num_joints)       # Hill receptor activation (0 to 1)
        
        # Moving window buffers for 1-cycle averaging
        window_size = int((1.0 / (SimConfig.CONTROL_TIMESTEP * 1.5)))  # W ≈ 133 steps (~2/3 CPG cycle)
        self.window_size = max(20, window_size)
        self.q_tgt_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        self.q_act_buffers = [deque(maxlen=self.window_size) for _ in range(self.num_joints)]
        
        self.filtered_stimulus = np.zeros(self.num_joints)
        self.mean_q_act = np.zeros(self.num_joints)

    @property
    def dh(self):
        return self._dh_override if self._dh_override is not None else HormoneConfig.DIFFUSION_DH

    @dh.setter
    def dh(self, val):
        self._dh_override = float(val) if val is not None else None

    @property
    def alpha_h(self):
        return self._alpha_h_override if self._alpha_h_override is not None else HormoneConfig.ALPHA_H

    @alpha_h.setter
    def alpha_h(self, val):
        self._alpha_h_override = float(val) if val is not None else None

    @property
    def kh(self):
        return self._kh_override if self._kh_override is not None else HormoneConfig.KH

    @kh.setter
    def kh(self, val):
        self._kh_override = float(val) if val is not None else None

    @property
    def hill_m(self):
        return self._hill_m_override if self._hill_m_override is not None else HormoneConfig.HILL_M

    @hill_m.setter
    def hill_m(self, val):
        self._hill_m_override = float(val) if val is not None else None

    def update_feedback(self, target_q, actual_q, actual_v, commanded_tau, actual_tau):
        """Record sensory feedback and compute cycle-averaged kinematic coherence stimulus S_i."""
        for i in range(self.num_joints):
            self.q_tgt_buffers[i].append(target_q[i])
            self.q_act_buffers[i].append(actual_q[i])
            self.mean_q_act[i] = np.mean(self.q_act_buffers[i])
            
            if len(self.q_tgt_buffers[i]) >= 35:
                range_tgt = float(np.max(self.q_tgt_buffers[i]) - np.min(self.q_tgt_buffers[i]))
                range_act = float(np.max(self.q_act_buffers[i]) - np.min(self.q_act_buffers[i]))
                
                ratio = range_act / max(0.20, range_tgt)
                
                # Deficit triggers if under-moving (locked joint) or over-moving/flailing (limp/partial torque)
                under_deficit = max(0.0, HormoneConfig.RATIO_UNDER_THRESH - ratio) / 0.70
                over_deficit = max(0.0, ratio - HormoneConfig.RATIO_OVER_THRESH) / 0.60
                
                stim = max(under_deficit, over_deficit)
                self.filtered_stimulus[i] = min(1.0, stim * 1.20)
            else:
                self.filtered_stimulus[i] = 0.0

    def step(self, dt=SimConfig.CONTROL_TIMESTEP):
        """Integrate Local & Global Hormone ODEs and compute Hill Receptor Activation."""
        dH = np.zeros(self.num_joints)
        alpha = self.alpha_h
        d0 = HormoneConfig.D0
        kd = HormoneConfig.KD
        n = HormoneConfig.EXP_N
        Dh = self.dh
        
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
        self.H = np.clip(self.H + dH * dt, 0.0, 1.0)
        
        # Global Hormone Concentration
        self.H_G = float(np.mean(self.H))
        
        # Hill Receptor Activation R_i = H_i^m / (Kh^m + H_i^m)
        m = self.hill_m
        Kh = self.kh
        self.R = (self.H ** m) / ((Kh ** m) + (self.H ** m) + 1e-9)
        self.R = np.clip(self.R, 0.0, 1.0)
        
        # Dedicated Receptor Attachments
        # 1. Heading Steering Bias Receptor
        half = self.num_joints / 2.0
        pos_weights = np.array([(i - half + 0.5) for i in range(self.num_joints)])
        self.R_steer = self.R * pos_weights
        
        # 2. Joint Stiffness Receptor
        self.R_stiff = np.clip(self.R * 1.5, 0.0, 1.0)
        
        # 3. Spatial Wavelength Receptor
        self.R_wave = np.clip(self.R * 0.8, 0.0, 1.0)
        
        return self.H, self.H_G, self.R
