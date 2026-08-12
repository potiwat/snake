"""
Parallel Publication Experiment Runner (8 CPU cores).
Re-runs all 270 benchmark episodes and 150 generalization stress episodes using the updated LocomotionMetrics.
"""

import sys
import os
import json
import time
import shutil
from pathlib import Path
from multiprocessing import Pool, cpu_count

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from config import SimConfig, RobotConfig
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType
from experiments.run_publication_experiments import (
    run_episode, PUB_DURATION, PUB_FAULT_TIME, PUB_CONTROLLERS,
    PUB_FAULT_TYPES, PUB_FAULT_JOINTS, OUTPUT_DIR
)

NUM_SEEDS_BENCHMARK = 5      # 5 seeds x 6 ctrls x 3 fault_types x 3 joints = 270 episodes
NUM_SEEDS_GENERALIZATION = 5 # 5 seeds x 6 ctrls x 5 stress modes = 150 episodes


def _worker_benchmark(args):
    ctrl, ft, jidx, seed_i = args
    seed = seed_i * 17 + 7
    try:
        metrics, _ = run_episode(
            controller_type=ctrl,
            fault_type=ft,
            fault_joint_idx=jidx,
            fault_time=PUB_FAULT_TIME,
            duration=PUB_DURATION,
            seed=seed
        )
        return {
            "controller": ctrl,
            "fault_type": ft,
            "joint_idx": jidx,
            "seed": seed_i,
            "metrics": metrics
        }
    except Exception as e:
        print(f"Error {ctrl} {ft} J{jidx} seed {seed_i}: {e}")
        return None


def _worker_generalization(args):
    ctrl, mode, seed_i = args
    seed = seed_i * 31 + 13
    kwargs = {
        "controller_type": ctrl,
        "fault_type": FaultType.LOCKED,
        "fault_joint_idx": 3,
        "fault_time": PUB_FAULT_TIME,
        "duration": PUB_DURATION,
        "seed": seed
    }
    if mode == "intermittent":
        kwargs["intermittent"] = True
    elif mode == "incline_10deg":
        kwargs["env_type"] = EnvironmentType.INCLINE
        kwargs["incline_deg"] = 10.0
    elif mode == "sensor_noise":
        kwargs["sensor_noise_std"] = 0.05
    elif mode == "mass_perturbation":
        kwargs["mass_scale"] = 1.35
    elif mode == "multi_joint":
        kwargs["multi_joint_faults"] = [2, 5]
        kwargs["fault_type"] = FaultType.NONE

    try:
        metrics, _ = run_episode(**kwargs)
        return {
            "controller": ctrl,
            "stress_mode": mode,
            "seed": seed_i,
            "metrics": metrics
        }
    except Exception as e:
        print(f"Error {ctrl} {mode} seed {seed_i}: {e}")
        return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    backup_dir = os.path.join(OUTPUT_DIR, "backup_prev_metrics")
    os.makedirs(backup_dir, exist_ok=True)

    # Backup existing
    b_path = os.path.join(OUTPUT_DIR, "benchmark_results.json")
    g_path = os.path.join(OUTPUT_DIR, "generalization_results.json")
    if os.path.exists(b_path):
        shutil.copy(b_path, os.path.join(backup_dir, "benchmark_results.json"))
    if os.path.exists(g_path):
        shutil.copy(g_path, os.path.join(backup_dir, "generalization_results.json"))

    num_procs = min(7, max(1, cpu_count() - 1))
    print(f"Starting parallel evaluation with {num_procs} workers...", flush=True)

    # 1. Benchmark tasks
    b_tasks = []
    for ctrl in PUB_CONTROLLERS:
        for ft in PUB_FAULT_TYPES:
            for jidx in PUB_FAULT_JOINTS:
                for seed_i in range(NUM_SEEDS_BENCHMARK):
                    b_tasks.append((ctrl, ft, jidx, seed_i))

    print(f"\n--- Phase 1: Benchmark Suite ({len(b_tasks)} episodes) ---", flush=True)
    t0 = time.time()
    pool1 = Pool(processes=num_procs)
    try:
        b_results = pool1.map(_worker_benchmark, b_tasks)
    finally:
        pool1.terminate()
        pool1.close()

    b_results = [r for r in b_results if r is not None]
    t_bench = time.time() - t0
    print(f"Benchmark finished in {t_bench:.1f}s. Total: {len(b_results)} episodes.", flush=True)

    with open(b_path, "w", encoding="utf-8") as f:
        json.dump(b_results, f, indent=2)

    # 2. Generalization tasks
    stress_modes = ["intermittent", "incline_10deg", "sensor_noise", "mass_perturbation", "multi_joint"]
    g_tasks = []
    for ctrl in PUB_CONTROLLERS:
        for mode in stress_modes:
            for seed_i in range(NUM_SEEDS_GENERALIZATION):
                g_tasks.append((ctrl, mode, seed_i))

    print(f"\n--- Phase 2: Generalization Suite ({len(g_tasks)} episodes) ---", flush=True)
    t0 = time.time()
    pool2 = Pool(processes=num_procs)
    try:
        g_results = pool2.map(_worker_generalization, g_tasks)
    finally:
        pool2.terminate()
        pool2.close()

    g_results = [r for r in g_results if r is not None]
    t_gen = time.time() - t0
    print(f"Generalization finished in {t_gen:.1f}s. Total: {len(g_results)} episodes.", flush=True)

    with open(g_path, "w", encoding="utf-8") as f:
        json.dump(g_results, f, indent=2)

    print(f"\n[DONE] All parallel evaluations saved successfully to {OUTPUT_DIR}/", flush=True)

    # Post-evaluation Statistical Analysis & Plot Generation
    import subprocess
    print("\n--- Phase 3: Post-Evaluation Statistical Analysis & Figure Generation ---", flush=True)
    try:
        subprocess.run([sys.executable, "analysis/statistics_publication.py"], check=True)
        print("  [OK] Statistical Analysis Complete.")
    except Exception as e:
        print(f"  [WARN] Stats script error: {e}")

    try:
        subprocess.run([sys.executable, "analysis/plot_publication.py"], check=True)
        print("  [OK] Publication Plots Complete.")
    except Exception as e:
        print(f"  [WARN] Plot script error: {e}")


if __name__ == "__main__":
    main()
