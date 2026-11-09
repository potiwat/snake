"""
Publication-Quality Master Experiment Runner.
Runs all experiments needed for a peer-reviewed journal paper:
  1. Full Factorial Benchmark (270 episodes)
  2. Generalization & Robustness Stress Tests (150 episodes)
  3. Detail Single-Episode Histories for Time-Series Figures (6 episodes)

All results are saved to results/publication/data/.
"""

import sys
import os
import json
import time
import pickle
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pybullet as p
from config import SimConfig, RobotConfig, CPGConfig
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


# ─── Publication Parameters ───────────────────────────────────────
PUB_DURATION = 35.0       # 35 seconds per episode
PUB_FAULT_TIME = 10.0     # Fault injected at t=10s
PUB_NUM_SEEDS = 5         # 5 seeds per condition
PUB_CONTROLLERS = ["C1", "C2", "C3", "C4", "C5", "C6"]
PUB_FAULT_TYPES = [FaultType.LOCKED, FaultType.FREE, FaultType.PARTIAL_TORQUE]
PUB_FAULT_JOINTS = [1, 3, 6]  # Anterior, Middle, Posterior

OUTPUT_DIR = "results/publication/data"
# ──────────────────────────────────────────────────────────────────


def make_controller(ctrl_type, num_joints):
    """Instantiate a controller by type string."""
    if ctrl_type in ["C5", "proposed"]:
        return AHMCPGController(num_joints=num_joints)
    elif ctrl_type in ["C1", "fixed"]:
        return FixedCPGController(num_joints=num_joints)
    elif ctrl_type in ["C2", "error_adaptive"]:
        return ErrorAdaptiveCPGController(num_joints=num_joints)
    elif ctrl_type in ["C3", "shape_recovery"]:
        return ShapeBasedRecoveryController(num_joints=num_joints)
    elif ctrl_type in ["C4", "oracle"]:
        return OracleFaultAwareCPGController(num_joints=num_joints)
    elif ctrl_type in ["C6", "ahm_nobypass"]:
        return AHMNobypassCPGController(num_joints=num_joints)
    raise ValueError(f"Unknown controller: {ctrl_type}")


def run_episode(controller_type, fault_type, fault_joint_idx, fault_time,
                duration, seed, env_type=EnvironmentType.FLAT, incline_deg=0.0,
                mass_scale=1.0, sensor_noise_std=0.0, intermittent=False,
                multi_joint_faults=None, save_history=False):
    """
    Run a single simulation episode with full parameter control.
    Returns (metrics_dict, history_dict_or_None).
    """
    np.random.seed(seed)

    env = SimulationEnvironment(
        gui=False, env_type=env_type, incline_deg=incline_deg
    )
    robot = SnakeRobot(physics_client=env.physics_client)

    # Mass perturbation
    if mass_scale != 1.0:
        new_mass = RobotConfig.LINK_MASS * mass_scale
        for link_idx in range(-1, robot.num_joints):
            p.changeDynamics(robot.robot_id, link_idx, mass=new_mass,
                             physicsClientId=env.physics_client)

    controller = make_controller(controller_type, robot.num_joints)

    history = {
        "time": [], "base_position": [], "base_velocity": [],
        "joint_angles": [], "target_angles": [], "joint_torques": [],
        "joint_velocities": [], "hormones": [], "receptors": []
    }

    sim_steps = int(duration / SimConfig.TIMESTEP)
    ctrl_substeps = int(SimConfig.CONTROL_TIMESTEP / SimConfig.TIMESTEP)

    target_angles = np.zeros(robot.num_joints)
    fault_injected = False
    intermittent_state = False
    next_toggle_time = fault_time

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP

        # ── Fault Injection Logic ──
        if current_time >= fault_time:
            if intermittent:
                if current_time >= next_toggle_time:
                    intermittent_state = not intermittent_state
                    next_toggle_time = current_time + np.random.uniform(1.5, 3.0)
                    if intermittent_state:
                        robot.inject_fault(joint_idx=fault_joint_idx,
                                           fault_type=FaultType.LOCKED)
                    else:
                        robot.fault_active = False
            elif multi_joint_faults is not None:
                if not fault_injected:
                    for jidx in multi_joint_faults:
                        robot.inject_fault(joint_idx=jidx,
                                           fault_type=FaultType.LOCKED)
                    fault_injected = True
            elif not fault_injected and fault_type != FaultType.NONE:
                params = {"gamma_f": 0.3} if fault_type == FaultType.PARTIAL_TORQUE else {}
                robot.inject_fault(joint_idx=fault_joint_idx,
                                   fault_type=fault_type, params=params)
                fault_injected = True

        # ── Sensory Feedback ──
        sensory = robot.get_sensory_feedback()

        if sensor_noise_std > 0.0:
            sensory["joint_angles"] += np.random.normal(
                0, sensor_noise_std, robot.num_joints)

        # ── Control Loop ──
        if step % ctrl_substeps == 0:
            if controller_type in ["C4", "oracle"]:
                fault_info = {"active": robot.fault_active,
                              "joint_idx": robot.fault_joint_idx}
                target_angles, ctrl_info = controller.step(sensory,
                                                           fault_info=fault_info)
            else:
                target_angles, ctrl_info = controller.step(sensory)

            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"].tolist())
            history["base_velocity"].append(sensory["base_velocity"].tolist())
            history["joint_angles"].append(sensory["joint_angles"].tolist())
            history["target_angles"].append(target_angles.tolist()
                                            if hasattr(target_angles, 'tolist')
                                            else list(target_angles))
            history["joint_velocities"].append(
                sensory["joint_velocities"].tolist())
            history["hormones"].append(
                ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("hormones", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("hormones", [0]*robot.num_joints)))
            history["receptors"].append(
                ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("receptors", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("receptors", [0]*robot.num_joints)))

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(
                applied_torques if isinstance(applied_torques, list)
                else list(applied_torques))

        env.step()

    env.close()

    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=fault_time, sim_duration=duration,
        total_mass=RobotConfig.LINK_MASS * RobotConfig.NUM_SEGMENTS * mass_scale
    )

    if save_history:
        return metrics, history
    return metrics, None


