"""
Publication-Quality Master Experiment Runner.
Runs all experiments needed for a peer-reviewed journal paper:
  1. Full Factorial Benchmark (480 episodes: 6 controllers x 8 fault scenarios x 10 seeds)
  2. Generalization & Robustness Stress Tests (420 episodes: 6 controllers x 7 stress modes x 10 seeds)
  3. Detail Single-Episode Histories for Time-Series Figures (18 episodes)

All results are saved to results/publication/data/.
"""

import sys
import os
import json
import time
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
PUB_DURATION = SimConfig.DEFAULT_DURATION          # 60 seconds per episode
PUB_FAULT_TIME = SimConfig.DEFAULT_FAULT_TIME        # Fault injected at t=18s
NUM_SEEDS_BENCHMARK = 10                            # 10 seeds per condition
NUM_SEEDS_GENERALIZATION = 10                       # 10 seeds per condition
PUB_CONTROLLERS = ["C1", "C2", "C3", "C4", "C5", "C6"]

BENCHMARK_SCENARIOS = [
    {"name": "locked_0rad_head", "fault_type": FaultType.LOCKED, "joints": [1], "params": {"locked_angle": 0.0}},
    {"name": "locked_0rad_mid", "fault_type": FaultType.LOCKED, "joints": [3], "params": {"locked_angle": 0.0}},
    {"name": "locked_0rad_tail", "fault_type": FaultType.LOCKED, "joints": [7], "params": {"locked_angle": 0.0}},
    {"name": "locked_offset_mid", "fault_type": FaultType.LOCKED, "joints": [3], "params": {"locked_angle": 0.2618}},
    {"name": "limp_mid", "fault_type": FaultType.FREE, "joints": [3], "params": {}},
    {"name": "dual_consecutive_j3_j4", "fault_type": FaultType.LOCKED, "joints": [3, 4], "params": {"locked_angle": 0.0}},
    {"name": "dual_nonconsecutive_j2_j5", "fault_type": FaultType.LOCKED, "joints": [2, 5], "params": {"locked_angle": 0.0}},
    {"name": "partial_torque_mid", "fault_type": FaultType.PARTIAL_TORQUE, "joints": [3], "params": {"gamma_f": 0.3}}
]

GENERALIZATION_MODES = [
    "intermittent",
    "incline_10deg",
    "sensor_noise",
    "mass_perturbation",
    "high_slip",
    "low_friction",
    "dynamic_friction"
]

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


