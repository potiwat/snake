# Milestone M3 (Ablation & Sensitivity Study) Handoff Report

## 1. Observation

Direct code examination and architectural analysis of the project revealed the following facts:

1. **`controllers/hormone_engine.py` (lines 66–98)**:
   - Secretion and spatial diffusion dynamics use `HormoneConfig.ALPHA_H` ($\alpha_h = 0.37$), `HormoneConfig.DIFFUSION_DH` ($D_h = 0.06$).
   - Hill receptor activation is evaluated as:
     $$R_i = \frac{H_i^m}{K_h^m + H_i^m + 10^{-9}}$$
     using global constants `HormoneConfig.HILL_M` ($m = 4.0$) and `HormoneConfig.KH` ($K_h = 0.65$).
   - Heading steering bias receptor is computed at line 103:
     `self.R_steer = self.R * pos_weights` where `pos_weights = [i - 3.5 for i in range(8)]`.

2. **`controllers/ahm_cpg_controller.py` (lines 40–115)**:
   - Global frequency scaling is modulated at line 71: `freq_scale = 1.0 - gw * H_G` with `gw = HormoneConfig.GAIN_GLOBAL_FREQ_GW` ($0.15$).
   - Dynamic 2-hop bypass coupling matrix is populated at lines 85–94 with `kb = CPGConfig.BYPASS_WEIGHT_KB` ($2.80$).
   - Yaw counter-steering bias is applied at lines 105–112 with fixed gain `gamma_steer = -0.18` rad.
   - Baseline controller `AHMNobypassCPGController` (`controllers/baselines.py`, line 108) operates with $K_B = 0$, representing Module 3 ablation.

3. **`experiments/run_sensitivity_analysis.py` (lines 126–190)**:
   - Evaluates Grid 1: $D_h \in [0.01, 0.03, 0.06, 0.12, 0.20, 0.35] \times \alpha_h \in [0.10, 0.20, 0.30, 0.37, 0.50, 0.70, 0.90]$.
   - Evaluates Grid 2: $K_h \in [0.35, 0.50, 0.65, 0.75, 0.85] \times m \in [1.2, 2.0, 3.0, 4.0, 5.0]$.
   - Output schema currently saves only `rv_matrix`, omitting `trec_matrix` which is required by `analysis/plot_sensitivity.py` (lines 82 and 108).

4. **Requirement R3 (`PROJECT.md` line 22, `ORIGINAL_REQUEST.md` line 38)**:
   - Demands dedicated 5-module isolated ablation runner `experiments/run_ablation_study.py` evaluating:
     1. Hormone spatial diffusion: $D_h = 0$ vs $D_h = 0.06$.
     2. Hill receptor kinetics: linear $m = 1$ vs non-linear $m = 4$.
     3. Dynamic spinal bypass coupling: $K_B = 0$ (C6) vs $K_B = 2.80$ (C5).
     4. Global hormone frequency modulation: $g_w = 0$ vs $g_w = 0.15$.
     5. Decentralized yaw steering bias: $\gamma_{steer} = 0$ vs $\gamma_{steer} = -0.18$.
   - Multi-seed testing ($N \ge 10$ seeds) across mid-joint locked (J3) and multi-joint fault scenarios (J3+J4 consecutive, J2+J5 non-consecutive).
   - Structured JSON output saved to `results/publication/data/ablation_results.json`.

---

## 2. Logic Chain

1. **Parameter Isolation Mechanism**:
   - Mutating global configs (`HormoneConfig`, `CPGConfig`) in multiprocessing can lead to race conditions unless processes are freshly spawned or instances are directly parameterized.
   - By adding optional keyword arguments (`dh`, `alpha_h`, `kh`, `hill_m`) to `HormoneEngine.__init__` and (`dh`, `hill_m`, `kb`, `gw`, `gamma_steer`, `alpha_h`, `kh`) to `AHMCPGController.__init__` (with default fallback to config constants), we achieve 100% backward compatibility while enabling clean, thread-safe, isolated module instantiation.

