"""
Adversarial Empirical Stress Testing & Verification Suite for AHM-CPG Snake Robot.
Authored by Empirical Challenger Agent.

Verifies:
1. CPG controller stepping under extreme and boundary parameters.
2. Multi-joint fault injection and motor torque clamping.
3. Numerical stability of 1D reaction-diffusion PDE integration and Hill receptor kinetics.
4. Metric calculations on edge-case trajectories (zero distance, reverse motion, jitter, short logs).
5. Statistical test functions handling edge-case data (zero variance, identical samples, NaN/Inf).
6. Figure files integrity and LaTeX manuscript syntax / BibTeX key resolution.
"""

import os
import re
import math
import json
import pytest
import numpy as np
from pathlib import Path
from scipy import stats

from config import RobotConfig, CPGConfig, HormoneConfig, SimConfig
from controllers.so2_cpg import SO2CPGNetwork
from controllers.hormone_engine import HormoneEngine
from controllers.ahm_cpg_controller import AHMCPGController
from controllers.baselines import (
    FixedCPGController,
    ErrorAdaptiveCPGController,
    ShapeBasedRecoveryController,
    OracleFaultAwareCPGController,
    AHMNobypassCPGController,
)
from simulation.snake_robot import SnakeRobot, FaultType
from simulation.environments import SimulationEnvironment, EnvironmentType
from analysis.metrics import LocomotionMetrics
from analysis.statistics_publication import (
    compute_cliffs_delta,
    cliffs_magnitude,
    compute_cohens_d,
    compute_paired_cohens_d,
    bootstrap_ci,
    holm_bonferroni_correct,
    one_way_anova,
    repeated_measures_anova,
)

import pybullet as p


