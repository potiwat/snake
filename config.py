"""
Config file for Local-Global Artificial Hormone-Gated CPG Snake Robot Simulation.
"""

import numpy as np

class RobotConfig:
    NUM_SEGMENTS = 9
    NUM_JOINTS = 8
    LINK_LENGTH = 0.122    # total body ~ 1.1 m
    LINK_RADIUS = 0.035
    LINK_MASS = 1.05       # total body ~ 9.45 kg
    MAX_TORQUE = 8.0       # N*m max joint torque
    MAX_VELOCITY = 10.0    # rad/s max joint speed
    
    # Low-level PD Controller
    KP = 45.0
    KD = 4.5
    
    # Joint limits (radians)
    JOINT_LIMIT_MIN = -np.pi / 3.0  # -60 deg
    JOINT_LIMIT_MAX = np.pi / 3.0   # +60 deg

class CPGConfig:
    # Dr. Manoonpong's SO(2) Limit-Cycle Oscillator Parameters
    FREQUENCY_HZ = 1.00            # Nominal undulation frequency (1.0 Hz)
    SO2_OMEGA = 2.0 * np.pi * FREQUENCY_HZ
    DEFAULT_AMPLITUDE = 0.60       # ~34.4 degrees nominal swing amplitude
    DESIRED_PHASE_DIFF = np.pi / 4 # pi/4 phase difference per joint (~45 deg)
    SO2_LIMIT_CYCLE_ALPHA = 2.5    # Limit cycle convergence gain
    
    # Coupling Strengths
    COUPLING_WEIGHT_K0 = 1.20      # Nominal adjacent joint coupling weight
    BYPASS_WEIGHT_KB = 2.80        # Dynamic bypass coupling weight K_B
    
    # Rate limiters for safe adaptation
    MAX_AMP_CHANGE_RATE = 0.15     # rad/s max rate of change of joint amplitude
    MAX_FREQ_CHANGE_RATE = 0.10    # rad/s max rate of change of frequency

class HormoneConfig:
    # Stimulus Weightings: e_q, e_v, e_tau, P_mech
    W_Q = 0.40
    W_V = 0.20
    W_TAU = 0.30
    W_P = 0.10
    
    # Hormone Dynamics
    ALPHA_H = 0.60                 # Secretion rate from stimulus (α_h, optimal sweep value)
    D0 = 0.04                      # Linear decay rate
    KD = 0.18                      # Nonlinear decay coefficient
    EXP_N = 2.0                    # Nonlinear decay exponent
    DIFFUSION_DH = 0.05            # 1D spatial diffusion coefficient along spine
    
    # Hill Receptor Activation R = H^m / (Kh^m + H^m)
    KH = 0.65                      # 50% activation threshold
    HILL_M = 2.0                   # Hill coefficient (steepness)
    
    # Reconfiguration Gains
    GAIN_AMP_DROP_GA = 0.150        # Amplitude reduction factor for failed joint
    GAIN_NEIGHBOR_GN = 0.95        # Compensation boost for adjacent joints
    NEIGHBOR_SIGMA = 1.42           # Spatial decay of neighbor compensation
    GAIN_GLOBAL_FREQ_GW = 0.15     # Global frequency reduction under high stress

class SimConfig:
    TIMESTEP = 0.005               # 200 Hz physics simulation rate
    CONTROL_TIMESTEP = 0.005       # 200 Hz CPG / Control loop rate
    NUM_SOLVER_ITERATIONS = 800    # Constraint accuracy under locomotion load
    DEFAULT_DURATION = 60.0        # Seconds per simulation episode
    DEFAULT_FAULT_TIME = 18.0      # Seconds into episode when fault is injected
    
    # Ground Contact Physics & Anisotropic Snake Friction
    LATERAL_FRICTION = 0.8
    FORWARD_FRICTION = 0.05        # Low forward friction (anisotropic snake scales)
    SIDEWAYS_FRICTION = 0.95       # High lateral friction (prevents side slipping)