def run_episode(
    controller_type,
    fault_type=FaultType.LOCKED,
    fault_joint_idx=3,
    fault_time=PUB_FAULT_TIME,
    duration=PUB_DURATION,
    seed=42,
    env_type=EnvironmentType.FLAT,
    incline_deg=0.0,
    mass_scale=1.0,
    sensor_noise_std=0.0,
    intermittent=False,
    multi_joint_faults=None,
    fault_params=None,
    transition_time=30.0,
    target_transition_env=EnvironmentType.HIGH_SLIP,
    save_history=False
):
    """
    Run a single simulation episode with full parameter control.
    Returns (metrics_dict, history_dict_or_None).
    """
    np.random.seed(seed)

    env = SimulationEnvironment(
        gui=False,
        env_type=env_type,
        incline_deg=incline_deg,
        transition_time=transition_time,
        target_transition_env=target_transition_env
    )
    robot = SnakeRobot(physics_client=env.physics_client)

    # ── Stochastic Variation for Seed Diversity ──
    # (a) Initial joint pose perturbation (±2° ≈ ±0.035 rad)
    init_noise = np.random.uniform(-0.035, 0.035, robot.num_joints)
    for j in range(robot.num_joints):
        p.resetJointState(
            robot.robot_id, j,
            targetValue=init_noise[j],
            targetVelocity=0.0,
            physicsClientId=env.physics_client
        )

    # (b) Per-link friction perturbation (±10%)
    friction_scale = 1.0 + np.random.uniform(-0.10, 0.10)
    for link_idx in range(-1, robot.num_joints):
        p.changeDynamics(
            robot.robot_id, link_idx,
            lateralFriction=SimConfig.LATERAL_FRICTION * friction_scale,
            anisotropicFriction=[
                SimConfig.FORWARD_FRICTION * friction_scale,
                SimConfig.SIDEWAYS_FRICTION * friction_scale,
                0.01
            ],
            physicsClientId=env.physics_client
        )

    # (c) Fault timing jitter (±0.5s)
    fault_time_jitter = np.random.uniform(-0.5, 0.5)
    fault_time_actual = max(1.0, fault_time + fault_time_jitter)

    # (d) Mass micro-perturbation (±3%)
    mass_noise_scale = 1.0 + np.random.uniform(-0.03, 0.03)
    if mass_scale != 1.0 or mass_noise_scale != 1.0:
        combined_mass_scale = mass_scale * mass_noise_scale
        new_mass = RobotConfig.LINK_MASS * combined_mass_scale
        for link_idx in range(-1, robot.num_joints):
            p.changeDynamics(
                robot.robot_id, link_idx,
                mass=new_mass,
                physicsClientId=env.physics_client
            )

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
    next_toggle_time = fault_time_actual

    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP

        # ── Dynamic Environmental Transition Check ──
        env.check_and_apply_transition(current_time, robot=robot)

        # ── Fault Injection Logic (uses jittered fault_time_actual) ──
        if current_time >= fault_time_actual:
            if intermittent:
                if current_time >= next_toggle_time:
                    intermittent_state = not intermittent_state
                    next_toggle_time = current_time + np.random.uniform(1.5, 3.0)
                    if intermittent_state:
                        robot.inject_fault(joint_idx=fault_joint_idx, fault_type=fault_type, params=fault_params)
                    else:
                        robot.clear_faults()
            elif multi_joint_faults is not None:
                if not fault_injected:
                    robot.inject_faults(multi_joint_faults)
                    fault_injected = True
            elif not fault_injected and fault_type != FaultType.NONE:
                fparams = dict(fault_params or {})
                if fault_type == FaultType.PARTIAL_TORQUE and "gamma_f" not in fparams:
                    fparams["gamma_f"] = 0.3
                robot.inject_fault(joint_idx=fault_joint_idx, fault_type=fault_type, params=fparams)
                fault_injected = True

        # ── Sensory Feedback ──
        sensory = robot.get_sensory_feedback()

        if sensor_noise_std > 0.0:
            sensory["joint_angles"] = sensory["joint_angles"] + np.random.normal(
                0, sensor_noise_std, robot.num_joints
            )

        # ── Control Loop ──
        if step % ctrl_substeps == 0:
            if controller_type in ["C4", "oracle"]:
                fault_info = {
                    "active": robot.fault_active,
                    "joint_idx": robot.fault_joint_idx,
                    "active_faults": robot.active_faults
                }
                target_angles, ctrl_info = controller.step(sensory, fault_info=fault_info)
            else:
                target_angles, ctrl_info = controller.step(sensory)

            history["time"].append(current_time)
            history["base_position"].append(sensory["base_position"].tolist())
            history["base_velocity"].append(sensory["base_velocity"].tolist())
            history["joint_angles"].append(sensory["joint_angles"].tolist())
            history["target_angles"].append(
                target_angles.tolist() if hasattr(target_angles, 'tolist') else list(target_angles)
            )
            history["joint_velocities"].append(sensory["joint_velocities"].tolist())
            history["hormones"].append(
                ctrl_info.get("hormones", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("hormones", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("hormones", [0] * robot.num_joints))
            )
            history["receptors"].append(
                ctrl_info.get("receptors", np.zeros(robot.num_joints)).tolist()
                if hasattr(ctrl_info.get("receptors", np.zeros(robot.num_joints)), 'tolist')
                else list(ctrl_info.get("receptors", [0] * robot.num_joints))
            )

        applied_torques = robot.apply_joint_commands(target_angles)
        if step % ctrl_substeps == 0:
            history["joint_torques"].append(
                applied_torques if isinstance(applied_torques, list) else list(applied_torques)
            )

        env.step()

    env.close()

    actual_total_mass = RobotConfig.LINK_MASS * RobotConfig.NUM_SEGMENTS * mass_scale * mass_noise_scale
    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=fault_time_actual, sim_duration=duration,
        total_mass=actual_total_mass
    )

    if save_history:
        return metrics, history
    return metrics, None