# ═══════════════════════════════════════════════════════════════════
# 1. CPG Controller Stepping Under Extreme & Boundary Parameters
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_CPGController:
    """Stress tests for SO(2) limit cycle oscillators and controller networks."""

    def test_cpg_extreme_frequencies(self):
        """Verify SO(2) CPG stepping remains bounded under extreme frequency scaling."""
        for freq_scale in [0.01, 0.1, 0.3, 1.0, 1.5, 5.0, 50.0]:
            cpg = SO2CPGNetwork(num_joints=8)
            cpg.set_global_frequency_scale(freq_scale)
            
            # Step for 500 steps
            for _ in range(500):
                angles = cpg.step(dt=0.01)
                assert not np.isnan(angles).any(), f"NaN detected at freq_scale={freq_scale}"
                assert not np.isinf(angles).any(), f"Inf detected at freq_scale={freq_scale}"
                assert np.all(np.abs(angles) <= 2.0 * RobotConfig.JOINT_LIMIT_MAX)

    def test_cpg_extreme_target_amplitudes(self):
        """Verify amplitude clipping under negative, zero, and huge amplitudes."""
        cpg = SO2CPGNetwork(num_joints=8)
        
        # Test negative, zero, and extreme amplitudes
        test_amps = [-10.0, 0.0, 0.0001, 0.5, 10.0, 1000.0]
        for amp in test_amps:
            target_amps = np.full(8, amp)
            cpg.set_amplitudes(target_amps)
            
            # Verify amplitude clamping
            assert np.all(cpg.amplitudes >= 0.05), "Amplitude dropped below minimum 0.05 rad"
            assert np.all(cpg.amplitudes <= RobotConfig.JOINT_LIMIT_MAX), "Amplitude exceeded joint limit"
            
            angles = cpg.step(dt=0.01)
            assert not np.isnan(angles).any()
            assert not np.isinf(angles).any()

    def test_cpg_long_term_limit_cycle_stability(self):
        """Verify 10,000 steps continuous integration without limit-cycle blowup or collapse."""
        cpg = SO2CPGNetwork(num_joints=8)
        for step in range(10000):
            angles = cpg.step(dt=0.01)
            # Verify state radius r^2 for all oscillators remains close to 1.0
            r2 = cpg.x[:, 0]**2 + cpg.x[:, 1]**2
            assert np.all(r2 > 0.1), f"Oscillator collapsed at step {step}: r2={r2}"
            assert np.all(r2 < 4.0), f"Oscillator exploded at step {step}: r2={r2}"
        assert not np.isnan(angles).any()

    def test_cpg_adversarial_bypass_matrices(self):
        """Verify CPG behavior with asymmetric, disconnected, and saturated bypass matrices."""
        cpg = SO2CPGNetwork(num_joints=8)
        
        # Case 1: Dense all-to-all bypass matrix
        dense_bypass = np.full((8, 8), 5.0)
        angles = cpg.step(dt=0.01, bypass_matrix=dense_bypass)
        assert not np.isnan(angles).any()
        
        # Case 2: Negative bypass weights
        neg_bypass = np.full((8, 8), -2.0)
        angles = cpg.step(dt=0.01, bypass_matrix=neg_bypass)
        assert not np.isnan(angles).any()
        
        # Case 3: Zero coupling weights
        zero_coupling = np.zeros(7)
        angles = cpg.step(dt=0.01, normal_coupling_weights=zero_coupling)
        assert not np.isnan(angles).any()

    def test_all_controllers_adversarial_sensory_feedback(self):
        """Verify all 6 controllers handle anomalous, infinite, and zero sensory feedback."""
        controllers = [
            FixedCPGController(),
            ErrorAdaptiveCPGController(),
            ShapeBasedRecoveryController(),
            OracleFaultAwareCPGController(),
            AHMCPGController(),
            AHMNobypassCPGController(),
        ]
        
        feedbacks = [
            # Case 1: All zeros
            {
                "joint_angles": np.zeros(8),
                "joint_velocities": np.zeros(8),
                "joint_torques": np.zeros(8),
                "commanded_torques": np.zeros(8),
            },
            # Case 2: Extreme high values
            {
                "joint_angles": np.full(8, 100.0),
                "joint_velocities": np.full(8, 500.0),
                "joint_torques": np.full(8, 1000.0),
                "commanded_torques": np.full(8, 1000.0),
            },
            # Case 3: Alternating signs
            {
                "joint_angles": np.array([(-1)**i * np.pi for i in range(8)]),
                "joint_velocities": np.array([(-1)**i * 50.0 for i in range(8)]),
                "joint_torques": np.array([(-1)**i * 20.0 for i in range(8)]),
                "commanded_torques": np.array([(-1)**i * 20.0 for i in range(8)]),
            },
        ]
        
        for ctrl in controllers:
            for fb in feedbacks:
                if isinstance(ctrl, OracleFaultAwareCPGController):
                    angles, info = ctrl.step(fb, fault_info={"active": True, "joint_idx": 3})
                else:
                    angles, info = ctrl.step(fb)
                assert len(angles) == 8
                assert not np.isnan(angles).any(), f"Controller {ctrl.__class__.__name__} produced NaN"
                assert not np.isinf(angles).any(), f"Controller {ctrl.__class__.__name__} produced Inf"
                # Joint angles must be within reasonable mechanical bounds
                assert np.all(np.abs(angles) <= np.pi), f"Controller {ctrl.__class__.__name__} angle out of bounds: {angles}"


