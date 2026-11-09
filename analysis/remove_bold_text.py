import os
import re

MANUSCRIPT_GEN_PATH = r"e:/agy/snake - Copy/analysis/build_18page_manuscript.py"

with open(MANUSCRIPT_GEN_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Abstract
text = text.replace(r"\textbf{Local-Global Artificial Hormone-Gated Central Pattern Generator (AHM-CPG)}", "local-global artificial hormone-gated central pattern generator (AHM-CPG)")
text = text.replace(r"\textbf{Local-Global Artificial Hormone-Gated CPG (AHM-CPG)}", "local-global artificial hormone-gated central pattern generator (AHM-CPG)")

# 2. Introduction
text = text.replace(r"\item \textbf{Dual Time-Scale Neuro-Endocrine Architecture and Analytical Boundedness}:", r"\item \textit{Dual time-scale neuro-endocrine architecture and analytical boundedness}:")
text = text.replace(r"\item \textbf{Dynamic Multi-Hop Spinal Bypass with Phase-Locking Stability}:", r"\item \textit{Dynamic multi-hop spinal bypass with phase-locking stability}:")
text = text.replace(r"\item \textbf{Decentralized Curvature Neutralization and Actuator Thermal Protection}:", r"\item \textit{Decentralized curvature neutralization and actuator thermal protection}:")
text = text.replace(r"\item \textbf{Factorial Benchmark Evaluation and Biological Reciprocity}:", r"\item \textit{Factorial benchmark evaluation and biological reciprocity}:")

# 3. Figure 1 caption
text = text.replace(r"\textbf{Stage 1}", "Stage 1")
text = text.replace(r"\textbf{Stage 2}", "Stage 2")
text = text.replace(r"\textbf{Stage 3}", "Stage 3")
text = text.replace(r"\textbf{Stage 4}", "Stage 4")

# 4. Proposition 1 and Phase-locking stability
text = text.replace(r"\noindent\textbf{Proposition 1 (Boundedness and Invariant State Space).}", r"\noindent\textit{Proposition 1 (Boundedness and Invariant State Space).}")
text = text.replace(r"\noindent\textbf{Phase-Locking Stability Under Dynamic Bypass.}", r"\noindent\textit{Phase-Locking Stability Under Dynamic Bypass.}")

# 5. Controller definitions in Section 4
text = text.replace(r"\item \textbf{C1 (Open-Loop Fixed CPG)}:", r"\item \textit{C1 (Open-Loop Fixed CPG)}:")
text = text.replace(r"\item \textbf{C2 (Error-Adaptive CPG)}:", r"\item \textit{C2 (Error-Adaptive CPG)}:")
text = text.replace(r"\item \textbf{C3 (Heuristic Shape Recovery~\cite{elsayed2021})}:", r"\item \textit{C3 (Heuristic Shape Recovery~\cite{elsayed2021})}:")
text = text.replace(r"\item \textbf{C4 (Oracle Fault-Aware CPG)}:", r"\item \textit{C4 (Oracle Fault-Aware CPG)}:")
text = text.replace(r"\item \textbf{C5 (Proposed AHM-CPG)}:", r"\item \textit{C5 (Proposed AHM-CPG)}:")
text = text.replace(r"\item \textbf{C6 (AHM-CPG without Dynamic Bypass)}:", r"\item \textit{C6 (AHM-CPG without Dynamic Bypass)}:")

# 6. Metrics definitions
text = text.replace(r"\item \textbf{Forward Locomotion Velocity ($v_{\text{fwd}}$)}:", r"\item \textit{Forward Locomotion Velocity ($v_{\text{fwd}}$)}:")
text = text.replace(r"\item \textbf{Speed Recovery Ratio ($\eta_{\text{rec}}$)}:", r"\item \textit{Speed Recovery Ratio ($\eta_{\text{rec}}$)}:")
text = text.replace(r"\item \textbf{Dynamic Adaptation Latency ($T_{\text{adapt}}$)}:", r"\item \textit{Dynamic Adaptation Latency ($T_{\text{adapt}}$)}:")
text = text.replace(r"\item \textbf{Specific Cost of Transport ($\text{COT}$)}:", r"\item \textit{Specific Cost of Transport ($\text{COT}$)}:")
text = text.replace(r"\item \textbf{Total Mechanical Energy ($E_{\text{total}}$)}:", r"\item \textit{Total Mechanical Energy ($E_{\text{total}}$)}:")
text = text.replace(r"\item \textbf{Directional Heading Deviation ($\Delta\theta_{\text{yaw}}$)}:", r"\item \textit{Directional Heading Deviation ($\Delta\theta_{\text{yaw}}$)}:")
text = text.replace(r"\item \textbf{Joint Torque Root-Mean-Square ($\tau_{\text{RMS}}$)}:", r"\item \textit{Joint Torque Root-Mean-Square ($\tau_{\text{RMS}}$)}:")
text = text.replace(r"\item \textbf{Actuator Thermal Dissipation Stress ($\mathcal{E}_{\text{thermal}}$)}:", r"\item \textit{Actuator Thermal Dissipation Stress ($\mathcal{E}_{\text{thermal}}$)}:")

# 7. Body text emphasis
text = text.replace(r"\textbf{$86.4\%$ reduction in actuator thermal stress}", r"$86.4\%$ reduction in actuator thermal stress")
text = text.replace(r"\textbf{86.4\% reduction in actuator thermal stress}", r"86.4\% reduction in actuator thermal stress")
text = text.replace(r"\textbf{-48.9\%}", r"-48.9\%")
text = text.replace(r"\textbf{48.9\%}", r"48.9\%")

# 8. Discussion bullets
text = text.replace(r"\item \textbf{Allosteric Receptor Cooperativity as a Biological Noise Filter}:", r"\item \textit{Allosteric Receptor Cooperativity as a Biological Noise Filter}:")
text = text.replace(r"\item \textbf{Propriospinal Relay Bridges for Phase-Locked Wave Continuity}:", r"\item \textit{Propriospinal Relay Bridges for Phase-Locked Wave Continuity}:")
text = text.replace(r"\item \textbf{Self-Limiting Homeostatic Equilibrium}:", r"\item \textit{Self-Limiting Homeostatic Equilibrium}:")

# 9. Sensitivity regimes
text = text.replace(r"\item \textbf{Regime I: Sub-Threshold Hypo-Reactive Zone ($K_h > 0.65$ or $m < 2$)}:", r"\item \textit{Regime I: Sub-Threshold Hypo-Reactive Zone ($K_h > 0.65$ or $m < 2$)}:")
text = text.replace(r"\item \textbf{Regime II: Resilient Homeostatic Operating Plateau ($K_h \in [0.25, 0.55], m \in [4, 8], \alpha_h/d_0 \in [4, 10]$)}:", r"\item \textit{Regime II: Resilient Homeostatic Operating Plateau ($K_h \in [0.25, 0.55], m \in [4, 8], \alpha_h/d_0 \in [4, 10]$)}:")
text = text.replace(r"\item \textbf{Regime III: Hyper-Sensitive Chatter Instability ($K_h < 0.20, \alpha_h/d_0 > 15$)}:", r"\item \textit{Regime III: Hyper-Sensitive Chatter Instability ($K_h < 0.20, \alpha_h/d_0 > 15$)}:")

# 10. Failure cases & Roadmap
text = text.replace(r"\item \textbf{Extreme Asymmetric Locked Offset Lesions}:", r"\item \textit{Extreme Asymmetric Locked Offset Lesions}:")
text = text.replace(r"\item \textbf{Concurrent Non-Adjacent Double Faults}:", r"\item \textit{Concurrent Non-Adjacent Double Faults}:")
text = text.replace(r"\item \textbf{Isotropic Low-Friction Ground ($\mu_{\text{lat}} \approx \mu_{\text{fwd}} \le 0.05$)}:", r"\item \textit{Isotropic Low-Friction Ground ($\mu_{\text{lat}} \approx \mu_{\text{fwd}} \le 0.05$)}:")
text = text.replace(r"\item \textbf{Computational Footprint and Communication Overhead}:", r"\item \textit{Computational Footprint and Communication Overhead}:")
text = text.replace(r"\item \textbf{Feedback Delay and Jitter Tolerance}:", r"\item \textit{Feedback Delay and Jitter Tolerance}:")
text = text.replace(r"\item \textbf{Extension to 3D Spatial Locomotion}:", r"\item \textit{Extension to 3D Spatial Locomotion}:")
text = text.replace(r"\item \textbf{Autonomous Parameter Optimization}:", r"\item \textit{Autonomous Parameter Optimization}:")

with open(MANUSCRIPT_GEN_PATH, "w", encoding="utf-8") as f:
    f.write(text)

print("[SUCCESS] Removed non-academic bold formatting from body text and replaced with standard academic italicization!")
