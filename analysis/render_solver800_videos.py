"""Render representative solver-800 videos without overwriting pre-repair artifacts."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.render_capability_videos import render_protocol
from simulation.environments import EnvironmentType


OUTPUT_ROOT = Path("results/capability_visuals/videos_solver800")


def main():
    render_protocol(
        "flat",
        EnvironmentType.FLAT,
        0.0,
        Path("results/paired_capability_benchmark_solver800.json"),
        output_root=OUTPUT_ROOT,
    )
    for label, environment in (
        ("low_friction", EnvironmentType.LOW_FRICTION),
        ("variable_friction", EnvironmentType.VARIABLE_FRICTION),
        ("incline10", EnvironmentType.INCLINE),
    ):
        render_protocol(
            label,
            environment,
            10.0 if environment == EnvironmentType.INCLINE else 0.0,
            Path("results/paired_capability_robustness_solver800_v2.json"),
            output_root=OUTPUT_ROOT,
        )


if __name__ == "__main__":
    main()