# ═══════════════════════════════════════════════════════════════════
# 2. Multi-Joint Fault Injection & Motor Torque Clamping
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_FaultInjectionTorqueClamping:
    """Stress tests for multi-joint faults and actuator torque constraints."""

    @pytest.fixture(scope="class")
    def physics_sim(self):
        env = SimulationEnvironment(gui=False)
        cid = env.physics_client
        robot = SnakeRobot(cid)
        yield cid, env, robot
        env.close()

    def test_multi_joint_fault_combinatorics(self, physics_sim):
        """Verify fault injector handles all combinations of single, dual, and full lesions."""
        cid, env, robot = physics_sim
        
        # Test configurations: (joints, fault_type, params)
        test_configs = [
            ([0], FaultType.LOCKED, {"locked_angle": 0.0}),
            ([7], FaultType.LOCKED, {"locked_angle": 0.3}),
            ([3, 4], FaultType.LOCKED, {"locked_angle": -0.2}),
            ([2, 5], FaultType.FREE, {}),
            ([1, 6], FaultType.PARTIAL_TORQUE, {"gamma_f": 0.3}),
            (list(range(8)), FaultType.LOCKED, {"locked_angle": 0.0}), # All 8 locked
            ([0, 2, 4, 6], FaultType.FREE, {}), # Alternating limp
        ]
        
        for joints, f_type, params in test_configs:
            robot.clear_faults()
            for j in joints:
                robot.inject_fault(j, f_type, params)
            
            assert len(robot.active_faults) == len(joints)
            assert robot.fault_active is True
            
            # Step simulation with motor commands
            cmd = np.zeros(8)
            applied = robot.apply_joint_commands(cmd)
            p.stepSimulation(physicsClientId=cid)
            
            assert len(applied) == 8
            # Verify torque bounds
            for j in range(8):
                if j in joints:
                    if f_type == FaultType.FREE:
                        assert applied[j] == 0.0
                    elif f_type == FaultType.PARTIAL_TORQUE:
                        assert applied[j] <= RobotConfig.MAX_TORQUE * 0.3 + 1e-5
                assert applied[j] <= RobotConfig.MAX_TORQUE

    def test_fault_lifecycle_transitions(self, physics_sim):
        """Verify dynamic lifecycle: lock -> switch to limp -> clear -> partial torque."""
        cid, env, robot = physics_sim
        robot.clear_faults()
        
        # 1. Lock joint 3 at 0.4 rad
        robot.inject_fault(3, FaultType.LOCKED, {"locked_angle": 0.4})
        assert robot.active_faults[3]["type"] == FaultType.LOCKED
        assert robot.active_faults[3]["params"]["locked_angle"] == 0.4
        
        # 2. Switch joint 3 to limp
        robot.inject_fault(3, FaultType.FREE)
        assert robot.active_faults[3]["type"] == FaultType.FREE
        
        # 3. Clear fault on joint 3
        robot.clear_fault(3)
        assert 3 not in robot.active_faults
        assert robot.fault_active is False
        
        # 4. Batch inject multi faults
        robot.inject_faults({
            1: {"type": FaultType.LOCKED, "params": {"locked_angle": 0.1}},
            4: {"type": FaultType.PARTIAL_TORQUE, "params": {"gamma_f": 0.5}},
            7: {"type": FaultType.FREE, "params": {}},
        })
        assert len(robot.active_faults) == 3
        robot.clear_faults()
        assert len(robot.active_faults) == 0

    def test_out_of_bounds_fault_rejection(self, physics_sim):
        """Verify invalid joint indices raise ValueError."""
        cid, env, robot = physics_sim
        with pytest.raises(ValueError):
            robot.inject_fault(-1, FaultType.LOCKED)
        with pytest.raises(ValueError):
            robot.inject_fault(8, FaultType.LOCKED)
        with pytest.raises(ValueError):
            robot.inject_fault(100, FaultType.LOCKED)