# ═══════════════════════════════════════════════════════════════════
#  Part 1: Full Factorial Benchmark (480 episodes)
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
                key = (r["controller"], r.get("fault_scenario", f"{r['fault_type']}_j{r['joint_idx']}"), r["seed"])
                existing_keys.add(key)
            print(f"  Loaded {len(results)} existing benchmark records.", flush=True)
        except Exception as e:
            print(f"  Could not load existing benchmark file: {e}", flush=True)

    total = len(PUB_CONTROLLERS) * len(BENCHMARK_SCENARIOS) * NUM_SEEDS_BENCHMARK
    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 1: Full Factorial Benchmark — {total} episodes", flush=True)
    print(f"  Duration={PUB_DURATION}s | Fault@{PUB_FAULT_TIME}s | Seeds={NUM_SEEDS_BENCHMARK}", flush=True)
    print(f"{'='*70}\n", flush=True)

    completed = len(existing_keys)
    t0 = time.time()

    for ctrl in PUB_CONTROLLERS:
        for scen in BENCHMARK_SCENARIOS:
            for seed_i in range(NUM_SEEDS_BENCHMARK):
                key = (ctrl, scen["name"], seed_i)
                if key in existing_keys:
                    continue
                completed += 1
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
                    record = {
                        "controller": ctrl,
                        "fault_type": scen["fault_type"],
                        "joint_idx": scen["joints"][0],
                        "fault_scenario": scen["name"],
                        "joints": scen["joints"],
                        "seed": seed_i,
                        "metrics": metrics
                    }
                    results.append(record)
                    existing_keys.add(key)
                    print(f"  [{completed:3d}/{total}] {ctrl} | {scen['name']:26s} | seed {seed_i:2d} | "
                          f"Rv={metrics['recovery_ratio']:.3f} | "
                          f"COT={metrics['cost_of_transport']:.2f}", flush=True)
                except Exception as e:
                    print(f"  [{completed:3d}/{total}] {ctrl} | {scen['name']} | FAILED: {e}", flush=True)

                if completed % 10 == 0:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  Benchmark completed: {len(results)}/{total} episodes in {elapsed:.1f}s\n", flush=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved to {output_path}", flush=True)
    return results


# ═══════════════════════════════════════════════════════════════════
#  Part 2: Generalization & Robustness Stress Tests (420 episodes)
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

    total = len(PUB_CONTROLLERS) * len(GENERALIZATION_MODES) * NUM_SEEDS_GENERALIZATION
    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 2: Generalization Stress Tests — {total} episodes", flush=True)
    print(f"{'='*70}\n", flush=True)

    completed = len(existing_keys)
    t0 = time.time()

    for ctrl in PUB_CONTROLLERS:
        for mode in GENERALIZATION_MODES:
            for seed_i in range(NUM_SEEDS_GENERALIZATION):
                key = (ctrl, mode, seed_i)
                if key in existing_keys:
                    continue
                completed += 1
                seed = seed_i * 13 + 5

                kwargs = dict(
                    controller_type=ctrl,
                    fault_type=FaultType.LOCKED,
                    fault_joint_idx=3,
                    fault_params={"locked_angle": 0.0},
                    fault_time=PUB_FAULT_TIME,
                    duration=PUB_DURATION,
                    seed=seed
                )

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
                    results.append({
                        "controller": ctrl,
                        "stress_mode": mode,
                        "seed": seed_i,
                        "metrics": metrics
                    })
                    existing_keys.add(key)
                    print(f"  [{completed:3d}/{total}] {ctrl} | {mode:20s} | seed {seed_i:2d} | "
                          f"Rv={metrics['recovery_ratio']:.3f}", flush=True)
                except Exception as e:
                    print(f"  [{completed:3d}/{total}] {ctrl} | {mode} | FAILED: {e}", flush=True)

                if completed % 10 == 0:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  Generalization completed: {len(results)}/{total} in {elapsed:.1f}s\n", flush=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved to {output_path}", flush=True)
    return results


