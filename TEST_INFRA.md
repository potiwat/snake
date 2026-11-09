# Test Infrastructure & Methodology Specification (TEST_INFRA.md)

**Project:** AHM-CPG Snake Robot Simulation, Statistical Benchmarking & Q1 Publication Pipeline  
**Test Suite Path:** `tests/test_e2e_pipeline.py`  
**Test Runner:** `pytest tests/test_e2e_pipeline.py` / `python -m pytest tests/test_e2e_pipeline.py`  
**Status:** PASSING (100 / 100 tests, 100% pass rate)

---

## 1. Test Architecture Overview

The testing infrastructure implements an **Opaque-Box 4-Tier Verification Architecture** designed strictly around user requirements (`ORIGINAL_REQUEST.md`) and project specifications (`PROJECT.md`).

```
                    ┌─────────────────────────────────────────────────────────┐
                    │               4-TIER E2E TEST ARCHITECTURE               │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
         ┌────────────────────────┬──────────────┴──────────┬────────────────────────┐
         │                        │                         │                        │
         ▼                        ▼                         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐      ┌──────────────────┐     ┌──────────────────┐
│      TIER 1      │    │      TIER 2      │      │      TIER 3      │     │      TIER 4      │
│ Feature Coverage │    │ Boundary/Corners │      │  Cross-Feature   │     │ Real-World E2E   │
│   (F1 ... F10)   │    │  (Stress/Limits) │      │  (Combinations)  │     │ (Integration)    │
│     52 Tests     │    │     17 Tests     │      │     23 Tests     │     │     8 Tests      │
└──────────────────┘    └──────────────────┘      └──────────────────┘     └──────────────────┘
```

---

## 2. Feature Inventory & Mapping

| Feature # | Feature Name | Description | Test Class in `tests/test_e2e_pipeline.py` | Tier 1 Tests |
|---|---|---|---|---|
| **F1** | Multi-Joint Fault Injection | Simultaneous multi-joint faults (locked 0 & offset angles, limp/free, partial torque) across anterior, middle, posterior joints | `TestTier1_F1_MultiJointFaultInjection` | 6 |
| **F2** | Dynamic Friction & Environments | Anisotropic friction ($\mu_{lat}=0.80/0.95, \mu_{fwd}=0.05$), low-friction ($\mu=0.25$), slopes ($10^\circ$), video capture | `TestTier1_F2_DynamicFrictionAndEnvironments` | 5 |
| **F3** | Multi-Process Benchmark Execution | Execution of controllers C1 (Fixed), C2 (Error-Adaptive), C3 (Shape Recovery), C4 (Oracle), C5 (Proposed AHM), C6 (No-Bypass) | `TestTier1_F3_ControllersAndBenchmarkExecution` | 6 |
| **F4** | Locomotion Metrics Suite | Multi-journal synthesized metrics ($v_{fwd}, R_{perf}, COT_{mech}, E_{total}, X_{drift}, Y_{drift}, Di, T_{adapt}, \tau_{RMS}, J_{kin}$) | `TestTier1_F4_LocomotionMetricsSuite` | 5 |
| **F5** | Statistical Significance Tests | Kruskal-Wallis, Mann-Whitney U, Holm-Bonferroni correction, Cliff's delta effect sizes, Bootstrap 95% CIs | `TestTier1_F5_StatisticalSignificanceTesting` | 5 |
| **F6** | 5-Module Isolated Ablation | Isolated evaluation of Hormone Diffusion ($D_h$), Hill Kinetics ($m$), Bypass Coupling ($K_B$), Frequency Mod ($g_w$), Steering Bias ($\gamma$) | `TestTier1_F6_FiveModuleIsolatedAblation` | 5 |
| **F7** | 2D Parameter Sensitivity Sweeps | 2D parameter grid sweeps ($D_h \times \alpha_h$, $K_h \times m$), JSON dataset schemas, monotonicity | `TestTier1_F7_ParameterSensitivitySweeps` | 5 |
| **F8** | Publication Figures (300+ DPI) | High-resolution publication figures (time-series, wave heatmaps, boxplots, radar charts, transition curves) | `TestTier1_F8_PublicationFigures` | 5 |
| **F9** | Q1 LaTeX Manuscript | Formatted manuscript generation (`manuscript.tex`), equations, section hierarchy, table/figure synchronization | `TestTier1_F9_LaTeXManuscriptFormat` | 5 |
| **F10** | Comprehensive Bibliography | Peer-reviewed citations, author resolution, in-text citation key matching, zero dangling references | `TestTier1_F10_BibliographyAndCitations` | 5 |