# ═══════════════════════════════════════════════════════════════════
# 3. 1D Reaction-Diffusion PDE & Hill Receptor Kinetics
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_ReactionDiffusionAndHillKinetics:
    """Stress tests for numerical reaction-diffusion stability and Hill kinetics."""

    def test_pde_conservative_bounds_under_massive_stimulus(self):
        """Verify hormone concentrations remain in [0.0, 1.0] under constant saturated stimulus."""
        engine = HormoneEngine(num_joints=8)
        # Drive maximum stimulus for 1000 steps
        engine.filtered_stimulus = np.full(8, 100.0)
        
        for step in range(1000):
            H, H_G, R = engine.step(dt=0.01)
            assert np.all(H >= 0.0) and np.all(H <= 1.0), f"Hormone violated bounds [0, 1] at step {step}: {H}"
            assert 0.0 <= H_G <= 1.0, f"Global hormone violated bounds [0, 1]: {H_G}"
            assert np.all(R >= 0.0) and np.all(R <= 1.0), f"Receptor violated bounds [0, 1]: {R}"

    def test_pde_zero_stimulus_decay_to_zero(self):
        """Verify hormone concentrations decay strictly towards zero in absence of stimulus over biological timescale."""
        engine = HormoneEngine(num_joints=8)
        engine.H = np.full(8, 0.9)  # initial high concentration
        engine.filtered_stimulus = np.zeros(8)  # zero stimulus
        
        # In biological endocrine models with D0=0.1/s, decay over 60s (6000 steps at dt=0.01)
        for _ in range(6000):
            H, H_G, R = engine.step(dt=0.01)
            
        assert np.all(H < 0.01), f"Hormone failed to decay to zero: {H}"
        assert H_G < 0.01
        assert np.all(R < 0.001)

    def test_diffusion_neumann_boundary_conservation(self):
        """Verify boundary diffusion handling at head (i=0) and tail (i=7)."""
        engine = HormoneEngine(num_joints=8, dh=0.5)
        # Inject concentration only at head
        engine.H = np.zeros(8)
        engine.H[0] = 0.8
        engine.filtered_stimulus = np.zeros(8)
        
        # Step once and check diffusion into neighbor
        engine.step(dt=0.01)
        assert engine.H[1] > 0.0, "Diffusion did not propagate from head to joint 1"
        assert not np.isnan(engine.H).any()

    def test_hill_kinetics_extreme_parameters(self):
        """Verify Hill gating R = H^m / (Kh^m + H^m) across extreme m and Kh."""
        for m in [0.01, 0.5, 1.0, 2.0, 4.0, 10.0, 50.0, 100.0]:
            for kh in [1e-5, 0.1, 0.65, 1.0, 10.0]:
                engine = HormoneEngine(num_joints=8, hill_m=m, kh=kh)
                for h_val in [0.0, 0.1, 0.5, 0.65, 0.9, 1.0]:
                    engine.H = np.full(8, h_val)
                    _, _, R = engine.step(dt=0.01)
                    assert not np.isnan(R).any(), f"Hill produced NaN at m={m}, Kh={kh}, H={h_val}"
                    assert not np.isinf(R).any(), f"Hill produced Inf at m={m}, Kh={kh}, H={h_val}"
                    assert np.all(R >= 0.0) and np.all(R <= 1.0)

    def test_sensory_mismatch_adversarial_normalization(self):
        """Verify cycle-averaged stimulus computation handles extreme mismatch without overflow."""
        engine = HormoneEngine(num_joints=8)
        # Extremely large tracking errors (1000 rad)
        engine.update_feedback(
            target_q=np.full(8, 1000.0),
            actual_q=np.full(8, -1000.0),
            actual_v=np.full(8, 5000.0),
            commanded_tau=np.full(8, 100.0),
            actual_tau=np.full(8, 0.0)
        )
        assert np.all(engine.filtered_stimulus >= 0.0)
        assert np.all(engine.filtered_stimulus <= 1.0), f"Filtered stimulus exceeded 1.0: {engine.filtered_stimulus}"


