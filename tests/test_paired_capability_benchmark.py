from pathlib import Path

from experiments import run_paired_capability_benchmark as benchmark


def test_delta_uses_matched_healthy_reference():
    healthy = {
        "forward_progress": 2.0,
        "lateral_drift": 1.0,
        "stall_fraction": 0.1,
        "heading_deviation_deg": 5.0,
        "performance_loss_auc": 0.0,
        "cost_of_transport": 0.2,
        "fall_fraction": 0.0,
        "torque_saturation_fraction": 0.2,
        "survival": True,
    }
    fault = {key: value for key, value in healthy.items()}
    fault.update(forward_progress=1.0, lateral_drift=2.5, stall_fraction=0.4)

    delta = benchmark._delta(fault, healthy)

    assert delta["forward_progress_delta"] == -1.0
    assert delta["lateral_drift_delta"] == 1.5
    assert delta["stall_fraction_delta"] == 0.30000000000000004
    assert delta["forward_progress_retention"] == 0.5


def test_zero_healthy_progress_has_explicit_missing_retention():
    healthy = {
        "forward_progress": 0.0,
        "lateral_drift": 0.0,
        "stall_fraction": 1.0,
        "heading_deviation_deg": 90.0,
        "performance_loss_auc": 1.0,
        "cost_of_transport": 0.0,
        "fall_fraction": 0.0,
        "torque_saturation_fraction": 0.0,
        "survival": True,
    }
    assert benchmark._delta(healthy, healthy)["forward_progress_retention"] is None


def test_runner_creates_one_record_per_fault_and_preserves_pairing(monkeypatch, tmp_path: Path):
    calls = []

    def fake_run(controller, environment, fault, fault_joint, seed, protocol):
        calls.append((controller, environment, fault, fault_joint, seed))
        return {
            "v_pre": 1.0,
            "v_post": 1.0 if fault == benchmark.FaultType.NONE else 0.5,
            "forward_progress": 2.0 if fault == benchmark.FaultType.NONE else 1.0,
            "lateral_drift": 0.1,
            "stall_fraction": 0.1,
            "heading_deviation_deg": 2.0,
            "performance_loss_auc": 0.0,
            "total_energy": 1.0,
            "cost_of_transport": 0.1,
            "shape_error": 0.0,
            "distance_traveled": 2.0,
            "survival": True,
            "survival_fraction": 1.0,
            "fall_fraction": 0.0,
            "torque_saturation_fraction": 0.5,
        }

    monkeypatch.setattr(benchmark, "_run_episode", fake_run)
    protocol = benchmark.BenchmarkProtocol(
        controllers=("C1",),
        environments=(benchmark.EnvironmentType.FLAT,),
        faults=(benchmark.FaultType.LOCKED, benchmark.FaultType.FREE),
        fault_joints=(3,),
        seeds=(7,),
    )
    output = tmp_path / "paired.json"

    records = benchmark.run_paired_benchmark(protocol, output, workers=1)

    assert len(records) == 2
    assert output.is_file()
    assert len(calls) == 3
    assert calls[0][2] == benchmark.FaultType.NONE
    assert all(call[0:2] == ("C1", benchmark.EnvironmentType.FLAT) for call in calls)
    assert all(record["paired_delta"]["forward_progress_retention"] == 0.5 for record in records)


def test_worker_count_is_bounded_and_explicit():
    assert benchmark.resolve_worker_count(0, task_count=10, available_cpus=16) == 4
    assert benchmark.resolve_worker_count(6, task_count=2, available_cpus=16) == 2
    assert benchmark.resolve_worker_count(1, task_count=10, available_cpus=16) == 1
