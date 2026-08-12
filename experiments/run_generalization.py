"""
Generalization & Robustness Stress Testing Suite for Snake Robot Failure Recovery.
Evaluates controllers on unseen stress conditions:
- Intermittent Joint Failures
- Steep Slope Locomotion (10 deg Incline)
- High Sensor Noise (Gaussian error)
- Segment Mass & Inertia Perturbations (+35% body mass)
"""

import sys
import os
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

def run_stress_test_episode(
    controller_type="C5",
    stress_mode="intermittent", # 'intermittent', 'slope', 'sensor_noise', 'mass_perturbation'
    gui=False,
    seed=42
):
    np.random.seed(seed)
    
    incline_deg = 10.0 if stress_mode == "slope" else 0.0
    env_type = EnvironmentType.INCLINE if stress_mode == "slope" else EnvironmentType.FLAT
    
    env = SimulationEnvironment(gui=gui, env_type=env_type, incline_deg=incline_deg)
    robot = SnakeRobot(physics_client=env.physics_client)
    
    if stress_mode == "mass_perturbation":
        for link_idx in range(-1, robot.num_joints):
            p.changeDynamics(robot.robot_id, link_idx, mass=1.42, physicsClientId=env.physics_client)
            
    if controller_type in ["C5", "proposed"]:
        controller = AHMCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C1", "fixed"]:
        controller = FixedCPGController(num_joints=robot.num_joints)
    elif controller_type in ["C3", "shape_recovery"]:
        controller = ShapeBasedRecoveryController(num_joints=robot.num_joints)
    elif controller_type in ["C6", "ahm_nobypass"]:
        controller = AHMNobypassCPGController(num_joints=robot.num_joints)
    else:
        controller = AHMCPGController(num_joints=robot.num_joints)

    history = {
        "time": [],
        "base_position": [],
        "base_velocity": [],
        "joint_angles": [],
        "target_angles": [],
        "joint_torques": [],
        "joint_velocities": []
    }

    duration = 10.0
    fault_time = 4.0
    fault_joint = 3
    sim_steps = int(duration / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
    
    target_angles = np.zeros(robot.num_joints)
    intermittent_state = False
    next_toggle_time = fault_time
    
    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        
        if stress_mode == "intermittent" and current_time >= fault_time:
            if current_time >= next_toggle_time:
                intermittent_state = not intermittent_state
                next_toggle_time = current_time + np.random.uniform(1.5, 3.0)
                if intermittent_state:
                    robot.inject_fault(joint_idx=fault_joint, fault_type=FaultType.LOCKED)
                else:
                    robot.fault_active = False
        elif current_time >= fault_time and not robot.fault_active:
            robot.inject_fault(joint_idx=fault_joint, fault_type=FaultType.LOCKED)
            
        sensory = robot.get_sensory_feedback()
        
        if stress_mode == "sensor_noise":
            sensory["joint_angles"] += np.random.normal(0, 0.05, robot.num_joints)
            
        if step % ctrl_substeps == 0:
            target_angles, ctrl_info = controller.step(sensory)
            
            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"])
            history["base_velocity"].append(sensory["base_velocity"])
            history["joint_angles"].append(sensory["joint_angles"])
            history["target_angles"].append(target_angles)
            history["joint_velocities"].append(sensory["joint_velocities"])

        applied_torques = robot.apply_joint_commands(target_angles)
        
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(applied_torques)
            
        env.step()
        
    env.close()
    
    metrics = LocomotionMetrics.calculate_metrics(
        history,
        fault_time=fault_time,
        sim_duration=duration,
        total_mass=RobotConfig.LINK_MASS * RobotConfig.NUM_SEGMENTS
    )
    return metrics

def run_generalization_benchmark(output_filepath="results/generalization_results.json"):
    controllers = ["C1", "C3", "C5", "C6"]
    stress_modes = ["intermittent", "slope", "sensor_noise", "mass_perturbation"]
    num_seeds = 2
    
    total_tasks = len(controllers) * len(stress_modes) * num_seeds
    print(f"Starting Generalization & Robustness Suite ({total_tasks} episodes)...", flush=True)
    
    results = []
    completed = 0
    start_time = time.time()
    
    for ctrl in controllers:
        for mode in stress_modes:
            for seed in range(num_seeds):
                completed += 1
                try:
                    metrics = run_stress_test_episode(controller_type=ctrl, stress_mode=mode, seed=seed * 13 + 5)
                    results.append({
                        "controller": ctrl,
                        "stress_mode": mode,
                        "seed": seed,
                        "metrics": metrics,
                        "success": True
                    })
                    print(f"[{completed:2d}/{total_tasks:2d}] {ctrl} | Mode: {mode:18s} | RecRatio={metrics['recovery_ratio']:.2f}", flush=True)
                except Exception as e:
                    print(f"[{completed:2d}/{total_tasks:2d}] {ctrl} failed: {e}", flush=True)

    elapsed = time.time() - start_time
    print(f"\nGeneralization Benchmark completed in {elapsed:.1f} seconds.", flush=True)
    
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    with open(output_filepath, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Results saved to {output_filepath}", flush=True)
    return results

if __name__ == "__main__":
    run_generalization_benchmark()