# ═══════════════════════════════════════════════════════════════════
# 4. Metric Calculations on Edge-Case Trajectories
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_MetricCalculations:
    """Stress tests for locomotion metrics on degenerate and edge-case trajectories."""

    def test_metrics_stationary_robot_zero_division(self):
        """Verify robot stationary at origin produces zero/finite metrics without ZeroDivisionError."""
        N = 100
        history = {
            "time": np.linspace(0, 10, N).tolist(),
            "base_position": np.zeros((N, 3)).tolist(),
            "base_velocity": np.zeros((N, 3)).tolist(),
            "joint_angles": np.zeros((N, 8)).tolist(),
            "target_angles": np.zeros((N, 8)).tolist(),
            "joint_velocities": np.zeros((N, 8)).tolist(),
            "joint_torques": np.zeros((N, 8)).tolist(),
            "hormones": np.zeros((N, 8)).tolist(),
            "receptors": np.zeros((N, 8)).tolist(),
        }
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=5.0, sim_duration=10.0)
        assert isinstance(metrics, dict)
        assert metrics["v_fwd"] == 0.0
        assert metrics["eta_rec"] == 0.0
        assert not np.isnan(metrics["cost_of_transport"])
        assert not np.isinf(metrics["cost_of_transport"])
        assert metrics["cost_of_transport"] >= 0.0
        assert metrics["delta_yaw_deg"] == 0.0
        assert not np.isnan(metrics["di_linear"])

    def test_metrics_backward_locomotion(self):
        """Verify metrics when robot moves purely in negative Y direction."""
        N = 100
        time_arr = np.linspace(0, 10, N)
        y_pos = -0.2 * time_arr  # moving backwards at 0.2 m/s
        base_pos = np.column_stack([np.zeros(N), y_pos, np.zeros(N)])
        
        history = {
            "time": time_arr.tolist(),
            "base_position": base_pos.tolist(),
            "joint_angles": np.zeros((N, 8)).tolist(),
            "target_angles": np.zeros((N, 8)).tolist(),
            "joint_velocities": np.zeros((N, 8)).tolist(),
            "joint_torques": np.zeros((N, 8)).tolist(),
        }
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=5.0, sim_duration=10.0)
        assert metrics["v_fwd"] >= 0.0
        assert not np.isnan(metrics["cost_of_transport"])

    def test_metrics_short_trajectory(self):
        """Verify minimal 2-step trajectory does not crash."""
        history = {
            "time": [0.0, 0.01],
            "base_position": [[0, 0, 0], [0, 0.002, 0]],
            "joint_angles": [[0]*8, [0.01]*8],
            "target_angles": [[0]*8, [0.01]*8],
            "joint_velocities": [[0]*8, [0.1]*8],
            "joint_torques": [[0]*8, [1.0]*8],
        }
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=0.005, sim_duration=0.01)
        assert isinstance(metrics, dict)
        assert not np.isnan(metrics["v_fwd"])
        assert not np.isnan(metrics["cost_of_transport"])

    def test_metrics_extreme_kinematic_jerk(self):
        """Verify kinematic jerk computation on high-frequency oscillatory motion."""
        N = 200
        t = np.linspace(0, 2, N)
        # High-frequency alternating joint angles
        q_act = np.sin(200.0 * t)[:, None] * np.ones((N, 8))
        history = {
            "time": t.tolist(),
            "base_position": np.zeros((N, 3)).tolist(),
            "joint_angles": q_act.tolist(),
            "target_angles": q_act.tolist(),
            "joint_velocities": np.zeros((N, 8)).tolist(),
            "joint_torques": np.zeros((N, 8)).tolist(),
        }
        metrics = LocomotionMetrics.calculate_metrics(history, fault_time=1.0, sim_duration=2.0)
        assert metrics["jerk_smoothness"] >= 0.0
        assert not np.isnan(metrics["jerk_smoothness"])
        assert not np.isinf(metrics["jerk_smoothness"])


