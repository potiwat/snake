"""
Factorial Benchmark Suite for Statistical Analysis.
Executes batch simulations sequentially with fast 10s duration for C1-C6, failure types, joint locations, and environments.
"""

import sys
import os
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from config import SimConfig
from simulation.snake_robot import FaultType
from simulation.environments import EnvironmentType
from experiments.run_single import run_single_episode

def run_full_factorial_benchmark(
    controllers=None,
    fault_types=None,
    joint_indices=None,
    env_types=None,
    num_seeds=2,
    duration=10.0,
    output_filepath="results/full_benchmark_results.json"
):
    if controllers is None:
        controllers = ["C1", "C2", "C3", "C4", "C5", "C6"]
    if fault_types is None:
        fault_types = [FaultType.LOCKED, FaultType.FREE]
    if joint_indices is None:
        joint_indices = [1, 3] # Anterior (1), Middle (3)
    if env_types is None:
        env_types = [EnvironmentType.FLAT]

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    results = []
    total_tasks = len(controllers) * len(fault_types) * len(joint_indices) * len(env_types) * num_seeds
    completed = 0
    start_time = time.time()
    
    print(f"Starting Fast Factorial Benchmark Suite ({total_tasks} episodes)...", flush=True)
    
    for ctrl in controllers:
        for f_type in fault_types:
            for j_idx in joint_indices:
                for env_t in env_types:
                    for seed in range(num_seeds):
                        completed += 1
                        try:
                            history, metrics = run_single_episode(
                                controller_type=ctrl,
                                fault_type=f_type,
                                fault_joint_idx=j_idx,
                                fault_time=4.0,
                                duration=duration,
                                gui=False,
                                env_type=env_t,
                                seed=seed * 19 + 7
                            )
                            record = {
                                "controller": ctrl,
                                "fault_type": f_type,
                                "joint_idx": j_idx,
                                "environment": env_t,
                                "seed": seed,
                                "metrics": metrics,
                                "success": True
                            }
                            results.append(record)
                            print(f"[{completed:2d}/{total_tasks:2d}] {ctrl} | {f_type} | Joint {j_idx} | RecRatio={metrics['recovery_ratio']:.2f}", flush=True)
                        except Exception as e:
                            print(f"[{completed:2d}/{total_tasks:2d}] {ctrl} failed: {e}", flush=True)

    elapsed = time.time() - start_time
    print(f"\nFull Benchmark Suite completed in {elapsed:.1f} seconds.", flush=True)
    
    with open(output_filepath, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Results saved to {output_filepath}", flush=True)
    return results

if __name__ == "__main__":
    run_full_factorial_benchmark()
