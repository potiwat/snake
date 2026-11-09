# Project: AHM-CPG Snake Robot Simulation, Statistical Benchmarking & Q1 Publication Pipeline

## Architecture
- **Multibody Physics & Simulation**: PyBullet 200 Hz rigid-body dynamics (`simulation/snake_robot.py`, `simulation/environments.py`), 9 segments, 8 revolute yaw joints, anisotropic ground friction ($\mu_{lat}=0.95, \mu_{fwd}=0.05$), multi-joint fault injector (locked at arbitrary angles, limp/free, partial torque), dynamic friction transitions, terrain inclines, and environmental disturbances.
- **CPG & Hormone Controllers**:
  - Continuous SO(2) limit-cycle oscillators (`controllers/so2_cpg.py`).
  - Neuro-endocrine AHM reaction-diffusion engine with Hill non-linear gating and multi-modal sensory feedback (`controllers/hormone_engine.py`).
  - Controller C5 (Proposed Local-Global AHM-CPG with 2-hop dynamic bypass and yaw counter-steering, `controllers/ahm_cpg_controller.py`).
  - Baseline Controllers C1 (Fixed SO(2) CPG), C2 (Error-Adaptive), C3 (Shape-Based Recovery), C4 (Oracle Fault-Aware), C6 (AHM without Dynamic Bypass) in `controllers/baselines.py`.
- **Metrics & Statistical Pipeline**: Multi-journal synthesized locomotion metrics suite ($v_{fwd}, \eta_{rec}, COT, E_{total}, \Delta\theta_{yaw}, t_{adapt}, \tau_{RMS}$) in `analysis/metrics.py`, and rigorous statistical testing in `analysis/statistics_publication.py` (Kruskal-Wallis, paired Wilcoxon, Mann-Whitney U with Holm-Bonferroni, One-Way ANOVA, Cohen's d, Cliff's delta, Bootstrap 95% CIs).
- **Visualization Suite**: High-resolution 300+ DPI IOP-style figures (`analysis/plot_publication.py`), including phase portraits, spacetime traveling wave heatmaps, boxplots with significance stars (`***`), 2D spatial trajectories, transition curves, and radar charts.
- **LaTeX Publication**: Complete IOPscience Bioinspiration & Biomimetics manuscript (`manuscript_bioinspiration.tex`, `references.bib`, embedded figures and tables).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Multi-Joint Fault Injection | Support simultaneous multi-joint faults (consecutive J3+J4, non-consecutive J2+J5, head J0/J1, mid J3/J4, tail J6/J7) with locked angles (0 rad & non-zero offsets) and limp modes | M1 | R1 |
| F2 | Dynamic Friction & Environmental Transitions | Dynamic mid-run friction transitions (anisotropic -> high-slip isotropic -> low friction) and slope/perturbation handling | M1 | R1 |
| F3 | Multi-Process Benchmark Execution | Multi-core parallel benchmark execution ($N \ge 10$ independent seeds) across all 6 controllers C1–C6 and all fault/environmental scenarios | M1 | R1 |
| F4 | Locomotion Metrics Suite | Full evaluation of $v_{fwd}, \eta_{rec}, COT, E_{total}, \Delta\theta_{yaw}, t_{adapt}, \tau_{RMS}, Di, J_{kin}$ | M2 | R2 |
| F5 | Statistical Significance Tests | Kruskal-Wallis, Wilcoxon signed-rank, Mann-Whitney U (Holm-Bonferroni), ANOVA, Cohen's d, Cliff's delta, Bootstrap 95% CIs, validating $p < 0.001$ superiority of C5 | M2 | R2 |
| F6 | 5-Module Isolated Ablation | Isolated evaluation of Hormone Diffusion ($D_h$), Hill Kinetics ($m$), Bypass Coupling ($K_B$), Frequency Mod ($g_w$), and Yaw Steering ($\gamma$) | M3 | R3 |
| F7 | 2D Parameter Sensitivity Sweeps | 2D parameter grid sweeps ($D_h \times \alpha_h$, $K_h \times m$) and sensitivity heatmaps | M3 | R3 |
| F8 | Publication Figures (300+ DPI) | High-res figures: phase portraits, wave heatmaps, boxplots with `***`, 2D paths, transition curves, radar charts | M4 | R4 |
| F9 | Q1 IOP LaTeX Manuscript | Complete *Bioinspiration & Biomimetics* (IOP) LaTeX manuscript (`manuscript_bioinspiration.tex`) with synchronized parameters and embedded figures/tables | M5 | R5 |
| F10 | Comprehensive Bibliography | Dedicated `references.bib` with 30+ peer-reviewed citations | M5 | R5 |
| F11 | End-to-End Verification & Audit | Complete validation against all acceptance criteria with clean forensic audit | M6 | Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Sim Engine & Benchmark Pipeline | Multi-joint fault storage, locked angles, dynamic friction transitions, $N \ge 10$ parallel simulation execution | none | DONE |
| M2 | Statistical Rigor & Metrics | Full metrics suite, Wilcoxon, Mann-Whitney U, ANOVA, Cohen's d, Cliff's delta, Bootstrap 95% CI, $p < 0.001$ validation | M1 | DONE |
| M3 | Ablation & Sensitivity Study | 5-module isolated ablations ($D_h, m, K_B, g_w, \gamma$) + 2D sensitivity grids | M1, M2 | DONE |
| M4 | Publication Visualizations | 300+ DPI IOP-style figures: phase portraits, wave heatmaps, 2D paths, boxplots with significance stars | M1, M2, M3 | DONE |
| M5 | Q1 LaTeX Manuscript & Bib | Complete IOPscience *Bioinspiration & Biomimetics* manuscript, `references.bib`, embedded figures & tables | M1, M2, M3, M4 | DONE |
| M6 | Final E2E Integration & Audit | Opaque-box E2E test verification, forensic audit, acceptance report | M1, M2, M3, M4, M5 | DONE |

