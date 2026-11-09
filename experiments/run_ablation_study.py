"""
Dedicated 5-Module Isolated Ablation Study Runner for AHM-CPG Snake Robot.
Evaluates:
  1. Hormone Spatial Diffusion: D_h = 0.0 vs D_h = 0.06
  2. Hill Receptor Kinetics: linear m = 1.0 vs non-linear m = 4.0
  3. Dynamic Spinal Bypass Coupling: K_B = 0.0 (C6) vs K_B = 2.80 (C5)
  4. Global Frequency Modulation: g_w = 0.0 vs g_w = 0.15
  5. Decentralized Yaw Steering Bias: gamma_steer = 0.0 vs gamma_steer = -0.18
  + Coupled Reference: D_h = 0.0 & K_B = 0.0

Evaluates N >= 10 seeds per variant under:
  - Single mid-joint locked fault (J3 locked at 0.0 rad)
  - Consecutive dual-joint locked fault (J3 + J4 locked at 0.0 rad)
  - Non-consecutive dual-joint locked fault (J2 + J5 locked at 0.0 rad)

Saves full dataset to: results/publication/data/ablation_results.json
Exports publication table to: results/publication/tables/table3_ablation.tex / .md
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool, cpu_count
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import SimConfig, RobotConfig, CPGConfig, HormoneConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from analysis.metrics import LocomotionMetrics
from analysis.statistics_publication import (
    compute_cliffs_delta,
    compute_cohens_d,
    bootstrap_ci,
    cliffs_magnitude,
    generate_table3_ablation
)

OUTPUT_PATH = PROJECT_ROOT / "results" / "publication" / "data" / "ablation_results.json"
TABLE_DIR = PROJECT_ROOT / "results" / "publication" / "tables"

ABLATION_VARIANTS = {
    "c5_baseline": {
        "name": "Full C5 Model",
        "description": "Complete Neuro-Endocrine AHM",
        "module_ablated": "none",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_dh_zero": {
        "name": "Variant 1 ($D_h = 0$)",
        "description": "No Hormone Diffusion",
        "module_ablated": "hormone_diffusion",
        "params": {"dh": 0.0, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_hill_m1": {
        "name": "Variant 2 ($m = 1$)",
        "description": "Linear Hill Gating",
        "module_ablated": "hill_kinetics",
        "params": {"dh": 0.06, "hill_m": 1.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_kb_zero": {
        "name": "Variant 3 ($K_B = 0$)",
        "description": "No Dynamic Spinal Bypass (C6)",
        "module_ablated": "spinal_bypass",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 0.0, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_gw_zero": {
        "name": "Variant 4 ($g_w = 0$)",
        "description": "No Global Frequency Mod",
        "module_ablated": "frequency_modulation",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.0, "gamma_steer": -0.18}
    },
    "ablation_gamma_zero": {
        "name": "Variant 5 ($\\gamma = 0$)",
        "description": "No Yaw Steering Bias",
        "module_ablated": "yaw_steering",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": 0.0}
    },
    "ablation_dh0_kb0": {
        "name": "Coupled Ref ($D_h=0, K_B=0$)",
        "description": "No Diff & No Bypass",
        "module_ablated": "diffusion_and_bypass",
        "params": {"dh": 0.0, "hill_m": 4.0, "kb": 0.0, "gw": 0.15, "gamma_steer": -0.18}
    }
}

ABLATION_SCENARIOS = [
    {
        "name": "locked_0rad_mid",
        "description": "Single Joint 3 locked at 0 rad",
        "faults": [(3, FaultType.LOCKED, {"locked_angle": 0.0})]
    },
    {
        "name": "dual_consecutive_j3_j4",
        "description": "Consecutive Joints 3 & 4 locked at 0 rad",
        "faults": [
            (3, FaultType.LOCKED, {"locked_angle": 0.0}),
            (4, FaultType.LOCKED, {"locked_angle": 0.0})
        ]
    },
    {
        "name": "dual_nonconsecutive_j2_j5",
        "description": "Non-consecutive Joints 2 & 5 locked at 0 rad",
        "faults": [
            (2, FaultType.LOCKED, {"locked_angle": 0.0}),
            (5, FaultType.LOCKED, {"locked_angle": 0.0})
        ]
    }
]


def _run_ablation_trial(task):
    """
    Worker task executing a single simulation episode for the ablation study.
    task: (variant_key, scenario_dict, seed, duration, fault_time)
    """
    variant_key, scenario, seed, duration, fault_time = task
    variant_info = ABLATION_VARIANTS[variant_key]
    params = variant_info["params"]
    
    np.random.seed(seed * 37 + 101)
    
    env = None
    try:
        env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
        robot = SnakeRobot(physics_client=env.physics_client)
        controller = AHMCPGController(
            num_joints=robot.num_joints,
            dh=params.get("dh"),
            hill_m=params.get("hill_m"),
            kb=params.get("kb"),
            gw=params.get("gw"),
            gamma_steer=params.get("gamma_steer")
        )
        
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
                for f_joint, f_type, f_params in scenario["faults"]:
                    robot.inject_fault(joint_idx=f_joint, fault_type=f_type, params=f_params)
                fault_injected = True
                
            sensory = robot.get_sensory_feedback()
            if step % ctrl_substeps == 0:
                target_angles, ctrl_info = controller.step(sensory)
                
            applied_torques = robot.apply_joint_commands(target_angles)
            env.step()
            
            if step % ctrl_substeps == 0:
                history["time"].append(current_time)
                history["base_position"].append(sensory["base_position"].tolist())
                history["base_velocity"].append(sensory["base_velocity"].tolist())
                history["joint_angles"].append(sensory["joint_angles"].tolist())
                history["target_angles"].append(target_angles.tolist() if hasattr(target_angles, 'tolist') else list(target_angles))
                history["joint_velocities"].append(sensory["joint_velocities"].tolist())
                history["joint_torques"].append(applied_torques)
                history["hormones"].append(ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist() if hasattr(ctrl_info.get("hormones", None), 'tolist') else list(ctrl_info.get("hormones", [0]*robot.num_joints)))
                history["receptors"].append(ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist() if hasattr(ctrl_info.get("receptors", None), 'tolist') else list(ctrl_info.get("receptors", [0]*robot.num_joints)))
                
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=fault_time, sim_duration=duration)
        
        return {
            "variant_key": variant_key,
            "variant_name": variant_info["name"],
            "scenario": scenario["name"],
            "seed": seed,
            "metrics": metrics
        }
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def run_ablation_study(num_seeds=10, duration=SimConfig.DEFAULT_DURATION, fault_time=SimConfig.DEFAULT_FAULT_TIME, parallel=True):
    """
    Execute full 5-module isolated ablation study across variants, scenarios, and random seeds.
    """
    print("\n" + "="*90)
    print("  5-MODULE ISOLATED ABLATION STUDY FOR AHM-CPG ARCHITECTURE")
    print(f"  Variants: {len(ABLATION_VARIANTS)} | Scenarios: {len(ABLATION_SCENARIOS)} | Seeds: {num_seeds}")
    print(f"  Total Trials: {len(ABLATION_VARIANTS) * len(ABLATION_SCENARIOS) * num_seeds}")
    print("="*90 + "\n")
    
    tasks = []
    for v_key in ABLATION_VARIANTS:
        for scen in ABLATION_SCENARIOS:
            for s in range(num_seeds):
                tasks.append((v_key, scen, s, duration, fault_time))
                
    start_t = time.time()
    
    if parallel:
        n_workers = min(6, max(1, cpu_count()))
        print(f"  Executing {len(tasks)} simulation episodes across {n_workers} parallel CPU cores...")
        pool = Pool(processes=n_workers)
        try:
            records = pool.map(_run_ablation_trial, tasks)
        finally:
            pool.terminate()
            pool.close()
    else:
        print(f"  Executing {len(tasks)} simulation episodes sequentially...")
        records = [_run_ablation_trial(t) for t in tasks]
        
    elapsed = time.time() - start_t
    print(f"\n  Ablation simulation completed in {elapsed:.2f}s ({elapsed/len(tasks):.2f}s per episode).\n")
    
    # Compile Statistical Summary
    stat_summary = {}
    grouped = {}
    for r in records:
        vk = r["variant_key"]
        if vk not in grouped:
            grouped[vk] = {
                "v_fwd": [], "eta_rec": [], "cot": [], "delta_yaw": [], "t_adapt": [], "e_total": []
            }
        m = r["metrics"]
        grouped[vk]["v_fwd"].append(float(m.get("v_post_fwd", m.get("v_fwd", 0.0))))
        grouped[vk]["eta_rec"].append(float(m.get("recovery_ratio", m.get("eta_rec", 0.0))))
        grouped[vk]["cot"].append(float(m.get("cost_of_transport", m.get("cot", 0.0))))
        grouped[vk]["delta_yaw"].append(float(m.get("delta_yaw_deg", m.get("delta_theta_yaw", 0.0))))
        grouped[vk]["t_adapt"].append(float(m.get("t_adapt", m.get("recovery_time", 0.0))))
        grouped[vk]["e_total"].append(float(m.get("total_energy", m.get("e_total", 0.0))))
        
    c5_etas = np.array(grouped.get("c5_baseline", {}).get("eta_rec", [0.85]))
    
    for vk, v_dict in grouped.items():
        etas = np.array(v_dict["eta_rec"])
        lo_ci, hi_ci = bootstrap_ci(etas)
        stat_summary[vk] = {
            "v_fwd_mean": float(np.mean(v_dict["v_fwd"])),
            "eta_rec_mean": float(np.mean(etas)),
            "eta_rec_std": float(np.std(etas, ddof=1)) if len(etas) > 1 else 0.0,
            "eta_rec_ci95": [float(lo_ci), float(hi_ci)],
            "cot_mean": float(np.mean(v_dict["cot"])),
            "delta_yaw_mean": float(np.mean(v_dict["delta_yaw"])),
            "t_adapt_mean": float(np.mean(v_dict["t_adapt"])),
            "e_total_mean": float(np.mean(v_dict["e_total"]))
        }
        if vk != "c5_baseline":
            d_val = compute_cohens_d(c5_etas, etas)
            delta_val = compute_cliffs_delta(list(c5_etas), list(etas))
            stat_summary[vk]["vs_c5_cohens_d"] = float(d_val)
            stat_summary[vk]["vs_c5_cliffs_delta"] = float(delta_val)
            stat_summary[vk]["vs_c5_effect"] = cliffs_magnitude(delta_val)
            
    # Assemble payload
    payload = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "num_variants": len(ABLATION_VARIANTS),
            "num_scenarios": len(ABLATION_SCENARIOS),
            "num_seeds": num_seeds,
            "total_episodes": len(records),
            "duration_s": duration,
            "fault_time_s": fault_time,
            "modules_evaluated": [
                "hormone_spatial_diffusion",
                "hill_receptor_kinetics",
                "dynamic_spinal_bypass",
                "global_frequency_modulation",
                "decentralized_yaw_steering",
                "coupled_diffusion_and_bypass"
            ]
        },
        "variants": ABLATION_VARIANTS,
        "scenarios": ABLATION_SCENARIOS,
        "statistical_summary": stat_summary,
        "records": records
    }
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  [OK] Saved Full Ablation Study Dataset: {OUTPUT_PATH}")
    
    # Generate Table 3 LaTeX & Markdown
    print("  Generating Publication Table 3 (table3_ablation.tex)...")
    generate_table3_ablation(ablation_records=records, output_dir=TABLE_DIR)
    print("\n  Ablation Study Completed Successfully.\n")
    return payload


if __name__ == "__main__":
    run_ablation_study(num_seeds=10)
