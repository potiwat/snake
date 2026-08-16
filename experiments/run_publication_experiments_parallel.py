"""
Parallel Publication Experiment Runner (Multi-Core Multiprocessing).
Runs all 480 benchmark episodes, 420 generalization stress episodes, and 18 detail history episodes.
All results are saved to results/publication/data/.
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
    BENCHMARK_SCENARIOS, GENERALIZATION_MODES,
    NUM_SEEDS_BENCHMARK, NUM_SEEDS_GENERALIZATION, OUTPUT_DIR
)


def _worker_benchmark(args):
    ctrl, scen, seed_i = args
    seed = seed_i * 17 + 7
    kwargs = {
        "controller_type": ctrl,
        "fault_type": scen["fault_type"],
        "fault_joint_idx": scen["joints"][0],
        "fault_time": PUB_FAULT_TIME,
        "duration": PUB_DURATION,
        "seed": seed,
        "fault_params": scen.get("params", {})
    }
    if len(scen["joints"]) > 1:
        kwargs["multi_joint_faults"] = [
            (j, scen["fault_type"], scen.get("params", {})) for j in scen["joints"]
        ]
    try:
        metrics, _ = run_episode(**kwargs)
        return {
            "controller": ctrl,
            "fault_type": scen["fault_type"],
            "joint_idx": scen["joints"][0],
            "fault_scenario": scen["name"],
            "joints": scen["joints"],
            "seed": seed_i,
            "metrics": metrics
        }
    except Exception as e:
        print(f"Error {ctrl} {scen['name']} seed {seed_i}: {e}")
        return None


def _worker_generalization(args):
    ctrl, mode, seed_i = args
    seed = seed_i * 13 + 5
    kwargs = {
        "controller_type": ctrl,
        "fault_type": FaultType.LOCKED,
        "fault_joint_idx": 3,
        "fault_params": {"locked_angle": 0.0},
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
    elif mode == "high_slip":
        kwargs["env_type"] = EnvironmentType.HIGH_SLIP
    elif mode == "low_friction":
        kwargs["env_type"] = EnvironmentType.LOW_FRICTION
    elif mode == "dynamic_friction":
        kwargs["env_type"] = EnvironmentType.VARIABLE_FRICTION
        kwargs["transition_time"] = 30.0
        kwargs["target_transition_env"] = EnvironmentType.HIGH_SLIP

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


def _worker_detail(args):
    ctrl, detail_type = args
    detail_dir = os.path.join(OUTPUT_DIR, "detail_histories")
    os.makedirs(detail_dir, exist_ok=True)

    kwargs = {
        "controller_type": ctrl,
        "fault_type": FaultType.LOCKED,
        "fault_joint_idx": 3,
        "fault_params": {"locked_angle": 0.0},
        "fault_time": PUB_FAULT_TIME,
        "duration": PUB_DURATION,
        "seed": 42,
        "save_history": True
    }
    if detail_type == "locked_j3":
        fname = f"{ctrl.lower()}_locked_j3.json"
    elif detail_type == "dynamic_friction":
        kwargs["env_type"] = EnvironmentType.VARIABLE_FRICTION
        kwargs["transition_time"] = 30.0
        kwargs["target_transition_env"] = EnvironmentType.HIGH_SLIP
        fname = f"{ctrl.lower()}_dynamic_friction.json"
    elif detail_type == "dual_locked_j3_j4":
        kwargs["multi_joint_faults"] = [
            (3, FaultType.LOCKED, {"locked_angle": 0.0}),
            (4, FaultType.LOCKED, {"locked_angle": 0.0})
        ]
        fname = f"{ctrl.lower()}_dual_locked_j3_j4.json"
    else:
        return None

    try:
        metrics, history = run_episode(**kwargs)
        fpath = os.path.join(detail_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"history": history, "metrics": metrics}, f)
        return (ctrl, detail_type, metrics["recovery_ratio"])
    except Exception as e:
        print(f"Error detail {ctrl} {detail_type}: {e}")
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

    num_procs = min(8, max(1, cpu_count() - 1))
    print(f"Starting parallel evaluation with {num_procs} workers...", flush=True)

    # 1. Benchmark tasks (480 episodes: 6 ctrls x 8 scenarios x 10 seeds)
    b_tasks = []
    for ctrl in PUB_CONTROLLERS:
        for scen in BENCHMARK_SCENARIOS:
            for seed_i in range(NUM_SEEDS_BENCHMARK):
                b_tasks.append((ctrl, scen, seed_i))

    print(f"\n--- Phase 1: Benchmark Suite ({len(b_tasks)} episodes) ---", flush=True)
    t0 = time.time()
    pool1 = Pool(processes=num_procs)
    try:
        b_results = pool1.map(_worker_benchmark, b_tasks)
    finally:
        pool1.close()
        pool1.join()

    b_results = [r for r in b_results if r is not None]
    t_bench = time.time() - t0
    print(f"Benchmark finished in {t_bench:.1f}s. Total: {len(b_results)} episodes.", flush=True)

    with open(b_path, "w", encoding="utf-8") as f:
        json.dump(b_results, f, indent=2)

    # 2. Generalization tasks (420 episodes: 6 ctrls x 7 modes x 10 seeds)
    g_tasks = []
    for ctrl in PUB_CONTROLLERS:
        for mode in GENERALIZATION_MODES:
            for seed_i in range(NUM_SEEDS_GENERALIZATION):
                g_tasks.append((ctrl, mode, seed_i))

    print(f"\n--- Phase 2: Generalization Suite ({len(g_tasks)} episodes) ---", flush=True)
    t0 = time.time()
    pool2 = Pool(processes=num_procs)
    try:
        g_results = pool2.map(_worker_generalization, g_tasks)
    finally:
        pool2.close()
        pool2.join()

    g_results = [r for r in g_results if r is not None]
    t_gen = time.time() - t0
    print(f"Generalization finished in {t_gen:.1f}s. Total: {len(g_results)} episodes.", flush=True)

    with open(g_path, "w", encoding="utf-8") as f:
        json.dump(g_results, f, indent=2)

    # 3. Detail histories (18 episodes: 6 ctrls x 3 conditions)
    d_tasks = []
    for ctrl in PUB_CONTROLLERS:
        for dtype in ["locked_j3", "dynamic_friction", "dual_locked_j3_j4"]:
            d_tasks.append((ctrl, dtype))

    print(f"\n--- Phase 3: Detail Histories ({len(d_tasks)} episodes) ---", flush=True)
    t0 = time.time()
    pool3 = Pool(processes=num_procs)
    try:
        d_results = pool3.map(_worker_detail, d_tasks)
    finally:
        pool3.close()
        pool3.join()

    t_det = time.time() - t0
    print(f"Detail histories finished in {t_det:.1f}s.", flush=True)

    print(f"\n[DONE] All parallel evaluations saved successfully to {OUTPUT_DIR}/", flush=True)

    # Post-evaluation Statistical Analysis & Plot Generation
    import subprocess
    print("\n--- Phase 4: Post-Evaluation Statistical Analysis & Figure Generation ---", flush=True)
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
