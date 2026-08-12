"""
Single Episode Experiment Runner for Snake Robot Locomotion & Fault Recovery.
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import numpy as np
import pybullet as p
from config import SimConfig, RobotConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType

from controllers.ahm_cpg_controller import AHMCPGController
from controllers.baselines import (
    FixedCPGController,
    ErrorAdaptiveCPGController,
    ShapeBasedRecoveryController,
    OracleFaultAwareCPGController,
    AHMNobypassCPGController
)
from analysis.metrics import LocomotionMetrics

def run_single_episode(
    controller_type="C3",
    fault_type=FaultType.LOCKED,
    fault_joint_idx=3,
    fault_time=SimConfig.DEFAULT_FAULT_TIME,
    duration=SimConfig.DEFAULT_DURATION,
    gui=False,
    env_type=EnvironmentType.FLAT,
    seed=42,
    record_video=False,
    video_filepath="results/videos/c3_simulation.mp4"
):
    np.random.seed(seed)
    env = SimulationEnvironment(
        gui=gui,
        env_type=env_type,
        record_video=record_video,
        video_filepath=video_filepath
    )
    robot = SnakeRobot(physics_client=env.physics_client)
    
    # Select Controller
    if controller_type in ["C5", "proposed", "ahm_cpg"]:
        controller = AHMCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C1", "fixed"]:
        controller = FixedCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C2", "error_adaptive"]:
        controller = ErrorAdaptiveCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C3", "shape_recovery"]:
        controller = ShapeBasedRecoveryController(num_joints=robot.num_joints)
    elif controller_type in ["C4", "oracle"]:
        controller = OracleFaultAwareCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C6", "ahm_nobypass"]:
        controller = AHMNobypassCPGController(num_joints=robot.num_joints)
    else:
        raise ValueError(f"Unknown controller_type: {controller_type}")
        
    history = {
        "time": [],
        "base_position": [],
        "base_velocity": [],
        "joint_angles": [],
        "target_angles": [],
        "joint_torques": [],
        "joint_velocities": [],
        "hormones": [],
        "receptors": []
    }
    
    sim_steps = int(duration / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    
    current_time = 0.0
    target_angles = np.zeros(robot.num_joints)
    fault_injected = False
    
    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        
        # Inject fault at specified time
        if not fault_injected and current_time >= fault_time and fault_type != FaultType.NONE:
            robot.inject_fault(
                joint_idx=fault_joint_idx,
                fault_type=fault_type,
                params={"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
            )
            fault_injected = True
            
        # Execute Control Loop at 100 Hz
        sensory = robot.get_sensory_feedback()
        if step % ctrl_substeps == 0:
            if controller_type in ["C4", "oracle"]:
                fault_info = {"active": robot.fault_active, "joint_idx": robot.fault_joint_idx}
                target_angles, ctrl_info = controller.step(sensory, fault_info=fault_info)
            else:
                target_angles, ctrl_info = controller.step(sensory)
                
            # Log history
            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"])
            history["base_velocity"].append(sensory["base_velocity"])
            history["joint_angles"].append(sensory["joint_angles"])
            history["target_angles"].append(target_angles)
            history["joint_velocities"].append(sensory["joint_velocities"])
            
            if "hormones" in ctrl_info:
                history["hormones"].append(ctrl_info["hormones"])
                history["receptors"].append(ctrl_info["receptors"])
            else:
                history["hormones"].append(np.zeros(robot.num_joints))
                history["receptors"].append(np.zeros(robot.num_joints))

        # Apply motors PD control
        applied_torques = robot.apply_joint_commands(target_angles)
        
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(applied_torques)
            
        # Capture Video Frame if recording enabled
        if record_video:
            env.capture_frame(sensory["base_position"])

        # Step Physics Engine
        env.step()
        
        if gui:
            time.sleep(SimConfig.TIMESTEP)
            
    env.close()
    
    # Calculate performance metrics
    results = LocomotionMetrics.calculate_metrics(
        history,
        fault_time=fault_time,
        sim_duration=duration,
        total_mass=RobotConfig.LINK_MASS * RobotConfig.NUM_SEGMENTS
    )
    
    return history, results

if __name__ == "__main__":
    print("Running test episode with Shape-Based Recovery CPG (C5) under Locked Joint failure...")
    history, res = run_single_episode(
        controller_type="C5",
        fault_type=FaultType.LOCKED,
        fault_joint_idx=3,
        gui=False,
        record_video=True,
        video_filepath="results/videos/c5_simulation.mp4"
    )
    print("\n=== Single Episode Metrics ===")
    for k, v in res.items():
        print(f"{k:25s}: {v}")
