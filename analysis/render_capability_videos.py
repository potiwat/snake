"""Render actual PyBullet clips for frozen Snake Hermes protocols.

Each clip is one deterministic representative (C5, joint 3, seed 7).
It is visualization-only; inferential evidence remains in paired statistics.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.run_single import run_single_episode
from simulation.environments import EnvironmentType
from simulation.snake_robot import FaultType

OUTPUT_DIR = Path("results/capability_visuals/videos")
CONTROLLER = "C5"
FAULTS = (FaultType.LOCKED, FaultType.FREE, FaultType.PARTIAL_TORQUE)
PROTOCOLS = (
    ("flat", EnvironmentType.FLAT, 0.0, "results/paired_capability_benchmark.json"),
    ("low_friction", EnvironmentType.LOW_FRICTION, 0.0, "results/paired_capability_robustness_slope10.json"),
    ("variable_friction", EnvironmentType.VARIABLE_FRICTION, 0.0, "results/paired_capability_robustness_slope10.json"),
    ("incline10", EnvironmentType.INCLINE, 10.0, "results/paired_capability_robustness_slope10.json"),
)


def _benchmark_metrics(path: Path, environment: str, fault: str | None):
    """Read the frozen C5/joint-3/seed-7 result for this visualized case."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        if (
            record["controller"] == CONTROLLER
            and record["environment"] == environment
            and record["fault_joint"] == 3
            and record["seed"] == 7
            and (fault is None or record["fault"] == fault)
        ):
            return record["healthy_metrics"] if fault is None else record["fault_metrics"]
    raise LookupError(f"No frozen benchmark record for {environment=}, {fault=}")


def render_protocol(label, environment, incline_deg, benchmark_path, output_root=OUTPUT_DIR):
    """Render healthy plus all fault clips and preserve rerun/benchmark metadata."""
    output_dir = Path(output_root) / label
    output_dir.mkdir(parents=True, exist_ok=True)
    conditions = ((FaultType.NONE, "healthy"),) + tuple((fault, fault) for fault in FAULTS)
    manifest = {
        "label": "visualization-only deterministic representative PyBullet episodes; not statistical evidence",
        "protocol": {
            "controller": CONTROLLER,
            "environment": environment,
            "incline_deg": incline_deg,
            "fault_joint": 3,
            "seed": 7,
            "fault_time": 4.0,
            "duration": 10.0,
            "record_fps": 30,
        },
        "benchmark_source": str(benchmark_path),
        "videos": [],
    }
    for fault, name in conditions:
        output = output_dir / f"c5_{label}_{name}_joint3_seed7.mp4"
        _, rerun_metrics = run_single_episode(
            controller_type=CONTROLLER,
            fault_type=fault,
            fault_joint_idx=3,
            fault_time=4.0,
            duration=10.0,
            gui=False,
            env_type=environment,
            incline_deg=incline_deg,
            seed=7,
            record_video=True,
            video_filepath=str(output),
        )
        benchmark_metrics = _benchmark_metrics(
            Path(benchmark_path), environment, None if fault == FaultType.NONE else fault
        )
        manifest["videos"].append(
            {
                "condition": name,
                "path": str(output),
                "rerun_metrics": rerun_metrics,
                "frozen_benchmark_metrics": benchmark_metrics,
            }
        )
        print(f"saved {output}")
    manifest_path = output_dir / "representative_video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"saved {manifest_path}")
    return manifest_path


def main():
    for protocol in PROTOCOLS:
        render_protocol(*protocol)


if __name__ == "__main__":
    main()