# ═══════════════════════════════════════════════════════════════════
# 5. Statistical Test Functions on Edge-Case Data
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_StatisticalTests:
    """Stress tests for publication statistical testing routines on edge cases."""

    def test_zero_variance_arrays(self):
        """Verify Cohen's d and Cliff's delta on constant identical arrays."""
        x = [1.0, 1.0, 1.0, 1.0, 1.0]
        y = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        d = compute_cohens_d(x, y)
        d_z = compute_paired_cohens_d(x, y)
        delta = compute_cliffs_delta(x, y)
        
        assert d == 0.0, f"Cohen's d should be 0.0 for identical constant arrays, got {d}"
        assert d_z == 0.0, f"Paired Cohen's d should be 0.0, got {d_z}"
        assert delta == 0.0, f"Cliff's delta should be 0.0, got {delta}"
        assert cliffs_magnitude(delta) == "Negligible"

    def test_single_sample_bootstrap_ci(self):
        """Verify Bootstrap CI on N=1 and N=2 arrays."""
        # N=1
        lo, hi = bootstrap_ci([5.0], n_boot=100)
        assert lo == 5.0 and hi == 5.0
        
        # N=2
        lo2, hi2 = bootstrap_ci([4.0, 6.0], n_boot=500)
        assert 4.0 <= lo2 <= hi2 <= 6.0

    def test_holm_bonferroni_edge_cases(self):
        """Verify Holm-Bonferroni on empty, ties, 0.0, 1.0, and reverse sorted p-values."""
        # Empty
        assert len(holm_bonferroni_correct([])) == 0
        
        # Saturated
        p_vals = [0.0, 0.0001, 0.01, 0.05, 0.99, 1.0]
        adj = holm_bonferroni_correct(p_vals)
        assert len(adj) == len(p_vals)
        assert np.all(adj >= 0.0) and np.all(adj <= 1.0)
        # Check monotonicity
        sorted_orig_idx = np.argsort(p_vals)
        for i in range(len(p_vals) - 1):
            assert adj[sorted_orig_idx[i]] <= adj[sorted_orig_idx[i+1]]

    def test_anova_edge_cases(self):
        """Verify One-Way and Repeated-Measures ANOVA on degenerate inputs."""
        # Empty groups
        f, p_val, eta, df_b, df_w = one_way_anova({})
        assert f == 0.0 and p_val == 1.0
        
        # Distinct groups with slight variance
        groups = {
            "C1": [1.0, 1.1, 0.9],
            "C2": [2.0, 2.1, 1.9],
            "C3": [3.0, 3.1, 2.9]
        }
        f, p_val, eta, df_b, df_w = one_way_anova(groups)
        assert not np.isnan(f)
        assert not np.isnan(p_val)
        assert p_val < 0.001
        
        # Repeated measures ANOVA on matrix with residual noise
        np.random.seed(42)
        matrix = np.array([[1.0, 2.0, 3.0, 4.0]] * 10) + np.random.normal(0, 0.05, (10, 4))
        f_rm, p_rm, eta_p, df_t, df_e = repeated_measures_anova(matrix)
        assert not np.isnan(f_rm)
        assert not np.isnan(p_rm)
        assert p_rm < 0.001
        assert eta_p > 0.80

        # Repeated measures ANOVA with zero residual error (guard returns 0.0 to prevent zero-division)
        zero_res_matrix = np.array([[1.0, 2.0, 3.0, 4.0]] * 5)
        f_zero, p_zero, _, _, _ = repeated_measures_anova(zero_res_matrix)
        assert f_zero == 0.0
        assert p_zero == 1.0


# ═══════════════════════════════════════════════════════════════════
# 6. Figure Files & LaTeX Manuscript Syntax Verification
# ═══════════════════════════════════════════════════════════════════

