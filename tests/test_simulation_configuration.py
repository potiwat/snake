import pybullet as p
import pytest

from config import SimConfig
from experiments import run_single
from simulation.environments import EnvironmentType, SimulationEnvironment
from simulation.snake_robot import FaultType, SnakeRobot


def test_run_single_forwards_configured_incline_angle(monkeypatch):
    captured = {}

    class StopAfterEnvironmentConstruction(Exception):
        pass

    def fake_environment(**kwargs):
        captured.update(kwargs)
        raise StopAfterEnvironmentConstruction

    monkeypatch.setattr(run_single, "SimulationEnvironment", fake_environment)
    with pytest.raises(StopAfterEnvironmentConstruction):
        run_single.run_single_episode(
            env_type=EnvironmentType.INCLINE,
            incline_deg=10.0,
        )
    assert captured["env_type"] == EnvironmentType.INCLINE
    assert captured["incline_deg"] == 10.0


def test_variable_friction_creates_multiple_surface_friction_regions():
    env = SimulationEnvironment(gui=False, env_type=EnvironmentType.VARIABLE_FRICTION)
    try:
        surface_ids = env.surface_ids
        frictions = [
            p.getDynamicsInfo(surface_id, -1, physicsClientId=env.physics_client)[1]
            for surface_id in surface_ids
        ]
        assert len(surface_ids) >= 2
        assert len(set(round(value, 6) for value in frictions)) >= 2
    finally:
        env.close()


def test_multi_joint_faults_preserve_all_locked_joints():
    env = SimulationEnvironment(gui=False)
    try:
        robot = SnakeRobot(env.physics_client)
        robot.inject_fault(2, FaultType.LOCKED)
        robot.inject_fault(5, FaultType.LOCKED)
        assert set(robot.active_faults) == {2, 5}
    finally:
        env.close()


def test_feedback_exposes_last_commanded_torques():
    env = SimulationEnvironment(gui=False)
    try:
        robot = SnakeRobot(env.physics_client)
        target = [0.2] * robot.num_joints
        commanded = robot.apply_joint_commands(target)
        feedback = robot.get_sensory_feedback()
        assert feedback["commanded_torques"] == commanded
    finally:
        env.close()


def test_locked_fault_uses_zero_torque_and_holds_fault_angle():
    env = SimulationEnvironment(gui=False)
    try:
        robot = SnakeRobot(env.physics_client)
        joint_idx = 2
        p.resetJointState(
            robot.robot_id, joint_idx, targetValue=0.31,
            physicsClientId=env.physics_client
        )
        robot.inject_fault(joint_idx, FaultType.LOCKED)
        commands = robot.apply_joint_commands([0.9] * robot.num_joints)
        for _ in range(100):
            p.stepSimulation(physicsClientId=env.physics_client)
        final_angle = p.getJointState(
            robot.robot_id, joint_idx, physicsClientId=env.physics_client
        )[0]
        assert commands[joint_idx] == 0.0
        assert abs(final_angle - robot.locked_angle) < 1e-3
    finally:
        env.close()


def test_video_capture_schedule_matches_declared_fps():
    """A 10 s, 200 Hz episode must produce 300 frames at 30 fps, not 333."""
    env = SimulationEnvironment(gui=False)
    try:
        env.record_fps = 30
        frame_count = sum(env._should_capture_frame(step) for step in range(1, 2001))
        assert frame_count == 300
    finally:
        env.close()


def test_environment_configures_canonical_solver_iterations():
    env = SimulationEnvironment(gui=False)
    try:
        params = p.getPhysicsEngineParameters(physicsClientId=env.physics_client)
        assert params["numSolverIterations"] == SimConfig.NUM_SOLVER_ITERATIONS
        assert SimConfig.NUM_SOLVER_ITERATIONS == 800
    finally:
        env.close()
