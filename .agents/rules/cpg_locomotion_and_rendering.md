# CPG Locomotion Controllers & Video Rendering Invariants

This rule defines mandatory technical guidelines for CPG fault-tolerant locomotion controllers, plot normalization, and OpenCV video canvas rendering in snake robot simulation projects.

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

---

## 5. IEEE Access Publication Invariants & Tuned AHM-CPG Baseline
- **Target Journal**: IEEE Access
- **Tuned Parameter Baseline**:
  - $g_w = 0.15$ (Global frequency scaling)
  - $g_a = 0.50$ (Amplitude reduction gain)
  - $g_n = 0.95$ (Neighbor compensation boost)
  - $K_0 \to 0.001$ (Isolated dead joint CPG state)
  - $K_B = 2.80 \cdot R_i$ (Dynamic bypass coupling weight)
  - Boundary Condition: Zero-flux at grid spacing $\Delta x = 1$
- **Benchmark Performance Anchor**:
  - Proposed AHM-CPG (C5) achieves lowest performance loss: $L_{\text{AUC}} = 0.232$ [0.205, 0.261].
  - Kruskal-Wallis non-parametric tests: $L_{\text{AUC}}$ ($H = 48.99, p < 0.001$), $R_v$ ($H = 29.14, p < 0.001$), $T_{\text{rec}}$ ($H = 36.03, p < 0.001$).

  ```
