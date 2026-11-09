# Survey & Architectural Investigation Report: AHM-CPG Snake Robot Simulation

**Agent**: Explorer 1 (Survey Phase)  
**Date**: 2026-08-15  
**Workspace**: `e:/agy/snake - Copy`  
**Working Directory**: `e:/agy/snake - Copy/.agents/teamwork_preview_explorer_survey_1`

---

## 1. Observation

Direct examination of the workspace structure, codebase, and configuration reveals the following components, implementation details, line-by-line mechanisms, and current assets.

### 1.1 Project Structure Overview
The repository contains the following primary directories and files:
- `config.py` (77 lines): Global configuration constants (`RobotConfig`, `CPGConfig`, `HormoneConfig`, `SimConfig`).
- `c5_architecture_diagram.md` (228 lines): Mermaid workflow diagrams for the 7-step AHM-CPG pipeline.
- `simulation/`:
  - `snake_robot.py` (199 lines): PyBullet multi-body procedural model, joint motor actuation, and fault injection.
  - `environments.py` (105 lines): Simulation environments (flat, low friction, incline), physics setup, and video recording.
- `controllers/`:
  - `so2_cpg.py` (106 lines): Continuous-time $SO(2)$ limit-cycle oscillator CPG network with dynamic phase coupling and bypass topology.
  - `hormone_engine.py` (112 lines): Cycle-averaged sensory mismatch computation, 1D spatial diffusion ODE, Hill receptor kinetics, and specialized receptor outputs.
  - `ahm_cpg_controller.py` (123 lines): Proposed Controller C5 combining proprioceptive feedback, AHM hormone engine, amplitude/frequency modulation, topology reconfiguration (dynamic bypass), and steering bias compensation.
  - `baselines.py` (172 lines): Baseline controllers C1 (Fixed CPG), C2 (Error-Adaptive), C3 (Shape-Based Recovery), C4 (Oracle Fault-Aware), and C6 (AHM without Dynamic Bypass).
- `experiments/`:
  - `run_single.py` (160 lines): Single-episode runner with logging and video export.
  - `run_batch_benchmark.py` (89 lines): Sequential benchmark runner.
  - `run_publication_experiments.py` (447 lines): Master publication experiment suite (Benchmark, Generalization, Detail Histories).
  - `run_publication_experiments_parallel.py` (174 lines): Multi-core parallel benchmark runner using `multiprocessing.Pool`.
  - `run_sensitivity_analysis.py` (245 lines): 2D hyperparameter sensitivity sweep ($D_h$ vs $\alpha_h$, $K_h$ vs $m$).
  - `run_4stage_hormone_preliminary.py` (479 lines): 4-stage hierarchical tuning pipeline.
