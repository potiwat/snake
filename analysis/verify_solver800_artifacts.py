"""Verify the frozen solver-800 Snake Hermes artifact chain.

This verifier checks recorded artifacts only. It does not treat the two-seed
benchmark as publication-level evidence and does not rerun simulation episodes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path("results")
VISUALS = ROOT / "capability_visuals"
VIDEO_ROOT = VISUALS / "videos_solver800"
ENVIRONMENTS = ("flat", "low_friction", "variable_friction", "incline10")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_records(path: Path, expected_count: int, expected_environments: set[str]) -> None:
    payload = _json(path)
    records = payload["records"]
    assert len(records) == expected_count, (path, len(records))
    assert {record["environment"] for record in records} == expected_environments
    keys = [
        (record["controller"], record["environment"], record["fault"], record["fault_joint"], record["seed"])
        for record in records
    ]
    assert len(keys) == len(set(keys))
    locked = [record["fault_metrics"] for record in records if record["fault"] == "locked"]
    assert locked
    assert all(metrics["locked_joint_drift_within_tolerance"] is True for metrics in locked)
    assert all(metrics["locked_joint_drift_steady_within_tolerance"] is True for metrics in locked)


def _verify_statistics(path: Path, expected_tests: int) -> None:
    payload = _json(path)
    assert payload["n_tests"] == expected_tests
    assert len(payload["tests"]) == expected_tests
    assert all("bootstrap_ci_95" in test and "permutation_p" in test for test in payload["tests"])


def _probe_video(path: Path) -> None:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-show_entries", "format=duration", "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    stream = payload["streams"][0]
    assert (stream["width"], stream["height"], stream["r_frame_rate"], stream["nb_frames"]) == (640, 480, "30/1", "300")
    assert abs(float(payload["format"]["duration"]) - 10.0) < 1e-6


def _verify_videos() -> int:
    clips = 0
    for environment in ENVIRONMENTS:
        manifest = _json(VIDEO_ROOT / environment / "representative_video_manifest.json")
        assert manifest["protocol"]["record_fps"] == 30
        assert len(manifest["videos"]) == 4
        for entry in manifest["videos"]:
            assert all(entry["rerun_metrics"][key] == value for key, value in entry["frozen_benchmark_metrics"].items())
            _probe_video(Path(entry["path"]))
            clips += 1
    return clips


def _verify_contact_sheets() -> None:
    for environment in ENVIRONMENTS:
        path = VISUALS / f"{environment}_solver800_video_contact_sheet.png"
        with Image.open(path) as image:
            assert image.size == (1920, 2070)
            assert image.getbbox() == (0, 0, 1920, 2070)


def main() -> None:
    _verify_records(ROOT / "paired_capability_benchmark_solver800.json", 108, {"flat"})
    _verify_records(
        ROOT / "paired_capability_robustness_solver800_v2.json",
        324,
        {"low_friction", "variable_friction", "incline"},
    )
    _verify_statistics(ROOT / "paired_capability_statistics_solver800.json", 21)
    _verify_statistics(ROOT / "paired_capability_robustness_solver800_v2_statistics.json", 63)
    clips = _verify_videos()
    _verify_contact_sheets()
    print(f"SOLVER800_ARTIFACT_CHAIN_PASS flat_records=108 robustness_records=324 clips={clips} contact_sheets=4")


if __name__ == "__main__":
    main()
