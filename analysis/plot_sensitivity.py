"""
Plotting script for AHM-CPG Hyperparameter Sensitivity Analysis.
Generates results/publication/figures/fig11_sensitivity_analysis.png using pure Matplotlib.
"""

import os
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DATA_PATH = Path("results/publication/data/sensitivity_results.json")
OUTPUT_FIG_PATH = Path("results/publication/figures/fig11_sensitivity_analysis.png")

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.dpi': 300
})

def draw_heatmap(ax, matrix, x_labels, y_labels, title, xlabel, ylabel, cbar_label, cmap="viridis", fmt=".3f"):
    im = ax.imshow(matrix, cmap=cmap, aspect='auto')
    
    ax.set_xticks(np.arange(len(x_labels)))
    ax.set_yticks(np.arange(len(y_labels)))
    ax.set_xticklabels(x_labels)
    ax.set_yticklabels(y_labels)
    
    ax.set_title(title, fontweight="bold", pad=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    
    # Annotate cells
    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            val = matrix[i, j]
            text_str = f"{val:.3f}" if "3f" in fmt else f"{val:.1f}"
            # Choose text color based on background luminance
            cell_color = im.norm(val)
            text_color = "white" if cell_color < 0.3 or cell_color > 0.7 else "black"
            ax.text(j, i, text_str, ha="center", va="center", color=text_color, fontsize=9, fontweight="bold")
            
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(cbar_label, rotation=270, labelpad=15)

def plot_sensitivity():
    if not DATA_PATH.exists():
        print(f"Error: {DATA_PATH} not found.")
        return

    with open(DATA_PATH, "r") as f:
        data = json.load(f)

    dh_alpha = data["dh_alpha_grid"]
    kh_m = data["kh_m_grid"]

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))

    # (a) D_h vs alpha_h -> R_v
    draw_heatmap(
        axes[0, 0],
        np.array(dh_alpha["rv_matrix"]),
        [f"{a:.2f}" for a in dh_alpha["alpha_values"]],
        [f"{d:.2f}" for d in dh_alpha["dh_values"]],
        "(a) Speed Recovery Ratio $R_v$ ($D_h$ vs $\\alpha_h$)",
        "Secretion Rate $\\alpha_h$",
        "Spine Diffusion $D_h$",
        "Speed Recovery Ratio ($R_v$)",
        cmap="YlGnBu", fmt=".3f"
    )

    # (b) D_h vs alpha_h -> T_rec
    draw_heatmap(
        axes[0, 1],
        np.array(dh_alpha["trec_matrix"]),
        [f"{a:.2f}" for a in dh_alpha["alpha_values"]],
        [f"{d:.2f}" for d in dh_alpha["dh_values"]],
        "(b) Recovery Time $T_{rec}$ ($D_h$ vs $\\alpha_h$)",
        "Secretion Rate $\\alpha_h$",
        "Spine Diffusion $D_h$",
        "Recovery Time $T_{rec}$ (s)",
        cmap="OrRd_r", fmt=".1f"
    )

    # (c) K_h vs m -> R_v
    draw_heatmap(
        axes[1, 0],
        np.array(kh_m["rv_matrix"]),
        [f"{m:.1f}" for m in kh_m["m_values"]],
        [f"{k:.2f}" for k in kh_m["kh_values"]],
        "(c) Speed Recovery Ratio $R_v$ ($K_h$ vs $m$)",
        "Hill Exponent $m$",
        "Hill Threshold $K_h$",
        "Speed Recovery Ratio ($R_v$)",
        cmap="YlGnBu", fmt=".3f"
    )

    # (d) K_h vs m -> T_rec
    draw_heatmap(
        axes[1, 1],
        np.array(kh_m["trec_matrix"]),
        [f"{m:.1f}" for m in kh_m["m_values"]],
        [f"{k:.2f}" for k in kh_m["kh_values"]],
        "(d) Recovery Time $T_{rec}$ ($K_h$ vs $m$)",
        "Hill Exponent $m$",
        "Hill Threshold $K_h$",
        "Recovery Time $T_{rec}$ (s)",
        cmap="OrRd_r", fmt=".1f"
    )

    plt.tight_layout()
    OUTPUT_FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_FIG_PATH, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Sensitivity plot saved to {OUTPUT_FIG_PATH}")

if __name__ == "__main__":
    plot_sensitivity()