# ═══════════════════════════════════════════════════════════════════
#  Part 1: Full Factorial Benchmark (270 episodes)
# ═══════════════════════════════════════════════════════════════════
def run_benchmark_suite():
    output_path = os.path.join(OUTPUT_DIR, "benchmark_results.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []
    existing_keys = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            for r in results:
                key = (r["controller"], r["fault_type"], r["joint_idx"], r["seed"])
                existing_keys.add(key)
            print(f"  Loaded {len(results)} existing benchmark records.", flush=True)
        except Exception as e:
            print(f"  Could not load existing benchmark file: {e}", flush=True)

    total = (len(PUB_CONTROLLERS) * len(PUB_FAULT_TYPES) *
             len(PUB_FAULT_JOINTS) * PUB_NUM_SEEDS)
    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 1: Full Factorial Benchmark — {total} episodes", flush=True)
    print(f"  Duration={PUB_DURATION}s | Fault@{PUB_FAULT_TIME}s | Seeds={PUB_NUM_SEEDS}", flush=True)
    print(f"{'='*70}\n", flush=True)

    completed = len(existing_keys)
    t0 = time.time()

    for ctrl in PUB_CONTROLLERS:
        for ft in PUB_FAULT_TYPES:
            for jidx in PUB_FAULT_JOINTS:
                for seed_i in range(PUB_NUM_SEEDS):
                    key = (ctrl, ft, jidx, seed_i)
                    if key in existing_keys:
                        continue
                    completed += 1
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
                        record = {
                            "controller": ctrl,
                            "fault_type": ft,
                            "joint_idx": jidx,
                            "seed": seed_i,
                            "metrics": metrics
                        }
                        results.append(record)
                        existing_keys.add(key)
                        eta = (time.time() - t0) / (completed - len(existing_keys) + 1) * (total - completed)
                        print(f"  [{completed:3d}/{total}] {ctrl} | {ft:14s} | J{jidx} | "
                              f"Rv={metrics['recovery_ratio']:.3f} | "
                              f"Trec={metrics['recovery_time']:.1f}s", flush=True)
                    except Exception as e:
                        print(f"  [{completed:3d}/{total}] {ctrl} | FAILED: {e}", flush=True)

                    if completed % 10 == 0:
                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(results, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  Benchmark completed: {len(results)}/{total} episodes in {elapsed:.1f}s\n",
          flush=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved to {output_path}", flush=True)
    return results


# ═══════════════════════════════════════════════════════════════════
#  Part 2: Generalization & Robustness Stress Tests (150 episodes)
# ═══════════════════════════════════════════════════════════════════
def run_generalization_suite():
    output_path = os.path.join(OUTPUT_DIR, "generalization_results.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []
    existing_keys = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            for r in results:
                key = (r["controller"], r["stress_mode"], r["seed"])
                existing_keys.add(key)
            print(f"  Loaded {len(results)} existing generalization records.", flush=True)
        except Exception as e:
            print(f"  Could not load existing generalization file: {e}", flush=True)

    stress_modes = ["intermittent", "slope", "sensor_noise",
                    "mass_perturbation", "multi_joint"]
    total = len(PUB_CONTROLLERS) * len(stress_modes) * PUB_NUM_SEEDS
    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 2: Generalization Stress Tests — {total} episodes", flush=True)
    print(f"{'='*70}\n", flush=True)

    completed = len(existing_keys)
    t0 = time.time()

    for ctrl in PUB_CONTROLLERS:
        for mode in stress_modes:
            for seed_i in range(PUB_NUM_SEEDS):
                key = (ctrl, mode, seed_i)
                if key in existing_keys:
                    continue
                completed += 1
                seed = seed_i * 13 + 5

                kwargs = dict(
                    controller_type=ctrl,
                    fault_type=FaultType.LOCKED,
                    fault_joint_idx=3,
                    fault_time=PUB_FAULT_TIME,
                    duration=PUB_DURATION,
                    seed=seed
                )

                if mode == "intermittent":
                    kwargs["intermittent"] = True
                elif mode == "slope":
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
                    results.append({
                        "controller": ctrl,
                        "stress_mode": mode,
                        "seed": seed_i,
                        "metrics": metrics
                    })
                    existing_keys.add(key)
                    print(f"  [{completed:3d}/{total}] {ctrl} | {mode:18s} | "
                          f"Rv={metrics['recovery_ratio']:.3f}",
                          flush=True)
                except Exception as e:
                    print(f"  [{completed:3d}/{total}] {ctrl} | FAILED: {e}", flush=True)

                if completed % 10 == 0:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  Generalization completed: {len(results)}/{total} in {elapsed:.1f}s\n",
          flush=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved to {output_path}", flush=True)
    return results


# ═══════════════════════════════════════════════════════════════════
#  Part 3: Detail History Runs (6 episodes with full time-series)
# ═══════════════════════════════════════════════════════════════════
def run_detail_histories():
    detail_dir = os.path.join(OUTPUT_DIR, "detail_histories")
    os.makedirs(detail_dir, exist_ok=True)

    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 3: Detail History Runs — 6 episodes (full time-series)", flush=True)
    print(f"{'='*70}\n", flush=True)

    for ctrl in PUB_CONTROLLERS:
        t0 = time.time()
        metrics, history = run_episode(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            fault_joint_idx=3,
            fault_time=PUB_FAULT_TIME,
            duration=PUB_DURATION,
            seed=42,
            save_history=True
        )
        elapsed = time.time() - t0

        fname = f"{ctrl.lower()}_locked_j3.json"
        fpath = os.path.join(detail_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"history": history, "metrics": metrics}, f)

        print(f"  {ctrl}: Rv={metrics['recovery_ratio']:.3f} | "
              f"Trec={metrics['recovery_time']:.1f}s | {elapsed:.1f}s | "
              f"Saved {fname}", flush=True)

    print(f"\n  Detail histories saved to {detail_dir}/", flush=True)


# ═══════════════════════════════════════════════════════════════════
#  Main Execution
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("  PUBLICATION-QUALITY EXPERIMENT SUITE", flush=True)
    print("  Snake Robot AHM-CPG Failure Recovery", flush=True)
    print("=" * 70, flush=True)

    t_global = time.time()

    # Phase 1: Benchmark
    run_benchmark_suite()

    # Phase 2: Generalization
    run_generalization_suite()

    # Phase 3: Detail Histories
    run_detail_histories()

    total_time = time.time() - t_global
    print(f"\n{'='*70}", flush=True)
    print(f"  ALL EXPERIMENTS COMPLETE — Total time: {total_time:.1f}s "
          f"({total_time/60:.1f} min)", flush=True)
    print(f"{'='*70}", flush=True)
