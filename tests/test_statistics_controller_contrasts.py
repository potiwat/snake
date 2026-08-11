import json
import os
from pathlib import Path
import subprocess

import pytest

from analysis.statistics_controller_contrasts import analyze


def _record(controller: str, fault: str, joint: int, seed: int, value: float) -> dict:
    return {
        "controller": controller,
        "environment": "flat",
        "fault": fault,
        "fault_joint": joint,
        "seed": seed,
        "paired_delta": {"forward_progress_delta": value},
    }


def test_controller_contrast_analysis_pairs_proposed_and_control_by_joint_seed():
    payload = {
        "protocol": {"seeds": [101, 102]},
        "records": [
            _record(controller, fault, joint, seed, value)
            for controller, value in (("C5", -0.1), ("C1", -0.5))
            for fault in ("locked", "free", "partial_torque")
            for joint in (1, 3)
            for seed in (101, 102)
        ],
    }

    result = analyze(
        payload,
        proposed_controller="C5",
        control_controllers=("C1",),
        n_permutations=100,
        n_bootstrap=100,
    )

    assert result["n_tests"] == 3
    assert result["alpha_bonferroni"] == 0.05 / 3
    assert all(test["n"] == 4 for test in result["tests"])
    assert all(test["mean_difference"] == pytest.approx(0.4) for test in result["tests"])


def test_controller_contrast_analysis_rejects_missing_matched_control_record():
    payload = {
        "records": [_record("C5", "locked", 1, 101, -0.1)],
    }

    with pytest.raises(ValueError, match="missing matched record"):
        analyze(
            payload,
            proposed_controller="C5",
            control_controllers=("C1",),
            n_permutations=10,
            n_bootstrap=10,
        )


def test_controller_contrast_cli_runs_from_project_root(tmp_path):
    payload = {
        "records": [
            _record(controller, fault, 1, 101, value)
            for controller, value in (("C5", -0.1), ("C1", -0.5))
            for fault in ("locked", "free", "partial_torque")
        ],
    }
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    project = Path(__file__).resolve().parent.parent

    completed = subprocess.run(
        [
            "python3", "analysis/statistics_controller_contrasts.py",
            "--input", str(input_path), "--output", str(output_path),
            "--controls", "C1", "--permutations", "10", "--bootstrap", "10",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output_path.read_text(encoding="utf-8"))["n_tests"] == 3
