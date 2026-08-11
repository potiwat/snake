"""
Publication-Quality Boxplots and Bar Charts for Full Benchmark & Generalization Stress Tests.
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11

def plot_benchmark_boxplots(json_filepath="results/full_benchmark_results.json", output_path="results/figures/full_benchmark_boxplots.png"):
    """Plot multi-panel boxplots comparing Recovery Time, Velocity Ratio, AUC, and COT."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if not os.path.exists(json_filepath):
        print(f"File not found: {json_filepath}")
        return
        
    with open(json_filepath, "r") as f:
        records = json.load(f)
        
    controllers = sorted(list(set(r["controller"] for r in records)))
    
    rec_times = {c: [] for c in controllers}
    rec_ratios = {c: [] for c in controllers}
    l_aucs = {c: [] for c in controllers}
    cots = {c: [] for c in controllers}
    
    for r in records:
        c = r["controller"]
        m = r["metrics"]
        rec_times[c].append(m["recovery_time"])
        rec_ratios[c].append(m["recovery_ratio"])
        l_aucs[c].append(m["performance_loss_auc"])
        cots[c].append(m["cost_of_transport"])
        
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=300)
    colors = ['#e74c3c', '#e67e22', '#f1c40f', '#9b59b6', '#2ecc71', '#3498db']
    
    # 1. Recovery Time
    data_t = [rec_times[c] for c in controllers]
    bp1 = axes[0, 0].boxplot(data_t, labels=controllers, patch_artist=True)
    for patch, col in zip(bp1['boxes'], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.7)
    axes[0, 0].set_ylabel('Recovery Time $T_{rec}$ (s)', fontweight='bold')
    axes[0, 0].set_title('Recovery Time (Lower = Better)', fontweight='bold')
    
    # 2. Speed Recovery Ratio
    data_r = [rec_ratios[c] for c in controllers]
    bp2 = axes[0, 1].boxplot(data_r, labels=controllers, patch_artist=True)
    for patch, col in zip(bp2['boxes'], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.7)
    axes[0, 1].set_ylabel('Speed Recovery Ratio $R_v$', fontweight='bold')
    axes[0, 1].set_title('Speed Recovery Ratio (Higher = Better)', fontweight='bold')
    
    # 3. Performance Loss AUC
    data_a = [l_aucs[c] for c in controllers]
    bp3 = axes[1, 0].boxplot(data_a, labels=controllers, patch_artist=True)
    for patch, col in zip(bp3['boxes'], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.7)
    axes[1, 0].set_ylabel('Performance Loss AUC ($L_{AUC}$)', fontweight='bold')
    axes[1, 0].set_title('Performance Degradation Area (Lower = Better)', fontweight='bold')
    
    # 4. Cost of Transport
    data_c = [cots[c] for c in controllers]
    bp4 = axes[1, 1].boxplot(data_c, labels=controllers, patch_artist=True)
    for patch, col in zip(bp4['boxes'], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.7)
    axes[1, 1].set_ylabel('Cost of Transport (COT)', fontweight='bold')
    axes[1, 1].set_title('Energy Cost of Transport (Lower = Better)', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Full benchmark boxplot saved to {output_path}")

def plot_generalization_robustness(json_filepath="results/generalization_results.json", output_path="results/figures/generalization_robustness.png"):
    """Plot performance across unseen stress testing conditions (intermittent, slope, noise, mass)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if not os.path.exists(json_filepath):
        print(f"File not found: {json_filepath}")
        return
        
    with open(json_filepath, "r") as f:
        records = json.load(f)
        
    controllers = sorted(list(set(r["controller"] for r in records)))
    stress_modes = sorted(list(set(r["stress_mode"] for r in records)))
    
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    
    x = np.arange(len(stress_modes))
    width = 0.18
    
    for i, c in enumerate(controllers):
        means = []
        for mode in stress_modes:
            vals = [r["metrics"]["recovery_ratio"] for r in records if r["controller"] == c and r["stress_mode"] == mode]
            means.append(np.mean(vals) if vals else 0.0)
            
        offset = (i - len(controllers) / 2.0) * width + width / 2.0
        ax.bar(x + offset, means, width, label=f'Ctrl {c}')
        
    ax.set_ylabel('Speed Recovery Ratio ($R_v$)', fontweight='bold')
    ax.set_title('Generalization & Robustness Under Unseen Stress Conditions', fontweight='bold', fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace('_', ' ').title() for m in stress_modes], fontweight='bold')
    ax.legend(loc='upper right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Generalization robustness plot saved to {output_path}")

if __name__ == "__main__":
    plot_benchmark_boxplots()
    plot_generalization_robustness()