- `analysis/`:
  - `metrics.py` (201 lines): Journal-grade locomotion metrics suite (`LocomotionMetrics.calculate_metrics`).
  - `statistics.py` & `statistics_publication.py` (289 lines): Statistical test runner (Kruskal-Wallis, Mann-Whitney U, Cliff's delta, Bootstrap 95% CI, LaTeX/Markdown tables).
  - `plot_publication.py` (622 lines): Matplotlib publication figure generator (10 figures).
  - `plot_sensitivity.py` (126 lines): 2D sensitivity heatmap plotter.
  - `plot_generalization.py` (130 lines): Benchmark & generalization boxplots/bar charts.
  - `generate_full_latex_manuscript.py` (324 lines) & `generate_latex_manuscript.py` (72 lines): LaTeX manuscript generators.
- `results/`:
  - `results/publication/data/`: `benchmark_results.json` (270 records), `generalization_results.json` (150 records), `sensitivity_results.json`, `detail_histories/` (6 json files: `c1_locked_j3.json` .. `c6_locked_j3.json`).
  - `results/publication/figures/`: 13 PNG figures (`fig01` to `fig10`, `fig_dR_*`, `table1_*`).
  - `results/publication/tables/`: `table1_benchmark_summary.md/.tex`, `table2_statistical_tests.md/.tex`.

---

### 1.2 Simulation Engine & PyBullet Setup
Inspecting `simulation/environments.py`:
- **Physics Client**: `p.connect(p.DIRECT)` or `p.connect(p.GUI)` (lines 24-25).
- **Physics Step Time**: `p.setTimeStep(0.005)` (line 29), running at 200 Hz. Gravity set to $-9.81\text{ m/s}^2$ on the Z axis (line 28).
- **Ground Model**: `_build_ground()` loads `plane.urdf` from `pybullet_data` (line 49/51).
  - Standard plane lateral friction: $\mu = 0.8$ (line 53).
  - Low-friction plane: $\mu = 0.25$ when `env_type == EnvironmentType.LOW_FRICTION` (line 55).
  - Incline slope: orientates `plane.urdf` by pitch Euler angle `[0, -rad, 0]` when `env_type == EnvironmentType.INCLINE` (lines 47-49).
- **Video Capture**: `capture_frame()` tracks `target_pos` using `p.computeViewMatrixFromYawPitchRoll()` and `p.getCameraImage()`, writing frames via `imageio.get_writer()` at 30 fps with `libx264` (lines 38-42, 60-95).

---

### 1.3 Robot Physical & Kinematic Model
Inspecting `simulation/snake_robot.py` and `config.py`:
- **Model Construction**: Procedural multi-body construction via `p.createMultiBody()` (lines 70-87 of `snake_robot.py`). No `.urdf` file is used.
- **Topology**:
  - `NUM_SEGMENTS = 9` (base link + 8 child links).
  - `NUM_JOINTS = 8` (revolute joints along Z-axis for planar Yaw motion, `joint_axes = [[0, 0, 1]] * 8`, line 68).
  - Parent indices: `[0, 1, 2, 3, 4, 5, 6, 7]` (line 64).
  - Segment Geometry: Cylinders with `LINK_RADIUS = 0.035` m, `LINK_LENGTH = 0.122` m (total robot length $\approx 1.10$ m).
  - Mass & Inertia: `LINK_MASS = 1.05` kg per link, `TOTAL_MASS = 9.45` kg (`baseMass = 1.05`, `linkMasses = [1.05]*8`).
  - Joint Limits: `[-pi/3, pi/3]` ($\pm 60^\circ$).
  - Actuator Limits: `MAX_TORQUE = 8.0` N$\cdot$m, `MAX_VELOCITY = 10.0` rad/s.
- **Anisotropic Ground Friction**:
  - Applied per link (from base link -1 through joint 7) via `p.changeDynamics()` (lines 90-99 of `snake_robot.py`):
    ```python
    p.changeDynamics(
        robot_id, link_idx,
        lateralFriction=SimConfig.LATERAL_FRICTION, # 0.8
        anisotropicFriction=[SimConfig.FORWARD_FRICTION, SimConfig.SIDEWAYS_FRICTION, 0.01], # [0.05, 0.95, 0.01]
        spinningFriction=0.001,
        rollingFriction=0.001,
        restitution=0.0
    )
    ```
  - Forward friction $\mu_{\text{fwd}} = 0.05$, lateral/sideways friction $\mu_{\text{lat}} = 0.95$, enabling passive propulsion via body undulation waves.

---

### 1.4 Joint Actuation & Fault Injection Mechanisms
Inspecting `simulation/snake_robot.py`:
- **Actuation**:
  - Normal operation: `p.setJointMotorControl2(controlMode=p.POSITION_CONTROL, targetPosition=target_angles[i], force=MAX_TORQUE)` (line 170).
  - Low-level PD gains: PyBullet default internal motor controller with `MAX_TORQUE = 8.0` N$\cdot$m.
- **Fault Injection (`inject_fault(joint_idx, fault_type, params)`)**:
  - `FaultType.LOCKED` (lines 122-124, 132-142): Reads current angle `joint_state[0]` and commands position control holding that angle with full torque (`force=MAX_TORQUE`).
  - `FaultType.FREE` (lines 144-154): Sets `controlMode=p.VELOCITY_CONTROL, targetVelocity=0, force=0.0` (unactuated, limp/passive joint).
  - `FaultType.PARTIAL_TORQUE` (lines 156-166): Sets `controlMode=p.POSITION_CONTROL, force=gamma_f * MAX_TORQUE` (e.g. $\gamma_f = 0.30$).
- **Multi-Joint Fault Limitation Observed**:
  - In `SnakeRobot.__init__` (lines 30-34): `self.fault_active = False`, `self.fault_joint_idx = None`, `self.fault_type = FaultType.NONE`.
  - In `inject_fault()` (lines 117-120): sets `self.fault_joint_idx = joint_idx`.
  - In `apply_joint_commands()` (line 131): checks `if self.fault_active and i == self.fault_joint_idx:`.
  - *Finding*: `SnakeRobot` only tracks a **single scalar integer** `self.fault_joint_idx`. When multiple joints are injected sequentially (e.g. `for jidx in [2, 5]: robot.inject_fault(jidx, ...)`), only the last joint is held in `self.fault_joint_idx`.

---

### 1.5 Ground Contact Models & Disturbance Mechanisms
- **Anisotropic Friction**:
  - Implemented on robot links via `anisotropicFriction=[0.05, 0.95, 0.01]`.
- **High-Slip / Low-Friction**:
  - Implemented at plane level via `EnvironmentType.LOW_FRICTION` ($\mu = 0.25$).
  - *Finding*: Robot link anisotropic friction remains active unless explicitly overwritten on the link dynamics.
- **Dynamic Friction Transitions Mid-Run**:
  - `EnvironmentType.VARIABLE_FRICTION` is declared in `simulation/environments.py` (line 12), but no mid-run friction modulation logic or trigger is currently implemented in `environments.py` or `snake_robot.py`.
- **Mechanical Disturbances**:
  - Generalization runner `run_publication_experiments.py` implements:
    1. Incline slope ($10^\circ$).
    2. Sensor noise: Gaussian noise $\mathcal{N}(0, 0.05\text{ rad})$ on joint angles.
    3. Mass perturbation: Link mass scaled by $+35\%$ ($1.35\times$).
    4. Intermittent fault toggling: periodic locking/unlocking every $1.5\text{s}$–$3.0\text{s}$.
  - *Finding*: External mechanical impulse/lateral force disturbances (`p.applyExternalForce`) are not yet integrated.

---

### 1.6 Controller Architectures (C1–C6)
1. **C1: Fixed SO(2) CPG** (`FixedCPGController` in `baselines.py` lines 10-18):
   - Open-loop SO(2) oscillators with fixed nominal amplitude $A_0 = 0.60$ and nominal phase coupling $K_0 = 1.20$. No sensory feedback or adaptation.
2. **C2: Error-Adaptive CPG** (`ErrorAdaptiveCPGController` in `baselines.py` lines 20-45):
   - First-order filtered tracking error $e_i = 0.92 e_i + 0.08 |q_d - q_{act}|$.
   - Drops amplitude of failed joint to $0.2 A_0$ if $e_i > 0.15$; boosts all others to $1.25 A_0$. No hormone diffusion or bypass.
3. **C3: Shape-Based Recovery CPG** (`ShapeBasedRecoveryController` in `baselines.py` lines 47-73):
   - Slow filtered error ($0.992 / 0.008$). If $e_i > 0.25$, freezes joint $i$ ($0.1 A_0$) and boosts immediate neighbors $i-1, i+1$ to $1.5 A_0$. No phase bypass coupling.
4. **C4: Oracle Controller** (`OracleFaultAwareCPGController` in `baselines.py` lines 75-106):
   - Perfect ground-truth fault knowledge: instantly decouples failed joint $f$, boosts $f \pm 1$ to $1.45 A_0$, and enables bypass coupling $K_B = 2.80$ between $f-1$ and $f+1$. Theoretical performance ceiling.
5. **C5: Proposed Local-Global AHM-Gated SO(2) CPG** (`AHMCPGController` in `ahm_cpg_controller.py` lines 12-123):
   - Step 1: Mismatch sensory input ($e_q, e_v, e_\tau, P_{mech}$) with cycle-window averaging ($W \approx 67$ steps).
   - Step 2: 1D spatial diffusion ODE: $\dot{H}_i = \alpha_h S_i - (d_0 + k_d H_i^n) H_i + D_h \nabla^2 H_i$, followed by Hill receptor activation $R_i = H_i^m / (K_h^m + H_i^m)$.
   - Step 3: Amplitude modulation: $A_j = A_0 (1 - g_a R_j)(1 + g_n \sum_{i \ne j} R_i e^{-|j-i|/\sigma})$.
   - Step 4: Frequency scaling: $\omega = \omega_0 (1 - g_w H_G)$.
   - Step 5: Topology reconfiguration: adjacent decoupling $K_{adj} = 1 - \max(R_i, R_{i+1})$ and dynamic two-hop bypass $K_B(i-1, i+1) = K_B R_i$.
   - Step 6: SO(2) limit-cycle integration with bypass matrix.
   - Step 7: Decentralized yaw steering correction: $\Delta q_j = \gamma_{steer} \sum R_{steer}$ on even joints.
6. **C6: AHM-CPG without Dynamic Bypass** (`AHMNobypassCPGController` in `baselines.py` lines 108-172):
   - Full AHM hormone dynamics, Hill gating, amplitude & frequency modulation, and steering bias, but **without** bypass matrix coupling ($K_B = 0$).

---

### 1.7 Metrics Suite & Statistical Pipeline
- **Metrics (`analysis/metrics.py`)**:
  - Computes heading-aligned $v_{pre\_fwd}, v_{post\_fwd}$, recovery ratio $R_{perf} / \eta_{rec} = v_{post\_fwd} / \max(v_{pre\_fwd}, v_{nom})$, adaptation latency $T_{adapt}$, mechanical cost of transport $COT = E_{total} / (m \cdot g \cdot d)$, dynamic RMS torque $\tau_{RMS}$, lateral drift $X_{drift}, Y_{drift}$, Dr. Potiwat Displacement Index $Di$, performance loss AUC $L_{AUC}$, hormone contrast ratio $C_H$, and kinematic jerk $J_{kin}$.
- **Statistical Testing (`analysis/statistics_publication.py`)**:
  - Kruskal-Wallis omnibus test across all controllers.
  - Mann-Whitney U pairwise tests (C5 vs baselines) with Holm-Bonferroni correction.
  - Non-parametric Cliff's $\delta$ effect size and 10,000-resample Bootstrap 95% confidence intervals.
  - Generates Markdown and LaTeX summary tables (`table1_benchmark_summary`, `table2_statistical_tests`).

---

### 1.8 LaTeX Manuscript & Figure Assets
- Existing manuscript scripts (`generate_latex_manuscript.py` and `generate_full_latex_manuscript.py`) generate an `IEEEtran` document (`\documentclass[journal]{IEEEtran}`).
- 10 publication figures are generated in `results/publication/figures/` (Fig 1: Velocity Recovery, Fig 2: Hormone Heatmap, Fig 3: Joint Trajectories, Fig 4: Receptor Heatmap, Fig 5: Benchmark Boxplots, Fig 6: Generalization Grid, Fig 7: Fault Location Sensitivity, Fig 8: Bypass Ablation, Fig 9: 6-Axis Radar Chart, Fig 10: Success Rate & Drift Heatmap).

---

## 2. Logic Chain

From the direct observations above, we establish the step-by-step logic chain assessing compliance against Requirements R1–R5 and identifying necessary enhancements.

```
[Observation 1.4: SnakeRobot tracks single scalar fault_joint_idx]
  └─► [Logic Step 1]: Consecutive dual (J3+J4) or non-consecutive dual (J2+J5) faults cannot be simulated simultaneously in SnakeRobot without overwriting fault states.
  └─► [Requirement R1 Gap]: Multi-joint fault injection must be updated to store a dictionary/list of active faults per joint index.

[Observation 1.4: inject_fault locks joint to current joint_state[0]]
  └─► [Logic Step 2]: R1 specifies testing locked joints at "0 rad & non-zero offset angles".
  └─► [Requirement R1 Gap]: inject_fault must support an explicit target lock angle (e.g. locked_angle=0.0 or specified offset) passed via parameters.

[Observation 1.5: environments.py lacks mid-run friction transition logic]
  └─► [Logic Step 3]: R1 requires dynamic friction transitions mid-run (e.g., standard anisotropic -> high-slip isotropic -> low friction).
  └─► [Requirement R1 Gap]: Need a dynamic environmental transition handler that alters link/plane friction dynamics during simulation execution.

[Observation 1.7: statistics_publication.py uses Kruskal-Wallis, Mann-Whitney U, Cliff's delta]
  └─► [Logic Step 4]: R2 explicitly specifies paired/unpaired Wilcoxon signed-rank tests, ANOVA, and Cohen's d effect sizes in addition to Mann-Whitney U.
  └─► [Requirement R2 Gap]: Add Wilcoxon signed-rank, one-way/two-way ANOVA, and Cohen's d effect size calculations into statistical analysis scripts.

[Observation 1.1 & 1.6: run_sensitivity_analysis.py covers Dh vs alpha_h and Kh vs m]
  └─► [Logic Step 5]: R3 requires isolated quantification of 5 distinct bio-inspired modules:
      (1) Dh=0 vs Dh>0, (2) m=1 vs m=4, (3) KB=0 vs KB=2.80, (4) gw=0 vs gw=0.15, (5) gamma=0 vs gamma=-0.18.
  └─► [Requirement R3 Gap]: Implement a dedicated 5-component ablation experiment runner and formatted summary table.

[Observation 1.8: plot_publication.py generates 10 figures]
  └─► [Logic Step 6]: R4 specifies limit-cycle phase portraits (x1 vs x2), 2D trajectory path tracking, and environmental transition response curves in Bioinspiration & Biomimetics style.
  └─► [Requirement R4 Gap]: Generate limit-cycle phase portraits, 2D X-Y path tracking curves, and dynamic transition plots.

[Observation 1.8: manuscript scripts generate IEEEtran LaTeX]
  └─► [Logic Step 7]: R5 mandates manuscript submission format for Bioinspiration & Biomimetics (IOPscience) with complete .bib bibliography.
  └─► [Requirement R5 Gap]: Create an IOPscience-formatted LaTeX manuscript template (manuscript_bioinspiration.tex / main.tex) with standalone bibliography.bib.
```

---

## 3. Caveats

1. **Read-Only Survey Discipline**:
   - In accordance with the Teamwork explorer role, no source files were modified during this investigation. All findings and gaps are documented for subsequent implementation.
2. **PyBullet Physics Determinism & Seed Stochasticity**:
   - PyBullet's rigid body engine is deterministic when initialized with identical states. To produce genuine multi-seed statistical variance ($N \ge 10$), `run_publication_experiments.py` injects initial joint pose perturbations ($\pm 2^\circ$), link friction variations ($\pm 10\%$), fault timing jitter ($\pm 0.5\text{s}$), and link mass noise ($\pm 3\%$). This stochastic protocol must be preserved across all $N \ge 10$ benchmark runs.
3. **Execution Runtime & Multiprocessing**:
   - A full factorial benchmark with $N = 10$ seeds across 6 controllers $\times$ 3 fault types $\times$ 3 joint locations $\times$ 5 environments requires over 2,700 simulation episodes. Parallel execution via `multiprocessing.Pool` (utilizing 6–7 CPU cores) is required to complete simulations efficiently.

---

## 4. Conclusion

### 4.1 Requirement Status Matrix

| Req | Requirement Name | Existing Implementation | Identified Gaps | Readiness |
|:---:|:---|:---|:---|:---:|
| **R1** | Simulation & Benchmarking Pipeline | Complete C1–C6 controllers, PyBullet 200 Hz engine, single-joint locked/free/partial faults, incline slope | • `SnakeRobot` multi-joint fault dict storage<br>• Explicit 0-rad & offset locked angle support<br>• Mid-run dynamic friction transition hook | 85% |
| **R2** | Statistical Rigor & Metric Suite | Full `LocomotionMetrics` suite, Kruskal-Wallis, Mann-Whitney U, Cliff's $\delta$, Bootstrap 95% CI | • $N \ge 10$ random seeds<br>• Wilcoxon signed-rank test<br>• ANOVA & Cohen's d effect size | 85% |
| **R3** | Comprehensive Ablation Study | 2D sensitivity sweeps ($D_h$ vs $\alpha_h$, $K_h$ vs $m$), C6 baseline ($K_B = 0$) | • Full 5-module isolated ablation matrix ($D_h, m, K_B, g_w, \gamma$) | 80% |
| **R4** | Publication-Ready Figures | 10 high-resolution (300 DPI) figures, radar chart, boxplots, heatmaps | • Limit-cycle phase portraits ($x_1, x_2$)<br>• 2D overhead trajectory paths<br>• Dynamic friction transition curves | 85% |
| **R5** | Q1 IOP LaTeX Manuscript | Working LaTeX generators with results, tables, and inline discussion | • Reformat from IEEEtran to IOPscience (Bioinspiration & Biomimetics)<br>• Standalone `.bib` bibliography | 80% |

---

## 5. Verification Method

To independently verify all findings and codebase capabilities, the following commands can be executed:

1. **Verify Single Episode Simulation & Controllers (C1–C6)**:
   ```bash
   python -c "from experiments.run_single import run_single_episode; h, res = run_single_episode(controller_type='C5', fault_type='locked', fault_joint_idx=3, duration=10.0); print('C5 OK, RecRatio:', res['recovery_ratio'])"
   ```

2. **Verify Multi-Core Parallel Benchmark Runner**:
   ```bash
   python experiments/run_publication_experiments_parallel.py
   ```

3. **Verify Statistical Analysis Suite**:
   ```bash
   python analysis/statistics_publication.py
   ```

4. **Verify Figure Generation**:
   ```bash
   python analysis/plot_publication.py
   python analysis/plot_sensitivity.py
   ```

5. **Verify LaTeX Manuscript Compilation**:
   ```bash
   python analysis/generate_full_latex_manuscript.py
   ```