---

## 3. Tier Methodology Breakdown

### Tier 1: Feature Coverage (52 Tests)
Validates the standard happy-path behavior, expected numerical outputs, mathematical transformations, and interface contracts for each assigned feature independently.

### Tier 2: Boundary & Corner Cases (17 Tests)
Probes system robustness against extreme inputs and failure modes:
- Zero-length & empty trajectory logs
- Division-by-zero protection under zero distance traveled ($d=0$)
- Extreme friction extremes ($\mu \to 0$ and $\mu \gg 1$)
- Full-body catastrophe (all 8 joints locked simultaneously)
- Boundary joint lesions (J0 head / J7 tail with no two-hop neighbors)
- Diffusion bounds ($D_h = 0.0$ complete isolation vs $D_h = 1.0$ instant equalization)
- Hill cooperativity limits ($m=1.0$ linear vs $m=20.0$ step function)
- Joint limit clipping ($[-\pi/3, +\pi/3]$ rad)
- Single-sample Bootstrap CI & zero-variance statistical arrays
- Out-of-bounds joint indexing validation

### Tier 3: Cross-Feature Combinations (23 Tests)
Evaluates pairwise and multi-way interactions across subsystems:
- **Fault Mode $\times$ Controller Matrix**: $3 \text{ fault types} \times 6 \text{ controllers} = 18$ parameterized simulation test cases.
- **Friction Regime $\times$ Bypass Coupling**: Low-friction terrain combined with middle-joint failure and two-hop bypass activation.
- **Statistical Significance $\times$ Sample Size**: Performance across $N \in [5, 10, 25]$ with step-down Holm-Bonferroni correction.
- **Dual Ablation ($D_h=0 \land K_B=0$)**: Simultaneous deactivation of spatial diffusion and bypass coupling.
- **Sensor Noise $\times$ Hill Gating**: Gaussian sensory noise ($\sigma = 0.08$ rad) filtered by Hill sigmoidal thresholding ($K_h=0.65, m=4.0$).
- **Metrics $\times$ LaTeX Table Roundtrip**: Automatic tabular formatting from metrics dictionary.

### Tier 4: Real-World Locomotion Scenarios (8 Tests)
Executes complete end-to-end integration pipelines:
- `test_tier4_s01`: Full Simulation $\to$ Metrics Calculation $\to$ Statistical Comparison $\to$ Table Export.
- `test_tier4_s02`: Physical Lesion Injection $\to$ Proprioceptive Mismatch $\to$ Hormone Secretion $\to$ Hill Gating $\to$ Dynamic Bypass $\to$ Propulsion Recovery.
- `test_tier4_s03`: 5-Module Isolated Ablation Pipeline ($D_h, m, K_B, g_w, \gamma$).
- `test_tier4_s04`: 2D Sensitivity Grid Sweeps & JSON Data Pipeline.
- `test_tier4_s05`: Publication Figure & Table Delivery Verification.
- `test_tier4_s06`: LaTeX Manuscript & Bibliography Synchronization Verification.
- `test_tier4_s07`: Multi-Seed Reproducibility Verification.
- `test_tier4_s08`: Cumulative Energy Monotonicity and Conservation.

---

## 4. Execution & Coverage Thresholds

- **Total Test Count:** 100
- **Passing Tests:** 100 (100%)
- **Failing Tests:** 0
- **Execution Time:** ~6.0 – 7.5 seconds
- **PyBullet Mode:** Direct headless (`p.DIRECT`) for fast, deterministic CI/CD execution.

### How to Run:
```bash
# Run all E2E tests with verbose output
python -m pytest tests/test_e2e_pipeline.py -v

# Run a specific tier
python -m pytest tests/test_e2e_pipeline.py -k "TestTier1" -v
python -m pytest tests/test_e2e_pipeline.py -k "TestTier2" -v
python -m pytest tests/test_e2e_pipeline.py -k "TestTier3" -v
python -m pytest tests/test_e2e_pipeline.py -k "TestTier4" -v
```
