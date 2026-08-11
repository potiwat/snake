"""
Hyperparameter Sensitivity Sweep Runner for AHM-CPG Snake Robot.
Evaluates 2D parameter grids:
  1. Diffusion Coefficient D_h vs Secretion Rate alpha_h
  2. Hill Threshold K_h vs Hill Exponent m

Outputs results to results/publication/data/sensitivity_results.json.
"""

import sys
import os
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pybullet as p
from config import SimConfig, RobotConfig, HormoneConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from analysis.metrics import LocomotionMetrics

OUTPUT_PATH = Path("results/publication/data/sensitivity_results.json")

def evaluate_episode(dh, alpha_h, kh, hill_m, fault_joint=3, duration=60.0, fault_time=15.0, seed=42):
    """Run episode with specific hormone parameters."""
    np.random.seed(seed)
    
    # Override HormoneConfig dynamically
    orig_dh = HormoneConfig.DIFFUSION_DH
    orig_alpha = HormoneConfig.ALPHA_H
    orig_kh = HormoneConfig.KH
    orig_m = HormoneConfig.HILL_M
    
    HormoneConfig.DIFFUSION_DH = float(dh)
    HormoneConfig.ALPHA_H = float(alpha_h)
    HormoneConfig.KH = float(kh)
    HormoneConfig.HILL_M = float(hill_m)
    
    try:
        env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
        robot = SnakeRobot(physics_client=env.physics_client)
        controller = AHMCPGController(num_joints=robot.num_joints)
        
        history = {
            "time": [], "base_position": [], "base_velocity": [],
            "joint_angles": [], "target_angles": [], "joint_torques": [],
            "joint_velocities": [], "hormones": [], "receptors": []
        }
        
        sim_steps = int(duration / SimConfig.TIMESTEP)
        ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)
        target_angles = np.zeros(robot.num_joints)
        fault_injected = False
        
        for step in range(sim_steps):
            current_time = step * SimConfig.TIMESTEP
            if not fault_injected and current_time >= fault_time:
                robot.inject_fault(joint_idx=fault_joint, fault_type=FaultType.FREE)
                fault_injected = True
                
            sensory = robot.get_sensory_feedback()
            if step % ctrl_substeps == 0:
                target_angles, ctrl_info = controller.step(sensory)
                
            robot.apply_joint_commands(target_angles)
            env.step()
            
            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"])
            history["base_velocity"].append(sensory["base_velocity"])
            history["joint_angles"].append(sensory["joint_angles"])
            history["target_angles"].append(target_angles.copy())
            history["joint_torques"].append(sensory["joint_torques"])
            history["joint_velocities"].append(sensory["joint_velocities"])
            history["hormones"].append(ctrl_info["hormones"].copy())
            history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).copy())
            
        env.close()
        
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=fault_time)
        return {
            "recovery_ratio": float(metrics["recovery_ratio"]),
            "recovery_time": float(metrics["recovery_time"]),
            "performance_loss_auc": float(metrics["performance_loss_auc"]),
            "cost_of_transport": float(metrics["cost_of_transport"]),
            "distance_traveled": float(metrics["distance_traveled"])
        }
    finally:
        # Restore original config
        HormoneConfig.DIFFUSION_DH = orig_dh
        HormoneConfig.ALPHA_H = orig_alpha
        HormoneConfig.KH = orig_kh
        HormoneConfig.HILL_M = orig_m

def main():
    print("=== Running Hyperparameter Sensitivity Sweep ===")
    
    dh_grid = [0.01,0.05, 0.12, 0.22, 0.35, 0.50]
    alpha_grid = [0.1, 0.25, 0.3, 0.4, 0.45, 0.6, 0.7, 0.80, 0.9, 1.00]
    
    kh_grid = [0.15, 0.25, 0.35, 0.50, 0.65]
    m_grid = [2.0, 3.0, 4.0, 5.0, 6.0]
    
    results = {
        "dh_alpha_grid": {
            "dh_values": dh_grid,
            "alpha_values": alpha_grid,
            "rv_matrix": [],
            "trec_matrix": []
        },
        "kh_m_grid": {
            "kh_values": kh_grid,
            "m_values": m_grid,
            "rv_matrix": [],
            "trec_matrix": []
        }
    }
    
    # 1. Sweep D_h vs alpha_h (with K_h=0.35, m=3.0)
    print("\n--- Sweeping D_h vs alpha_h ---")
    rv_dh_alpha = []
    trec_dh_alpha = []
    for dh in dh_grid:
        rv_row = []
        trec_row = []
        for alpha_h in alpha_grid:
            m_res = evaluate_episode(dh=dh, alpha_h=alpha_h, kh=0.65, hill_m=2.0)
            rv_row.append(m_res["recovery_ratio"])
            trec_row.append(m_res["recovery_time"])
            print(f"D_h={dh:.2f}, alpha_h={alpha_h:.2f} -> Rv={m_res['recovery_ratio']:.3f}, Trec={m_res['recovery_time']:.1f}s")
        rv_dh_alpha.append(rv_row)
        trec_dh_alpha.append(trec_row)
        
    results["dh_alpha_grid"]["rv_matrix"] = rv_dh_alpha
    results["dh_alpha_grid"]["trec_matrix"] = trec_dh_alpha
    
    # 2. Sweep K_h vs m (with D_h=0.35, alpha_h=0.25)
    print("\n--- Sweeping K_h vs Hill Exponent m ---")
    rv_kh_m = []
    trec_kh_m = []
    for kh in kh_grid:
        rv_row = []
        trec_row = []
        for m_val in m_grid:
            m_res = evaluate_episode(dh=0.12, alpha_h=0.6, kh=kh, hill_m=m_val)
            rv_row.append(m_res["recovery_ratio"])
            trec_row.append(m_res["recovery_time"])
            print(f"K_h={kh:.2f}, m={m_val:.1f} -> Rv={m_res['recovery_ratio']:.3f}, Trec={m_res['recovery_time']:.1f}s")
        rv_kh_m.append(rv_row)
        trec_kh_m.append(trec_row)
        
    results["kh_m_grid"]["rv_matrix"] = rv_kh_m
    results["kh_m_grid"]["trec_matrix"] = trec_kh_m
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Sensitivity sweep complete. Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