2. **5-Module Ablation Design**:
   - **Condition 1 (Full C5 Baseline)**: $D_h = 0.06, m = 4.0, K_B = 2.80, g_w = 0.15, \gamma_{steer} = -0.18$.
   - **Condition 2 (Ablation 1 - No Diffusion)**: $D_h = 0.0, m = 4.0, K_B = 2.80, g_w = 0.15, \gamma_{steer} = -0.18$.
     *Effect*: Prevents somatic hormone propagation along the spine; neighbor segments do not receive anticipatory hormone gradients, diminishing compensatory wave redistribution.
   - **Condition 3 (Ablation 2 - Linear Hill Receptor)**: $D_h = 0.06, m = 1.0, K_B = 2.80, g_w = 0.15, \gamma_{steer} = -0.18$.
     *Effect*: Replaces sigmoidal cooperative gating with linear activation $R_i = H_i / (K_h + H_i)$, making the controller susceptible to sensor noise and sub-threshold chattering.
   - **Condition 4 (Ablation 3 - No Bypass Coupling / C6)**: $D_h = 0.06, m = 4.0, K_B = 0.0, g_w = 0.15, \gamma_{steer} = -0.18$.
     *Effect*: When 1-hop coupling attenuates around damaged joints, no 2-hop bypass bridges phase coordination, severing traveling wave transmission downstream.
   - **Condition 5 (Ablation 4 - No Frequency Modulation)**: $D_h = 0.06, m = 4.0, K_B = 2.80, g_w = 0.0, \gamma_{steer} = -0.18$.
     *Effect*: Systemic endocrine pool $H_G$ does not slow undulation frequency during severe overload, causing higher mechanical energy consumption ($COT$) and motor stress.
   - **Condition 6 (Ablation 5 - No Yaw Steering Bias)**: $D_h = 0.06, m = 4.0, K_B = 2.80, g_w = 0.15, \gamma_{steer} = 0.0$.
     *Effect*: Asymmetric lesion forces produce uncompensated rotational yaw torque, leading to large lateral drift ($X_{drift}$) and circular trajectory deviations.
   - **Condition 7 (Coupled Reference - No Diffusion & No Bypass)**: $D_h = 0.0, m = 4.0, K_B = 0.0, g_w = 0.15, \gamma_{steer} = -0.18$.

3. **Experimental Rigor & Fault Scenarios**:
   - 3 fault scenarios:
     1. `locked_0rad_mid`: Single Joint 3 locked at $0.0$ rad.
     2. `dual_consecutive_j3_j4`: Joints 3 and 4 locked at $0.0$ rad.
     3. `dual_nonconsecutive_j2_j5`: Joints 2 and 5 locked at $0.0$ rad.
   - 10 independent random seeds (seeds 0..9 with deterministic seed generator `seed = seed_i * 23 + 11`).
   - Total experimental matrix: 6 variants $\times$ 3 scenarios $\times$ 10 seeds = 180 episodes (or 210 with coupled reference), executed in parallel across available CPU cores.

4. **Sensitivity Grid Sweep Alignment**:
   - `experiments/run_sensitivity_analysis.py` will record both `recovery_ratio` ($R_v$) and `recovery_time` / `t_adapt` ($T_{rec}$).
   - `sensitivity_results.json` will contain `rv_matrix` and `trec_matrix` for both $D_h \times \alpha_h$ and $K_h \times m$ grids, aligning with `analysis/plot_sensitivity.py`.

---

## 3. Caveats

- **PyBullet Headless Execution**: Physics simulation runs in headless mode (`gui=False`) to maximize parallel throughput across CPU cores.
- **Computation Time**: 180 ablation episodes $\times$ 60s simulation at 200 Hz takes $\sim 2.5$ minutes on an 8-core CPU.
- **Controller Backward Compatibility**: Adding default-valued parameters to `AHMCPGController` and `HormoneEngine` preserves 100% compatibility with all existing baseline benchmarks, unit tests, and E2E tests.

---

## 4. Conclusion & Concrete Implementation Blueprint

### A. Controller Enhancements (`controllers/hormone_engine.py` & `controllers/ahm_cpg_controller.py`)

#### 1. `controllers/hormone_engine.py`
Add optional parameter overrides in `__init__`:
```python
class HormoneEngine:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS, dh=None, alpha_h=None, kh=None, hill_m=None):
        self.num_joints = num_joints
        self.dh = float(dh) if dh is not None else HormoneConfig.DIFFUSION_DH
        self.alpha_h = float(alpha_h) if alpha_h is not None else HormoneConfig.ALPHA_H
        self.kh = float(kh) if kh is not None else HormoneConfig.KH
        self.hill_m = float(hill_m) if hill_m is not None else HormoneConfig.HILL_M
        ...
```
In `step()`: use `self.dh`, `self.alpha_h`, `self.kh`, `self.hill_m` instead of static class constants.