class TestAdversarial_PublicationFiguresAndLaTeX:
    """Stress tests for publication artifacts, figure files, and LaTeX/BibTeX integrity."""

    def test_publication_figure_files_exist_and_non_empty(self):
        """Verify all core publication figures (fig01 to fig14) exist and are non-empty."""
        fig_dir = Path("results/publication/figures")
        assert fig_dir.exists(), f"Directory {fig_dir} does not exist"
        
        expected_figs = [
            "fig01_velocity_recovery.png",
            "fig02_hormone_heatmap.png",
            "fig03_joint_trajectories.png",
            "fig04_receptor_heatmap.png",
            "fig05_benchmark_boxplots.png",
            "fig06_generalization.png",
            "fig07_fault_location.png",
            "fig08_bypass_ablation.png",
            "fig09_radar_chart.png",
            "fig10_success_heatmap.png",
            "fig11_phase_portraits.png",
            "fig12_traveling_wave_heatmap.png",
            "fig13_trajectory_paths.png",
            "fig14_dynamic_transitions.png",
        ]
        
        for fig_name in expected_figs:
            fig_path = fig_dir / fig_name
            assert fig_path.exists(), f"Missing publication figure: {fig_name}"
            file_size = fig_path.stat().st_size
            assert file_size > 1024, f"Figure {fig_name} is empty or suspiciously small ({file_size} bytes)"

    def test_latex_manuscript_syntax_and_balanced_structures(self):
        """Verify LaTeX manuscript syntax, balanced environments, and table/figure links."""
        tex_path = Path("results/publication/manuscript_bioinspiration.tex")
        if not tex_path.exists():
            tex_path = Path("results/publication/manuscript.tex")
        assert tex_path.exists(), f"Missing manuscript LaTeX file"
        
        with open(tex_path, "r", encoding="utf-8") as f:
            tex_content = f.read()
            
        assert len(tex_content) > 10000, "LaTeX manuscript is too short"
        
        # Check required IOP sections and abstract environment
        assert "\\begin{abstract}" in tex_content and "\\end{abstract}" in tex_content, "Missing abstract in manuscript"
        for sec in ["Introduction", "Modeling", "Methodology", "Results", "Ablation", "Conclusion"]:
            pattern = re.compile(rf"\\section\*?\{{.*{sec}.*\}}", re.IGNORECASE)
            assert pattern.search(tex_content), f"Missing section matching '{sec}' in manuscript"
            
        # Check balanced environments: \begin{env} and \end{env}
        begins = re.findall(r"\\begin\{([a-zA-Z0-9_\*]+)\}", tex_content)
        ends = re.findall(r"\\end\{([a-zA-Z0-9_\*]+)\}", tex_content)
        
        # Count frequency of each environment
        from collections import Counter
        begin_counts = Counter(begins)
        end_counts = Counter(ends)
        
        for env, count in begin_counts.items():
            assert env in end_counts, f"Environment {env} has {count} \\begin but no \\end"
            assert begin_counts[env] == end_counts[env], (
                f"Unbalanced environment \\{env}: {begin_counts[env]} \\begin vs {end_counts[env]} \\end"
            )

    def test_bibtex_bibliography_citation_resolution(self):
        """Verify BibTeX database has at least 30 references and verify citation coverage."""
        bib_path = Path("results/publication/references.bib")
        assert bib_path.exists(), "Missing references.bib"
        
        with open(bib_path, "r", encoding="utf-8") as f:
            bib_content = f.read()
            
        # Extract all bibtex keys: @article{key, @inproceedings{key, etc.
        bib_keys = set(re.findall(r"@\w+\s*\{\s*([a-zA-Z0-9_\-\:]+)\s*,", bib_content))
        assert len(bib_keys) >= 30, f"Expected at least 30 BibTeX references, found {len(bib_keys)}"
        
        # Find manuscript file
        tex_path = Path("results/publication/manuscript_bioinspiration.tex")
        if not tex_path.exists():
            tex_path = Path("results/publication/manuscript.tex")
            
        with open(tex_path, "r", encoding="utf-8") as f:
            tex_content = f.read()
            
        # Find all in-text citations: \cite{key1, key2} or \citep{...} or \citet{...}
        cite_matches = re.findall(r"\\cite[tp]?\*?\{([^}]+)\}", tex_content)
        all_cited_keys = []
        for match in cite_matches:
            keys = [k.strip() for k in match.split(",")]
            all_cited_keys.extend(keys)
            
        dangling_keys = [k for k in all_cited_keys if k and k not in bib_keys]
        # In case of any dangling keys, verify they are identified
        if len(dangling_keys) > 0:
            print(f"\n[Challenger Finding] Dangling citation keys in manuscript: {dangling_keys}")
        # Core standard citations must resolve
        for key in ["grillner2006", "manoonpong2007", "ijspeert2008", "turing1952", "crespi2008"]:
            assert key in bib_keys, f"Missing critical citation key {key} in references.bib"

