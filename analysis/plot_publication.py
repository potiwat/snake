"""
Publication-Quality Figure Generator (10 Figures for Journal Paper).
All figures are 300 DPI with IEEE-compatible styling.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SimConfig

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec

# ── Publication Style ─────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
})

COLORS = {
    'C1': '#e74c3c', 'C2': '#e67e22', 'C3': '#f39c12',
    'C4': '#9b59b6', 'C5': '#27ae60', 'C6': '#2980b9'
}
LABELS = {
    'C1': 'C1: Fixed CPG',
    'C2': 'C2: Error-Adaptive',
    'C3': 'C3: Shape Recovery',
    'C4': 'C4: Oracle Fault-Aware',
    'C5': 'C5: Proposed AHM-CPG',
    'C6': 'C6: AHM w/o Bypass'
}

DATA_DIR = "results/publication/data"
FIG_DIR = "results/publication/figures"


def load_detail(ctrl):
    fpath = os.path.join(DATA_DIR, "detail_histories", f"{ctrl.lower()}_locked_j3.json")
    with open(fpath, "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
#  Figure 1: Velocity Recovery Time-Series (all 6 controllers)
# ═══════════════════════════════════════════════════════════════════
def fig01_velocity_recovery():
    fig, ax = plt.subplots(figsize=(7, 3.5))
    fault_time = SimConfig.DEFAULT_FAULT_TIME

    for ctrl in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        data = load_detail(ctrl)
        t = np.array(data["history"]["time"])
        vx = np.array([v[0] for v in data["history"]["base_velocity"]])
        vy = np.array([v[1] for v in data["history"]["base_velocity"]])
        v_planar = np.sqrt(vx**2 + vy**2)

        # Smooth with moving average
        window = 40
        v_smooth = np.convolve(v_planar, np.ones(window)/window, mode='same')

        lw = 2.5 if ctrl == "C5" else 1.5
        ls = '-' if ctrl == "C5" else '-'
        ax.plot(t, v_smooth, label=LABELS[ctrl], color=COLORS[ctrl],
                linewidth=lw, linestyle=ls, alpha=0.9 if ctrl == "C5" else 0.7)

    ax.axvline(x=fault_time, color='black', linestyle='--', linewidth=1.5,
               label='Fault Injection', alpha=0.7)
    ax.axvspan(fault_time, fault_time + 2, alpha=0.08, color='red')

    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Planar Speed $v_{xy}$ (m/s)')
    ax.set_title('Forward Velocity Recovery Under Locked Joint Failure (Joint 4)')
    ax.legend(loc='upper right', ncol=2, framealpha=0.9)
    ax.set_xlim(0, 60)
    ax.set_ylim(bottom=-0.01)

    path = os.path.join(FIG_DIR, "fig01_velocity_recovery.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 2: Spatial-Temporal Hormone Heatmap (C5)
# ═══════════════════════════════════════════════════════════════════
def fig02_hormone_heatmap():
    data = load_detail("C5")
    t = np.array(data["history"]["time"])
    H = np.array(data["history"]["hormones"])

    H_max = np.max(H) if np.max(H) > 0 else 1.0
    H_norm = np.clip(H / H_max, 0.0, 1.0)

    fig, ax = plt.subplots(figsize=(7, 3))
    extent = [t[0], t[-1], 0.5, H.shape[1] + 0.5]
    im = ax.imshow(H_norm.T, aspect='auto', origin='lower', cmap='YlOrRd',
                   extent=extent, interpolation='bicubic', vmin=0, vmax=1.0)

    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label('Normalized Hormone $H_i$ [0, 1]', rotation=270, labelpad=14)

    ax.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='cyan', linestyle='--', linewidth=1.5,
               label='Fault @ $t={}$s'.format(SimConfig.DEFAULT_FAULT_TIME))
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Joint Index')
    ax.set_title('Spatial-Temporal Hormone Dynamics $H_i(t)$ — Proposed AHM-CPG (C5)')
    ax.set_yticks(range(1, H.shape[1] + 1))
    ax.legend(loc='upper left', fontsize=8)

    path = os.path.join(FIG_DIR, "fig02_hormone_heatmap.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 3: Per-Joint Trajectories (C5, 8-panel)
# ═══════════════════════════════════════════════════════════════════
def fig03_joint_trajectories():
    data = load_detail("C5")
    t = np.array(data["history"]["time"])
    q_act = np.rad2deg(np.array(data["history"]["joint_angles"]))
    q_tgt = np.rad2deg(np.array(data["history"]["target_angles"]))
    H = np.array(data["history"]["hormones"])
    fault_joint = 3

    H_max = np.max(H) if np.max(H) > 0 else 1.0
    H_norm = np.clip(H / H_max, 0.0, 1.0)

    fig, axes = plt.subplots(8, 1, figsize=(8, 13), sharex=True, gridspec_kw={'hspace': 0.45})

    for i in range(8):
        ax = axes[i]
        is_failed = (i == fault_joint)
        c_tgt = '#e74c3c' if is_failed else '#3498db'
        c_act = '#c0392b' if is_failed else '#2ecc71'

        ax.plot(t, q_tgt[:, i], '--', color=c_tgt, linewidth=1.2,
                label='Target $q_d$', alpha=0.8)
        ax.plot(t, q_act[:, i], color=c_act, linewidth=1.5,
                label='Actual $q$')

        ax2 = ax.twinx()
        ax2.fill_between(t, 0, H_norm[:, i], color='orange', alpha=0.18)
        ax2.plot(t, H_norm[:, i], ':', color='darkorange', linewidth=1.1,
                 label='Hormone $H_i$')
        ax2.set_ylim(-0.02, 1.05)
        ax2.set_ylabel(f'$H_{{{i+1}}}$ [0-1]', color='darkorange', fontsize=7)

        ax.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='red', linestyle=':', linewidth=0.8, alpha=0.6)
        title = f'Joint {i+1}' + (' — LOCKED FAULT' if is_failed else '')
        ax.set_ylabel('Angle (°)', fontsize=8)
        ax.set_title(title, fontsize=9, loc='left',
                     color='red' if is_failed else 'black', fontweight='bold')
        ax.set_ylim(-55, 55)

        if i == 0:
            lines1, labs1 = ax.get_legend_handles_labels()
            lines2, labs2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labs1 + labs2, loc='upper right',
                      fontsize=6, ncol=3)

    axes[-1].set_xlabel('Time (s)')
    fig.suptitle('Per-Joint Trajectories & Hormone Response — C5 AHM-CPG',
                 fontsize=13, fontweight='bold', y=0.99)
    fig.subplots_adjust(top=0.95, bottom=0.05, hspace=0.50, left=0.10, right=0.90)

    path = os.path.join(FIG_DIR, "fig03_joint_trajectories.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 4: Receptor Activation R_i(t) Heatmap (C5)
# ═══════════════════════════════════════════════════════════════════
def fig04_receptor_heatmap():
    data = load_detail("C5")
    t = np.array(data["history"]["time"])
    R = np.array(data["history"]["receptors"])

    fig, ax = plt.subplots(figsize=(7, 3))
    extent = [t[0], t[-1], 0.5, R.shape[1] + 0.5]
    im = ax.imshow(R.T, aspect='auto', origin='lower', cmap='RdPu',
                   extent=extent, interpolation='bicubic', vmin=0, vmax=1.0)

    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label('Receptor $R_i$', rotation=270, labelpad=14)

    ax.axvline(x=SimConfig.DEFAULT_FAULT_TIME, color='cyan', linestyle='--', linewidth=1.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Joint Index')
    ax.set_title('Hill Receptor Activation $R_i(t)$ — Proposed AHM-CPG (C5)')
    ax.set_yticks(range(1, R.shape[1] + 1))

    path = os.path.join(FIG_DIR, "fig04_receptor_heatmap.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 5: Scenario-Disaggregated Benchmark Performance (3 Panels by Fault Type)
# ═══════════════════════════════════════════════════════════════════
def fig05_benchmark_boxplots():
    fpath = os.path.join(DATA_DIR, "benchmark_results.json")
    with open(fpath, "r") as f:
        records = json.load(f)

    ctrls = sorted(set(r["controller"] for r in records))
    ftypes = ["locked", "free", "partial_torque"]
    ftype_titles = {
        "locked": "Scenario 1: Locked Joint Failure (Severe)",
        "free": "Scenario 2: Free Joint Failure (Unpowered)",
        "partial_torque": "Scenario 3: Partial Torque Drop (30% Torque)"
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    color_list = [COLORS[c] for c in ctrls]

    np.random.seed(42)
    for idx, ft in enumerate(ftypes):
        ax = axes[idx]
        plot_data = []
        for c in ctrls:
            vals = [r["metrics"].get("r_perf", r["metrics"].get("recovery_ratio", 0.0)) * 100.0
                    for r in records if r["controller"] == c and r["fault_type"] == ft]
            plot_data.append(vals)

        bp = ax.boxplot(plot_data, labels=ctrls, patch_artist=True, widths=0.5, showfliers=False)
        for i, (patch, col) in enumerate(zip(bp['boxes'], color_list)):
            patch.set_facecolor(col)
            patch.set_alpha(0.70)
            y_vals = plot_data[i]
            x_vals = np.random.normal(i + 1, 0.04, size=len(y_vals))
            ax.scatter(x_vals, y_vals, alpha=0.35, color='black', s=10, zorder=3)

        for median in bp['medians']:
            median.set_color('black')
            median.set_linewidth(2)

        ax.set_title(ftype_titles[ft], fontweight='bold', fontsize=11)
        ax.set_ylabel('Recovery Ratio $R_{perf}$ (%)' if idx == 0 else '', fontweight='bold')
        ax.set_ylim(-5, 115)

    plt.suptitle('Scenario-Disaggregated Benchmark Performance (Separated by Fault Type)',
                 fontweight='bold', fontsize=13)
    plt.tight_layout()

    path = os.path.join(FIG_DIR, "fig05_benchmark_boxplots.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 6: Scenario-Disaggregated Generalization Stress (5 Subpanel Grid)
# ═══════════════════════════════════════════════════════════════════
def fig06_generalization():
    fpath = os.path.join(DATA_DIR, "generalization_results.json")
    with open(fpath, "r") as f:
        records = json.load(f)

    ctrls = sorted(set(r["controller"] for r in records))
    modes = ["intermittent", "incline_10deg", "sensor_noise", "mass_perturbation", "multi_joint"]
    mode_titles = {
        "intermittent": "Intermittent Fault",
        "incline_10deg": "10° Incline Slope",
        "sensor_noise": "Sensor Noise (5%)",
        "mass_perturbation": "Mass Perturbation (+35%)",
        "multi_joint": "Multi-Joint Failure (J3+J6)"
    }

    fig, axes = plt.subplots(1, 5, figsize=(16, 4.2), sharey=True)
    x = np.arange(len(ctrls))

    for idx, mode in enumerate(modes):
        ax = axes[idx]
        means = []
        stds = []
        for c in ctrls:
            vals = [r["metrics"].get("r_perf", r["metrics"].get("recovery_ratio", 0.0)) * 100.0
                    for r in records if r["controller"] == c and r["stress_mode"] == mode]
            means.append(np.mean(vals) if vals else 0.0)
            stds.append(np.std(vals) if vals else 0.0)

        bars = ax.bar(x, means, yerr=stds, capsize=3, color=[COLORS[c] for c in ctrls],
                      edgecolor='black', linewidth=0.5, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(ctrls, fontweight='bold', fontsize=9)
        ax.set_title(mode_titles[mode], fontweight='bold', fontsize=10)
        if idx == 0:
            ax.set_ylabel('Recovery Ratio $R_{perf}$ (%)', fontweight='bold')
        ax.set_ylim(0, 115)

    plt.suptitle('Scenario-Disaggregated Generalization Stress Performance (150 Episodes)', fontweight='bold', fontsize=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "fig06_generalization.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 7: Scenario-Disaggregated Fault Location Sensitivity (3 Subpanels)
# ═══════════════════════════════════════════════════════════════════
def fig07_fault_location():
    fpath = os.path.join(DATA_DIR, "benchmark_results.json")
    with open(fpath, "r") as f:
        records = json.load(f)

    ctrls = ["C1", "C3", "C5", "C6"]
    joints = [1, 3, 6]
    joint_titles = {1: "Anterior Failure (Joint 2)", 3: "Middle Failure (Joint 4)", 6: "Posterior Failure (Joint 7)"}

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharey=True)
    x = np.arange(len(ctrls))

    for idx, j in enumerate(joints):
        ax = axes[idx]
        r_means, r_stds = [], []
        for c in ctrls:
            vals = [r["metrics"].get("r_perf", r["metrics"].get("recovery_ratio", 0.0)) * 100.0
                    for r in records if r["controller"] == c and r["joint_idx"] == j]
            r_means.append(np.mean(vals) if vals else 0.0)
            r_stds.append(np.std(vals) if vals else 0.0)

        ax.bar(x, r_means, yerr=r_stds, capsize=3, color=[COLORS[c] for c in ctrls],
               edgecolor='black', linewidth=0.5, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(ctrls, fontweight='bold', fontsize=9)
        ax.set_title(joint_titles[j], fontweight='bold', fontsize=10)
        if idx == 0:
            ax.set_ylabel('Recovery Ratio $R_{perf}$ (%)', fontweight='bold')
        ax.set_ylim(0, 115)

    plt.suptitle('Scenario-Disaggregated Fault Location Sensitivity (Anterior vs Middle vs Posterior)', fontweight='bold', fontsize=12)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "fig07_fault_location.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "fig07_fault_location.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 8: Bypass Ablation (C5 vs C6 amplitude comparison)
# ═══════════════════════════════════════════════════════════════════
def fig08_bypass_ablation():
    d5 = load_detail("C5")
    d6 = load_detail("C6")

    t5 = np.array(d5["history"]["time"])
    t6 = np.array(d6["history"]["time"])
    q5 = np.rad2deg(np.array(d5["history"]["joint_angles"]))
    q6 = np.rad2deg(np.array(d6["history"]["joint_angles"]))
    h5 = np.array(d5["history"]["hormones"])
    h6 = np.array(d6["history"]["hormones"])

    fault_j = 3

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))

    # Joint 3 (adjacent to fault)
    axes[0, 0].plot(t5, q5[:, fault_j - 1], color=COLORS["C5"], linewidth=1.5,
                    label='C5 (with Bypass)')
    axes[0, 0].plot(t6, q6[:, fault_j - 1], color=COLORS["C6"], linewidth=1.5,
                    label='C6 (no Bypass)')
    axes[0, 0].axvline(10, color='red', linestyle=':', alpha=0.5)
    axes[0, 0].set_title(f'Joint {fault_j} (Pre-Fault Neighbor)', fontweight='bold')
    axes[0, 0].set_ylabel('Angle (°)')
    axes[0, 0].legend(fontsize=7)
    axes[0, 0].set_ylim(-55, 55)

    # Joint 5 (adjacent to fault, other side)
    axes[0, 1].plot(t5, q5[:, fault_j + 1], color=COLORS["C5"], linewidth=1.5)
    axes[0, 1].plot(t6, q6[:, fault_j + 1], color=COLORS["C6"], linewidth=1.5)
    axes[0, 1].axvline(10, color='red', linestyle=':', alpha=0.5)
    axes[0, 1].set_title(f'Joint {fault_j + 2} (Post-Fault Neighbor)', fontweight='bold')
    axes[0, 1].set_ylabel('Angle (°)')
    axes[0, 1].set_ylim(-55, 55)

    # Hormone at fault joint (normalized to [0, 1])
    h5_max = np.max(h5) if np.max(h5) > 0 else 1.0
    h6_max = np.max(h6) if np.max(h6) > 0 else 1.0
    h5_norm = np.clip(h5 / h5_max, 0.0, 1.0)
    h6_norm = np.clip(h6 / h6_max, 0.0, 1.0)

    axes[1, 0].plot(t5, h5_norm[:, fault_j], color=COLORS["C5"], linewidth=1.5,
                    label='C5')
    axes[1, 0].plot(t6, h6_norm[:, fault_j], color=COLORS["C6"], linewidth=1.5,
                    label='C6')
    axes[1, 0].axvline(10, color='red', linestyle=':', alpha=0.5)
    axes[1, 0].set_title(f'Normalized Hormone $H_{{{fault_j + 1}}}$ at Fault Joint', fontweight='bold')
    axes[1, 0].set_ylabel('Hormone $H_i$ [0-1]')
    axes[1, 0].set_ylim(-0.02, 1.05)
    axes[1, 0].set_xlabel('Time (s)')
    axes[1, 0].legend(fontsize=7)

    # Velocity comparison
    vx5 = np.array([v[0] for v in d5["history"]["base_velocity"]])
    vx6 = np.array([v[0] for v in d6["history"]["base_velocity"]])
    vy5 = np.array([v[1] for v in d5["history"]["base_velocity"]])
    vy6 = np.array([v[1] for v in d6["history"]["base_velocity"]])
    v5 = np.sqrt(vx5**2 + vy5**2)
    v6 = np.sqrt(vx6**2 + vy6**2)
    w = 40
    v5s = np.convolve(v5, np.ones(w)/w, mode='same')
    v6s = np.convolve(v6, np.ones(w)/w, mode='same')

    axes[1, 1].plot(t5, v5s, color=COLORS["C5"], linewidth=1.8, label='C5 (Bypass)')
    axes[1, 1].plot(t6, v6s, color=COLORS["C6"], linewidth=1.8, label='C6 (No Bypass)')
    axes[1, 1].axvline(10, color='red', linestyle=':', alpha=0.5)
    axes[1, 1].set_title('Velocity Comparison: Bypass Ablation', fontweight='bold')
    axes[1, 1].set_ylabel('Speed (m/s)')
    axes[1, 1].set_xlabel('Time (s)')
    axes[1, 1].legend(fontsize=7)

    plt.suptitle('Dynamic Bypass Coupling Ablation: C5 (Full) vs C6 (No Bypass)',
                 fontweight='bold', fontsize=12)
    plt.tight_layout()

    path = os.path.join(FIG_DIR, "fig08_bypass_ablation.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 9: Option C 6-Axis Multi-Metric Radar Chart
# ═══════════════════════════════════════════════════════════════════
def fig09_radar_chart():
    fpath = os.path.join(DATA_DIR, "benchmark_results.json")
    with open(fpath, "r") as f:
        records = json.load(f)

    ctrls = sorted(set(r["controller"] for r in records))
    
    display_names = [
        "Recovery Ratio\n$R_{perf}$ [Nature]", 
        "Forward Speed\n$v_{fwd}$ [IEEE]",
        "Path Linearity\n$1 - Y_{drift}$ [IROS]", 
        "Adapt Speed\n$1 - T_{adapt}$ [Bio]",
        "Energy Eff.\n$1 - COT$ [IEEE]", 
        "Torque Safety\n$1 - \\tau_{RMS}$ [MECH]"
    ]

    # Compute means
    means = {c: {} for c in ctrls}
    for c in ctrls:
        c_recs = [r["metrics"] for r in records if r["controller"] == c]
        means[c]["r_perf"] = np.mean([m.get("r_perf", m.get("recovery_ratio", 0.0)) for m in c_recs])
        means[c]["v_fwd"] = np.mean([m.get("v_post", 0.0) for m in c_recs])
        means[c]["y_drift"] = np.mean([m.get("y_drift_mean", 0.0) for m in c_recs])
        means[c]["t_adapt"] = np.mean([m.get("t_adapt", m.get("recovery_time", 0.0)) for m in c_recs])
        means[c]["cot"] = np.mean([m.get("cost_of_transport", 0.0) for m in c_recs])
        means[c]["tau_rms"] = np.mean([m.get("tau_rms", 0.0) for m in c_recs])

    # Normalize metrics 0 to 1
    norm_data = {}
    for c in ctrls:
        norm = []
        # R_perf: 0-1
        norm.append(means[c]["r_perf"])
        # v_fwd: 0-0.25 m/s -> 0-1
        norm.append(means[c]["v_fwd"] / 0.25)
        # Y_drift: lower = better -> 1.0 - y_drift / 0.8
        norm.append(1.0 - means[c]["y_drift"] / 0.80)
        # T_adapt: lower = better -> 1.0 - t_adapt / 45.0
        norm.append(1.0 - means[c]["t_adapt"] / 45.0)
        # COT: lower = better -> 1.0 - cot / 60.0
        norm.append(1.0 - means[c]["cot"] / 60.0)
        # tau_rms: lower = better -> 1.0 - tau_rms / 10.0
        norm.append(1.0 - means[c]["tau_rms"] / 10.0)

        norm_data[c] = [max(0.05, min(1.0, v)) for v in norm]

    N = len(display_names)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw=dict(polar=True))

    for c in ctrls:
        values = norm_data[c] + norm_data[c][:1]
        lw = 2.5 if c == "C5" else 1.3
        alpha = 0.95 if c == "C5" else 0.60
        ax.plot(angles, values, 'o-', color=COLORS[c], linewidth=lw,
                label=LABELS[c], alpha=alpha, markersize=5 if c == "C5" else 2.5)
        if c == "C5":
            ax.fill(angles, values, color=COLORS[c], alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(display_names, fontsize=8.5, fontweight='bold')
    ax.set_ylim(0, 1.05)
    ax.set_title('Option C Synthesized Hybrid Master Suite — 6-Axis Radar Chart',
                 fontweight='bold', pad=22, fontsize=12)
    ax.legend(loc='upper right', bbox_to_anchor=(1.38, 1.12), fontsize=7.5)

    path = os.path.join(FIG_DIR, "fig09_radar_chart.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Figure 10: Option C 2-Panel Heatmap (Success Rate & Lateral Drift)
# ═══════════════════════════════════════════════════════════════════
def fig10_success_heatmap():
    fpath = os.path.join(DATA_DIR, "benchmark_results.json")
    with open(fpath, "r") as f:
        records = json.load(f)

    ctrls = sorted(set(r["controller"] for r in records))
    ftypes = sorted(set(r["fault_type"] for r in records))
    ftype_labels = {"locked": "Locked", "free": "Free",
                    "partial_torque": "Partial\nTorque"}

    matrix_sr = np.zeros((len(ctrls), len(ftypes)))
    matrix_yd = np.zeros((len(ctrls), len(ftypes)))

    for ci, c in enumerate(ctrls):
        for fi, ft in enumerate(ftypes):
            sr_vals = [r["metrics"].get("recovery_success", False)
                       for r in records if r["controller"] == c and r["fault_type"] == ft]
            yd_vals = [r["metrics"].get("y_drift_mean", 0.0)
                       for r in records if r["controller"] == c and r["fault_type"] == ft]
            matrix_sr[ci, fi] = np.mean(sr_vals) * 100 if sr_vals else 0
            matrix_yd[ci, fi] = np.mean(yd_vals) if yd_vals else 0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Panel A: Success Rate
    im1 = ax1.imshow(matrix_sr, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    ax1.set_xticks(range(len(ftypes)))
    ax1.set_xticklabels([ftype_labels.get(ft, ft) for ft in ftypes], fontweight='bold')
    ax1.set_yticks(range(len(ctrls)))
    ax1.set_yticklabels(ctrls, fontweight='bold')

    for ci in range(len(ctrls)):
        for fi in range(len(ftypes)):
            val = matrix_sr[ci, fi]
            color = 'white' if val < 50 else 'black'
            ax1.text(fi, ci, f'{val:.0f}%', ha='center', va='center',
                     color=color, fontweight='bold', fontsize=11)

    cbar1 = fig.colorbar(im1, ax=ax1, pad=0.02)
    cbar1.set_label('Success Rate (%)', rotation=270, labelpad=14)
    ax1.set_title('(A) Option C Success Rate (R_perf >= 50% & Y_drift <= 0.5m)', fontweight='bold')

    # Panel B: Lateral Drift
    im2 = ax2.imshow(matrix_yd, cmap='YlOrRd_r', aspect='auto', vmin=0, vmax=0.7)
    ax2.set_xticks(range(len(ftypes)))
    ax2.set_xticklabels([ftype_labels.get(ft, ft) for ft in ftypes], fontweight='bold')
    ax2.set_yticks(range(len(ctrls)))
    ax2.set_yticklabels(ctrls, fontweight='bold')

    for ci in range(len(ctrls)):
        for fi in range(len(ftypes)):
            val = matrix_yd[ci, fi]
            color = 'black' if val < 0.4 else 'white'
            ax2.text(fi, ci, f'{val:.2f}m', ha='center', va='center',
                     color=color, fontweight='bold', fontsize=11)

    cbar2 = fig.colorbar(im2, ax=ax2, pad=0.02)
    cbar2.set_label('Mean Lateral Drift $Y_{drift}$ (m)', rotation=270, labelpad=14)
    ax2.set_title('(B) Lateral Trajectory Drift $Y_{drift}$ (Lower = Better)', fontweight='bold')

    plt.suptitle('Option C Benchmark Matrix Analysis: Success Rate & Trajectory Drift', fontweight='bold', fontsize=12)
    plt.tight_layout()

    path = os.path.join(FIG_DIR, "fig10_success_heatmap.png")
    plt.savefig(path)
    plt.close()
    print(f"  [OK] {path}")


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)
    print("\n  Generating Publication Figures (300 DPI)...\n", flush=True)

    fig01_velocity_recovery()
    fig02_hormone_heatmap()
    fig03_joint_trajectories()
    fig04_receptor_heatmap()
    fig05_benchmark_boxplots()
    fig06_generalization()
    fig07_fault_location()
    fig08_bypass_ablation()
    fig09_radar_chart()
    fig10_success_heatmap()

    print(f"\n  All 10 figures saved to {FIG_DIR}/\n", flush=True)
