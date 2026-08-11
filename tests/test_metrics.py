import numpy as np

from analysis.metrics import LocomotionMetrics


def make_history(velocity):
    velocity = np.asarray(velocity, dtype=float)
    n = len(velocity)
    base_position = np.cumsum(velocity, axis=0)
    base_position[:, 2] = 0.05
    return {
        "time": np.arange(n, dtype=float),
        "base_position": base_position,
        "base_velocity": velocity,
        "base_orientation": np.tile([0.0, 0.0, 0.0, 1.0], (n, 1)),
        "joint_angles": np.zeros((n, 8)),
        "target_angles": np.zeros((n, 8)),
        "joint_torques": np.zeros((n, 8)),
        "joint_velocities": np.zeros((n, 8)),
    }


def test_survival_and_torque_saturation_are_reported():
    velocity = np.tile([0.0, -0.2, 0.0], (10, 1))
    history = make_history(velocity)
    history["joint_torques"][:5] = 8.0
    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=5.0, sim_duration=10.0
    )
    assert metrics["survival"] is True
    assert metrics["survival_fraction"] == 1.0
    assert metrics["fall_fraction"] == 0.0
    assert metrics["torque_saturation_fraction"] == 0.0


def test_post_fault_fall_is_not_survival():
    velocity = np.tile([0.0, -0.2, 0.0], (10, 1))
    history = make_history(velocity)
    history["base_position"][7:, 2] = 0.0
    metrics = LocomotionMetrics.calculate_metrics(
        history, fault_time=5.0, sim_duration=10.0
    )
    assert metrics["survival"] is False
    assert metrics["fall_fraction"] > 0.0


def test_forward_metrics_follow_pre_fault_minus_y_motion():
    velocity = np.tile([0.0, -0.2, 0.0], (10, 1))
    metrics = LocomotionMetrics.calculate_metrics(
        make_history(velocity), fault_time=5.0, sim_duration=10.0
    )
    assert abs(metrics["v_pre"] - 0.2) < 1e-9
    assert abs(metrics["v_post"] - 0.2) < 1e-9
    assert abs(metrics["recovery_ratio"] - 1.0) < 1e-9
    assert metrics["forward_progress"] > 0.0
    assert metrics["lateral_drift"] < 1e-9


def test_lateral_motion_is_not_forward_progress():
    velocity = np.tile([0.2, 0.0, 0.0], (10, 1))
    metrics = LocomotionMetrics.calculate_metrics(
        make_history(velocity), fault_time=5.0, sim_duration=10.0
    )
    assert abs(metrics["v_pre"] - 0.0) < 1e-9
    assert abs(metrics["forward_progress"]) < 1e-9
    assert metrics["lateral_drift"] > 0.0


def test_performance_loss_auc_is_bounded_for_backward_motion():
    velocity = np.vstack([
        np.tile([0.0, -0.2, 0.0], (5, 1)),
        np.tile([0.0, 0.2, 0.0], (5, 1)),
    ])
    metrics = LocomotionMetrics.calculate_metrics(
        make_history(velocity), fault_time=5.0, sim_duration=10.0
    )
    assert 0.0 <= metrics["performance_loss_auc"] <= 1.0


def test_locked_joint_drift_is_reported_against_fault_angle():
    velocity = np.tile([0.0, -0.2, 0.0], (10, 1))
    history = make_history(velocity)
    history["joint_angles"][5:, 2] = [0.26, 0.25, 0.25, 0.25, 0.25]
    metrics = LocomotionMetrics.calculate_metrics(
        history,
        fault_time=5.0,
        sim_duration=10.0,
        locked_joint_idx=2,
        locked_angle=0.25,
    )
    assert abs(metrics["locked_joint_drift_max_rad"] - 0.01) < 1e-12
    assert metrics["locked_joint_drift_rms_rad"] > 0.0
    assert metrics["locked_joint_drift_within_tolerance"] is False
    assert metrics["locked_joint_drift_steady_max_rad"] == 0.0
    assert metrics["locked_joint_drift_steady_within_tolerance"] is True


def test_non_locked_metrics_leave_lock_drift_undefined():
    metrics = LocomotionMetrics.calculate_metrics(
        make_history(np.tile([0.0, -0.2, 0.0], (10, 1))),
        fault_time=5.0,
        sim_duration=10.0,
    )
    assert metrics["locked_joint_drift_max_rad"] is None
    assert metrics["locked_joint_drift_within_tolerance"] is None


def test_windowed_heading_detects_lateral_zigzag_that_cancels_at_endpoint():
    velocity = np.array([
        [0.2, -0.2, 0.0],
        [-0.2, -0.2, 0.0],
        [0.2, -0.2, 0.0],
        [-0.2, -0.2, 0.0],
        [0.2, -0.2, 0.0],
        [-0.2, -0.2, 0.0],
        [0.2, -0.2, 0.0],
        [-0.2, -0.2, 0.0],
        [0.2, -0.2, 0.0],
        [-0.2, -0.2, 0.0],
    ])
    metrics = LocomotionMetrics.calculate_metrics(
        make_history(velocity),
        fault_time=5.0,
        sim_duration=10.0,
        heading_window_s=1.0,
    )
    assert metrics["lateral_drift"] > 0.0
    assert metrics["heading_deviation_deg"] > 0.0