## Interface Contracts
### `simulation.snake_robot` ↔ `controllers.*`
- Robot provides: `get_joint_states() -> (q_act, q_vel, torques)`, `get_base_pose() -> (pos, orn)`, `get_base_velocity() -> (lin_vel, ang_vel)`.
- Controller provides: `step(dt, sensory_feedback) -> target_angles (list of 8 floats)`.
- Robot receives: `apply_joint_commands(target_angles)`.

### `simulation.snake_robot` ↔ `experiments.*`
- Fault injection: `inject_fault(joint_idx, fault_type, params=dict(locked_angle=float, ...))` supporting multiple active joints simultaneously via dictionary mapping `self.active_faults[joint_idx] = {'type': fault_type, 'params': params}`.

### `experiments.*` ↔ `analysis.metrics`
- Simulation history dictionary `history` contains: `time`, `pos`, `vel`, `joint_angles`, `target_angles`, `joint_torques`, `joint_vels`, `hormone_levels`, `receptors`.
- `LocomotionMetrics.calculate_metrics(history, config, ...)` returns standardized dictionary with keys: `v_pre_fwd`, `v_post_fwd`, `recovery_ratio`, `cost_of_transport`, `total_mechanical_energy`, `delta_yaw_deg`, `adaptation_time`, `tau_rms`, `x_drift_mean`, `y_drift_mean`, `di_index`, `kinematic_jerk`, etc.

### `analysis.metrics` ↔ `analysis.statistics_publication`
- Formatted metrics DataFrame passed to statistical test runners for Kruskal-Wallis, Wilcoxon, Mann-Whitney U, ANOVA, Cohen's d, Cliff's delta, and LaTeX table export.

### `analysis.*` ↔ `results/publication/`
- All final datasets saved to `results/publication/data/*.json`.
- All publication tables saved to `results/publication/tables/*.tex` and `*.md`.
- All figures saved to `results/publication/figures/fig*.png` and `.pdf` (300 DPI).
- Manuscript saved to `results/publication/manuscript_bioinspiration.tex` with `references.bib`.

## Code Layout
```
e:/agy/snake - Copy/
├── config.py                                    # Global constants
├── c5_architecture_diagram.md                   # Architecture diagram
├── PROJECT.md                                   # Global Project Blueprint
├── TEST_INFRA.md                                # E2E Test Suite Architecture
├── TEST_READY.md                                # E2E Test Suite Readiness Signal
├── simulation/
│   ├── snake_robot.py                           # Multi-joint physics model & fault injector
│   └── environments.py                          # Ground friction, slopes & transitions
├── controllers/
│   ├── so2_cpg.py                               # SO(2) limit-cycle network
│   ├── hormone_engine.py                        # AHM reaction-diffusion & Hill kinetics
│   ├── ahm_cpg_controller.py                    # C5 Local-Global AHM-CPG Controller
│   └── baselines.py                             # C1, C2, C3, C4, C6 Controllers
├── experiments/
│   ├── run_single.py                            # Single-episode runner
│   ├── run_publication_experiments.py           # Master benchmark runner
│   ├── run_publication_experiments_parallel.py  # Parallel multiprocessing runner
│   ├── run_sensitivity_analysis.py              # 2D sensitivity grid sweep
│   └── run_ablation_study.py                    # 5-module isolated ablation runner
├── analysis/
│   ├── metrics.py                               # Locomotion metrics suite
│   ├── statistics_publication.py                # Journal statistical testing suite
│   ├── plot_publication.py                      # 300-DPI IOP publication figures
│   ├── plot_sensitivity.py                      # Sensitivity heatmap generator
│   └── generate_iop_latex_manuscript.py         # Bioinspiration & Biomimetics manuscript generator
├── tests/
│   └── test_e2e_pipeline.py                     # Requirement-driven E2E test suite
└── results/
    └── publication/
        ├── data/                                # Benchmark & ablation JSON datasets
        ├── figures/                             # 300+ DPI publication figures (PNG & PDF)
        ├── tables/                              # LaTeX & Markdown tables
        ├── references.bib                       # BibTeX bibliography
        └── manuscript_bioinspiration.tex        # IOPscience LaTeX manuscript
```
