# CPG Locomotion Controllers & Video Rendering Invariants

This rule defines mandatory technical guidelines for CPG fault-tolerant locomotion controllers, plot normalization, OpenCV video canvas rendering, and Q1 publication standards in snake robot simulation projects.

---

## 1. Low-Pass EMA Error Filtering for CPG Adaptation
- **Context**: Real-time position tracking errors `|q_target - q_actual|` naturally fluctuate during healthy undulation due to ground friction and mechanical inertia.
- **Invariant**: Never use raw, unfiltered tracking error directly for thresholding or amplitude switching in CPG controllers. Always apply an Exponential Moving Average (EMA) low-pass filter:
  ```python
  self.filtered_errors = 0.92 * self.filtered_errors + 0.08 * raw_errors
  ```
- **Reason**: Prevents high-frequency false-trigger chattering during un-damaged locomotion.

---

## 2. Hormone Signal Normalization ($H_i \in [0, 1]$)
- **Context**: Local hormone concentration $H_i$ varies across simulation environments.
- **Invariant**: All hormone plots, heatmaps, and video overlays must normalize $H_i$ to $[0, 1]$:
  ```python
  H_max = np.max(H) if np.max(H) > 0 else 1.0
  H_norm = np.clip(H / H_max, 0.0, 1.0)
  ```
- **Axis Bounds**: Always set explicit Y-axis limits (`ax.set_ylim(-0.02, 1.05)`) to prevent line overlays from bleeding outside subplot bounding boxes.

---

## 3. Strict Y-Coordinate Pixel Clamping in OpenCV Video Panels
- **Context**: In OpenCV video frame rendering, converting raw data values (e.g. speed $v_{xy}$, joint angles $q$, hormone $H$) to Y-pixel coordinates can produce out-of-bounds numbers if values exceed nominal scales.
- **Invariant**: Always clamp data values before computing Y-pixel coordinates:
  ```python
  def v_to_y(v_val):
      v_c = np.clip(v_val, 0.0, 0.60)  # Clamp strictly to subpanel range
      return int(y3 + h3 - 12 - (v_c / 0.60) * (h3 - 24))
  ```
- **Reason**: Guarantees that plot lines never shoot out or overflow into adjacent subpanels above or below.

---

## 4. Causal 20-Sample Moving Average (MA20) for Locomotion Speed
- **Context**: Raw velocity signals $v_{xy}(t)$ contain high-frequency contact chatter.
- **Invariant**: Smooth real-time velocity arrays in video renderers using a 20-sample causal sliding window moving average with initial cumulative padding:
  ```python
  window_size = 20
  if len(v_arr) >= window_size:
      kernel = np.ones(window_size) / window_size
      v_valid = np.convolve(v_arr, kernel, mode='valid')
      initial_pad = [np.mean(v_arr[:idx+1]) for idx in range(window_size - 1)]
      v_smooth = np.concatenate([initial_pad, v_valid])
  ```

---

## 5. Q1 Bio-Inspired Publication Standards (*Bioinspiration & Biomimetics*, IOP)
- **Target Journal**: *Bioinspiration & Biomimetics* (IOPscience, Q1)
- **Scope**: High-fidelity simulation & theoretical bio-inspired control modeling (does not require physical hardware when physics simulation is rigorous, multi-seed validated, and theoretically grounded).
- **Tuned Parameter Baseline**:
  - $g_w = 0.15$ (Global frequency scaling)
  - $g_a = 0.15$ (Amplitude reduction factor for failed joint)
  - $g_n = 0.95$ (Neighbor compensation boost)
  - $\sigma = 1.42$ (Spatial neighbor decay parameter)
  - $\gamma_{\text{steer}} = -0.18$ (Decentralized yaw steering bias compensation)
  - $K_0 \to 0.001$ (Decoupled lesion joint state)
  - $K_B = 2.80 \cdot R_i$ (Dynamic spinal bypass coupling weight)
  - Boundary Condition: Zero-flux at spatial diffusion grid spacing $\Delta x = 1$
- **Benchmark Performance Anchor**:
  - Proposed AHM-CPG (C5) achieves statistically significant speed recovery ($\eta_{\text{rec}} = 85.8\%$ under severe lesion regimes) and up to $74.2\%$ lateral drift reduction ($p < 0.001$, Wilcoxon signed-rank, Cliff's $\delta > 0.85$, Cohen's $d_z > 2.5$).

---

## 6. Multiprocessing Pool Sizing & Resource Safety
- **Context**: Running parallel PyBullet physics episodes (e.g. 480 benchmark + 420 generalization runs) can overwhelm system CPU threads if unconstrained.
- **Invariant**: Always calculate worker pool size reserving at least 1 core for OS/background processes:
  ```python
  num_procs = min(8, max(1, cpu_count() - 1))
  ```
- **Data Safety**: Worker processes must return structured metric dictionaries to memory; master process writes the consolidated results atomically to JSON to prevent file lock collisions.

---

## 7. Mandatory Q1 Publication Deliverables Checklist
Every publication-grade simulation release must deliver:
1. **Simulation Datasets**: Factorial benchmarks ($N \ge 10$ seeds), generalization regimes (friction transitions, inclines, sensor noise, mass scaling), isolated 5-module ablations ($D_h, m, K_B, g_w, \gamma_{\text{steer}}$), and 200 Hz detail histories.
2. **Statistical Rigor**: Matched-pair Wilcoxon signed-rank tests, Mann-Whitney U, step-down Holm-Bonferroni correction, Cohen's $d_z$, Cliff's $\delta$, and 95% bootstrap confidence intervals.
3. **Publication Figures**: 14 high-resolution (300+ DPI PNG and vector PDF) figures styled for IOPscience.
4. **Complete LaTeX Package**: `manuscript_bioinspiration.tex` (`iopart.cls`), `references.bib` (40+ peer-reviewed citations), and standalone TeX tables.
