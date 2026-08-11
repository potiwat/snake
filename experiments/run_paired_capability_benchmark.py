"""Paired healthy-versus-fault capability benchmark.

This is an execution protocol, not a confirmatory statistical analysis. Every
fault episode is paired with a healthy episode using the same controller,
environment, fault-joint configuration, and seed.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType


@dataclass(frozen=True)
class BenchmarkProtocol:
    controllers: tuple[str, ...] = ("C1", "C2", "C3", "C4", "C5", "C6")
    environments: tuple[str, ...] = (EnvironmentType.FLAT,)
    faults: tuple[str, ...] = (
        FaultType.LOCKED,
        FaultType.FREE,
        FaultType.PARTIAL_TORQUE,
    )
    fault_joints: tuple[int, ...] = (1, 3, 5)
    seeds: tuple[int, ...] = (7, 26)
    fault_time: float = 4.0
    duration: float = 10.0
    partial_torque_gamma: float = 0.3
    incline_deg: float = 10.0


def _metric_subset(metrics: dict[str, Any]) -> dict[str, float | bool]:
    keys = (
        "v_pre",
        "v_post",
        "forward_progress",
        "lateral_drift",
        "stall_fraction",
        "heading_deviation_deg",
        "performance_loss_auc",
        "total_energy",
        "cost_of_transport",
        "shape_error",
        "distance_traveled",
        "survival",
        "survival_fraction",
        "fall_fraction",
        "torque_saturation_fraction",
        "locked_joint_drift_max_rad",
        "locked_joint_drift_rms_rad",
        "locked_joint_drift_within_tolerance",
        "locked_joint_drift_steady_max_rad",
        "locked_joint_drift_steady_within_tolerance",
    )
    result = {
        key: (None if metrics.get(key) is None else float(metrics[key]))
        for key in keys
        if key not in (
            "survival",
            "locked_joint_drift_within_tolerance",
            "locked_joint_drift_steady_within_tolerance",
        )
    }
    result["survival"] = bool(metrics["survival"])
    result["locked_joint_drift_within_tolerance"] = (
        None if metrics.get("locked_joint_drift_within_tolerance") is None
        else bool(metrics["locked_joint_drift_within_tolerance"])
    )
    result["locked_joint_drift_steady_within_tolerance"] = (
        None if metrics.get("locked_joint_drift_steady_within_tolerance") is None
        else bool(metrics["locked_joint_drift_steady_within_tolerance"])
    )
    return result


def _run_episode(
    controller: str,
    environment: str,
    fault: str,
    fault_joint: int,
    seed: int,
    protocol: BenchmarkProtocol,
) -> dict[str, Any]:
    incline_deg = protocol.incline_deg if environment == EnvironmentType.INCLINE else 0.0
    _, metrics = run_single_episode(
        controller_type=controller,
        fault_type=fault,
        fault_joint_idx=fault_joint,
        fault_time=protocol.fault_time,
        duration=protocol.duration,
        gui=False,
        env_type=environment,
        incline_deg=incline_deg,
        seed=seed,
    )
    return _metric_subset(metrics)


def _run_pair_task(task: tuple[int, str, str, int, int, BenchmarkProtocol]) -> tuple[int, list[dict[str, Any]]]:
    """Run one matched healthy reference and all its fault episodes in one process."""
    index, controller, environment, fault_joint, seed, protocol = task
    healthy = _run_episode(controller, environment, FaultType.NONE, fault_joint, seed, protocol)
    records = []
    for fault in protocol.faults:
        fault_metrics = _run_episode(controller, environment, fault, fault_joint, seed, protocol)
        records.append(
            {
                "controller": controller,
                "environment": environment,
                "fault": fault,
                "fault_joint": fault_joint,
                "seed": seed,
                "healthy_metrics": healthy,
                "fault_metrics": fault_metrics,
                "paired_delta": _delta(fault_metrics, healthy),
            }
        )
    return index, records


def resolve_worker_count(requested: int | None, task_count: int, available_cpus: int | None = None) -> int:
    """Choose a bounded worker count; zero/None means automatic (at most four)."""
    if task_count < 1:
        raise ValueError("task_count must be positive")
    if requested is not None and requested < 0:
        raise ValueError("workers must be non-negative")
    if requested in (None, 0):
        return min(4, available_cpus or os.cpu_count() or 1, task_count)
    return min(requested, task_count)


def _delta(fault_metrics: dict[str, float], healthy_metrics: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key in (
        "forward_progress",
        "lateral_drift",
        "stall_fraction",
        "heading_deviation_deg",
        "performance_loss_auc",
        "cost_of_transport",
        "fall_fraction",
        "torque_saturation_fraction",
        "survival",
    ):
        result[f"{key}_delta"] = float(fault_metrics[key]) - float(healthy_metrics[key])
    healthy_progress = healthy_metrics["forward_progress"]
    result["forward_progress_retention"] = (
        fault_metrics["forward_progress"] / healthy_progress
        if healthy_progress > 1e-9
        else None
    )
    return result


def run_paired_benchmark(
    protocol: BenchmarkProtocol | None = None,
    output_path: str | Path = "results/paired_capability_benchmark.json",
    workers: int | None = 1,
) -> list[dict[str, Any]]:
    protocol = protocol or BenchmarkProtocol()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tasks = [
        (index, controller, environment, fault_joint, seed, protocol)
        for index, (controller, environment, fault_joint, seed) in enumerate(
            (
                (controller, environment, fault_joint, seed)
                for controller in protocol.controllers
                for environment in protocol.environments
                for fault_joint in protocol.fault_joints
                for seed in protocol.seeds
            )
        )
    ]
    worker_count = resolve_worker_count(workers, len(tasks))
    records: list[dict[str, Any]] = []
    total = (
        len(protocol.controllers)
        * len(protocol.environments)
        * len(protocol.faults)
        * len(protocol.fault_joints)
        * len(protocol.seeds)
    )
    completed = 0
    started = time.perf_counter()

    if worker_count == 1:
        task_results = map(_run_pair_task, tasks)
        start_method = "serial"
    else:
        context = mp.get_context("spawn")
        executor = ProcessPoolExecutor(max_workers=worker_count, mp_context=context)
        task_results = executor.map(_run_pair_task, tasks)
        start_method = context.get_start_method()
    try:
        for _, pair_records in task_results:
            records.extend(pair_records)
            for record in pair_records:
                completed += 1
                print(
                    f"[{completed}/{total}] {record['controller']} | {record['environment']} | "
                    f"{record['fault']} | joint={record['fault_joint']} | seed={record['seed']}",
                    flush=True,
                )
    finally:
        if worker_count > 1:
            executor.shutdown(wait=True, cancel_futures=True)

    payload = {
        "protocol": asdict(protocol),
        "records": records,
        "execution": {
            "record_count": len(records),
            "elapsed_seconds": time.perf_counter() - started,
            "workers": worker_count,
            "multiprocessing_start_method": start_method,
            "analysis_status": "raw paired benchmark; no confirmatory inference",
        },
    }
    output_path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(f"saved {output_path}", flush=True)
    print(f"records={len(records)}", flush=True)
    return records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/paired_capability_benchmark.json")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--fault-time", type=float, default=4.0)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 26])
    parser.add_argument(
        "--environments", nargs="+",
        default=[EnvironmentType.FLAT],
        choices=[
            EnvironmentType.FLAT,
            EnvironmentType.LOW_FRICTION,
            EnvironmentType.VARIABLE_FRICTION,
            EnvironmentType.INCLINE,
        ],
        help="environment modes to benchmark",
    )
    parser.add_argument(
        "--workers", type=int, default=0,
        help="processes (0=automatic, bounded to 4; 1=serial)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    protocol = BenchmarkProtocol(
        environments=tuple(args.environments),
        seeds=tuple(args.seeds), duration=args.duration, fault_time=args.fault_time
    )
    run_paired_benchmark(protocol, args.output, workers=args.workers)


if __name__ == "__main__":
    main()