# ═══════════════════════════════════════════════════════════════════
#  Part 3: Detail History Runs (18 episodes with full time-series)
# ═══════════════════════════════════════════════════════════════════
def run_detail_histories():
    detail_dir = os.path.join(OUTPUT_DIR, "detail_histories")
    os.makedirs(detail_dir, exist_ok=True)

    print(f"\n{'='*70}", flush=True)
    print(f"  PHASE 3: Detail History Runs — 18 episodes (full time-series)", flush=True)
    print(f"{'='*70}\n", flush=True)

    for ctrl in PUB_CONTROLLERS:
        # 1. Locked Joint 3
        t0 = time.time()
        m1, h1 = run_episode(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            fault_joint_idx=3,
            fault_params={"locked_angle": 0.0},
            fault_time=PUB_FAULT_TIME,
            duration=PUB_DURATION,
            seed=42,
            save_history=True
        )
        fname1 = f"{ctrl.lower()}_locked_j3.json"
        with open(os.path.join(detail_dir, fname1), "w", encoding="utf-8") as f:
            json.dump({"history": h1, "metrics": m1}, f)
        print(f"  {ctrl} [locked_j3]: Rv={m1['recovery_ratio']:.3f} in {time.time() - t0:.1f}s", flush=True)

        # 2. Dynamic Friction Transition
        t0 = time.time()
        m2, h2 = run_episode(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            fault_joint_idx=3,
            fault_params={"locked_angle": 0.0},
            fault_time=PUB_FAULT_TIME,
            duration=PUB_DURATION,
            seed=42,
            env_type=EnvironmentType.VARIABLE_FRICTION,
            transition_time=30.0,
            target_transition_env=EnvironmentType.HIGH_SLIP,
            save_history=True
        )
        fname2 = f"{ctrl.lower()}_dynamic_friction.json"
        with open(os.path.join(detail_dir, fname2), "w", encoding="utf-8") as f:
            json.dump({"history": h2, "metrics": m2}, f)
        print(f"  {ctrl} [dynamic_friction]: Rv={m2['recovery_ratio']:.3f} in {time.time() - t0:.1f}s", flush=True)

        # 3. Dual Locked J3+J4
        t0 = time.time()
        m3, h3 = run_episode(
            controller_type=ctrl,
            fault_type=FaultType.LOCKED,
            multi_joint_faults=[(3, FaultType.LOCKED, {"locked_angle": 0.0}), (4, FaultType.LOCKED, {"locked_angle": 0.0})],
            fault_time=PUB_FAULT_TIME,
            duration=PUB_DURATION,
            seed=42,
            save_history=True
        )
        fname3 = f"{ctrl.lower()}_dual_locked_j3_j4.json"
        with open(os.path.join(detail_dir, fname3), "w", encoding="utf-8") as f:
            json.dump({"history": h3, "metrics": m3}, f)
        print(f"  {ctrl} [dual_j3_j4]: Rv={m3['recovery_ratio']:.3f} in {time.time() - t0:.1f}s", flush=True)

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
    print(f"  ALL EXPERIMENTS COMPLETE — Total time: {total_time:.1f}s ({total_time/60:.1f} min)", flush=True)
    print(f"{'='*70}", flush=True)