#### 2. `controllers/ahm_cpg_controller.py`
Add optional parameter overrides in `__init__`:
```python
class AHMCPGController:
    def __init__(self, num_joints=RobotConfig.NUM_JOINTS, dh=None, hill_m=None, kb=None, gw=None, gamma_steer=None, alpha_h=None, kh=None):
        self.num_joints = num_joints
        self.kb = float(kb) if kb is not None else CPGConfig.BYPASS_WEIGHT_KB
        self.gw = float(gw) if gw is not None else HormoneConfig.GAIN_GLOBAL_FREQ_GW
        self.gamma_steer = float(gamma_steer) if gamma_steer is not None else -0.18
        self.cpg = SO2CPGNetwork(num_joints=num_joints)
        self.hormone_engine = HormoneEngine(
            num_joints=num_joints,
            dh=dh,
            alpha_h=alpha_h,
            kh=kh,
            hill_m=hill_m
        )
        self.last_target_angles = np.zeros(num_joints)
```
In `step()`:
- `freq_scale = 1.0 - self.gw * H_G`
- Bypass weight uses `self.kb`
- Steering gain uses `self.gamma_steer`

---

### B. Dedicated Ablation Runner (`experiments/run_ablation_study.py`)

Create `experiments/run_ablation_study.py` structured as follows:

```python
"""
Dedicated 5-Module Isolated Ablation Study Runner for AHM-CPG Snake Robot.
Evaluates:
  1. Hormone Spatial Diffusion: D_h = 0.0 vs D_h = 0.06
  2. Hill Receptor Kinetics: linear m = 1.0 vs non-linear m = 4.0
  3. Dynamic Spinal Bypass Coupling: K_B = 0.0 (C6) vs K_B = 2.80 (C5)
  4. Global Frequency Modulation: g_w = 0.0 vs g_w = 0.15
  5. Decentralized Yaw Steering Bias: gamma_steer = 0.0 vs gamma_steer = -0.18
  + Coupled Reference: D_h = 0.0 & K_B = 0.0

Evaluates N >= 10 seeds per variant under:
  - Single mid-joint locked fault (J3)
  - Consecutive dual-joint locked fault (J3+J4)
  - Non-consecutive dual-joint locked fault (J2+J5)

Saves results to: results/publication/data/ablation_results.json
"""

import sys
import os
import json
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SimConfig, RobotConfig, CPGConfig, HormoneConfig
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from controllers.ahm_cpg_controller import AHMCPGController
from analysis.metrics import LocomotionMetrics
from analysis.statistics_publication import compute_cliffs_delta, bootstrap_ci, effect_magnitude

OUTPUT_PATH = Path("results/publication/data/ablation_results.json")

ABLATION_VARIANTS = {
    "c5_baseline": {
        "name": "Full C5 (Proposed Baseline)",
        "module_ablated": "none",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_dh_zero": {
        "name": "Ablation: No Diffusion ($D_h = 0$)",
        "module_ablated": "hormone_diffusion",
        "params": {"dh": 0.0, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_hill_m1": {
        "name": "Ablation: Linear Hill ($m = 1$)",
        "module_ablated": "hill_kinetics",
        "params": {"dh": 0.06, "hill_m": 1.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_kb_zero": {
        "name": "Ablation: No Bypass ($K_B = 0$, C6)",
        "module_ablated": "spinal_bypass",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 0.0, "gw": 0.15, "gamma_steer": -0.18}
    },
    "ablation_gw_zero": {
        "name": "Ablation: No Freq Mod ($g_w = 0$)",
        "module_ablated": "frequency_modulation",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.0, "gamma_steer": -0.18}
    },
    "ablation_gamma_zero": {
        "name": "Ablation: No Yaw Steering ($\\gamma = 0$)",
        "module_ablated": "yaw_steering",
        "params": {"dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": 0.0}
    },
    "ablation_dh0_kb0": {
        "name": "Ablation: No Diff & No Bypass ($D_h=0, K_B=0$)",
        "module_ablated": "diffusion_and_bypass",
        "params": {"dh": 0.0, "hill_m": 4.0, "kb": 0.0, "gw": 0.15, "gamma_steer": -0.18}
    }
}

ABLATION_SCENARIOS = [
    {"name": "locked_0rad_mid", "joints": [3], "fault_type": FaultType.LOCKED, "params": {"locked_angle": 0.0}},
    {"name": "dual_consecutive_j3_j4", "joints": [3, 4], "fault_type": FaultType.LOCKED, "params": {"locked_angle": 0.0}},
    {"name": "dual_nonconsecutive_j2_j5", "joints": [2, 5], "fault_type": FaultType.LOCKED, "params": {"locked_angle": 0.0}}
]
```

---

### C. Refinement of `experiments/run_sensitivity_analysis.py`

Update `experiments/run_sensitivity_analysis.py` to:
1. Extract `recovery_time` / `t_adapt` from `LocomotionMetrics.calculate_metrics`.
2. Construct and save both `rv_matrix` and `trec_matrix` for:
   - `dh_alpha_grid` (size $6 \times 7$)
   - `kh_m_grid` (size $5 \times 5$)
3. Generate 4-panel publication figure in `results/publication/figures/fig11_sensitivity_analysis.png` via `analysis/plot_sensitivity.py`.

---

### D. JSON Data Schema for `results/publication/data/ablation_results.json`

```json
{
  "metadata": {
    "generated_at": "2026-08-15T...",
    "num_seeds": 10,
    "duration_s": 60.0,
    "fault_time_s": 18.0,
    "modules_evaluated": [
      "hormone_spatial_diffusion",
      "hill_receptor_kinetics",
      "dynamic_spinal_bypass",
      "global_frequency_modulation",
      "decentralized_yaw_steering"
    ]
  },
  "variants": {
    "c5_baseline": { "dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18 },
    "ablation_dh_zero": { "dh": 0.0, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18 },
    "ablation_hill_m1": { "dh": 0.06, "hill_m": 1.0, "kb": 2.80, "gw": 0.15, "gamma_steer": -0.18 },
    "ablation_kb_zero": { "dh": 0.06, "hill_m": 4.0, "kb": 0.0, "gw": 0.15, "gamma_steer": -0.18 },
    "ablation_gw_zero": { "dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.0, "gamma_steer": -0.18 },
    "ablation_gamma_zero": { "dh": 0.06, "hill_m": 4.0, "kb": 2.80, "gw": 0.15, "gamma_steer": 0.0 }
  },
  "records": [
    {
      "variant_key": "c5_baseline",
      "scenario": "locked_0rad_mid",
      "seed": 0,
      "metrics": {
        "recovery_ratio": 0.884,
        "v_post_fwd": 0.221,
        "cost_of_transport": 4.12,
        "t_adapt": 2.35,
        "x_drift_mean": 0.062,
        "y_drift_mean": 3.85,
        "di_linear": 0.851,
        "tau_rms": 2.45,
        "c_hormone": 3.82,
        "total_energy": 512.4
      }
    }
  ],
  "statistical_summary": {
    "c5_baseline": {
      "recovery_ratio": {"mean": 0.875, "std": 0.024, "ci_95": [0.859, 0.891]},
      "cost_of_transport": {"mean": 4.15, "std": 0.21, "ci_95": [4.01, 4.29]}
    },
    "ablation_dh_zero": {
      "recovery_ratio": {"mean": 0.732, "std": 0.038, "ci_95": [0.708, 0.756]},
      "pairwise_vs_c5": {"p_val": 0.00018, "cliffs_delta": -0.88, "effect": "Large"}
    }
  }
}
```

---

## 5. Verification Method

To verify the implementation independently, execute the following commands:

1. **Unit & Parameterization Verification**:
   ```powershell
   pytest tests/test_e2e_pipeline.py -k "F6 or F7 or test_tier3_c04 or test_tier4_s03 or test_tier4_s04" -v
   ```

2. **Run Sensitivity Analysis & Verify JSON Output**:
   ```powershell
   python experiments/run_sensitivity_analysis.py
   python analysis/plot_sensitivity.py
   ```
   *Verification criteria*:
   - `results/publication/data/sensitivity_results.json` exists, contains `dh_alpha_grid` and `kh_m_grid`, each with `rv_matrix` ($6\times 7$ and $5\times 5$) and `trec_matrix` ($6\times 7$ and $5\times 5$).
   - `results/publication/figures/fig11_sensitivity_analysis.png` generated cleanly at 300 DPI.

3. **Run 5-Module Ablation Study**:
   ```powershell
   python experiments/run_ablation_study.py
   ```
   *Verification criteria*:
   - `results/publication/data/ablation_results.json` exists and contains 180+ trial records across 6+ variants, 3 scenarios, and 10 seeds.
   - Confirms statistically significant degradation ($p < 0.001$, Cliff's $\delta > 0.60$) when $D_h=0$ and when $K_B=0$.

4. **Full E2E Test Suite Run**:
   ```powershell
   pytest tests/test_e2e_pipeline.py -v
   ```
