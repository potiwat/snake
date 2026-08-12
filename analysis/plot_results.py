"""
Publication-Quality Plotting & Visualization Generator for Research Paper.
Generates Spatial-Temporal Hormone Heatmaps, Velocity Recovery Time Series,
and Benchmark Bar Charts with 95% Confidence Intervals.
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# Set publication style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11

def plot_hormone_heatmap(history, output_path="results/figures/hormone_heatmap.png"):
    """Plot Spatial-Temporal Heatmap of Local Hormone Concentration H_i(t)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    time = np.array(history["time"])
    hormones = np.array(history["hormones"]) # Shape: (T, num_joints)
    
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
    
    # Heatmap imshow: x=time, y=joint_index
    extent = [time[0], time[-1], 0.5, hormones.shape[1] + 0.5]
    im = ax.imshow(
        hormones.T,
        aspect='auto',
        origin='lower',
        cmap='YlOrRd',
        extent=extent,
        interpolation='bicubic'
    )
    
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label('Local Hormone Concentration ($H_i$)', rotation=270, labelpad=18, fontweight='bold')
    
    ax.axvline(x=10.0, color='blue', linestyle='--', linewidth=2, label='Fault Injection ($t=10s$)')
    ax.set_xlabel('Time (s)', fontweight='bold')
    ax.set_ylabel('Snake Joint Index (Head $\\rightarrow$ Tail)', fontweight='bold')
    ax.set_title('Spatial-Temporal Artificial Hormone Dynamics ($H_i$)', fontweight='bold', fontsize=13)
    ax.set_yticks(range(1, hormones.shape[1] + 1))
    ax.legend(loc='upper left')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Hormone heatmap saved to {output_path}")

def plot_velocity_comparison(histories_dict, fault_time=10.0, output_path="results/figures/velocity_recovery.png"):
    """Plot Velocity Recovery R_v(t) time series for multiple controllers."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    colors = {'C1': '#e74c3c', 'C2': '#e67e22', 'C3': '#f1c40f', 'C4': '#9b59b6', 'C5': '#2ecc71', 'C6': '#3498db'}
    labels = {
        'C1': 'C1: Fixed CPG',
        'C2': 'C2: Error-Adaptive CPG',
        'C3': 'C3: Shape Recovery (Elsayed et al.)',
        'C4': 'C4: Oracle Fault-Aware CPG',
        'C5': 'C5: Proposed Local-Global AHM-CPG',
        'C6': 'C6: AHM-CPG w/o Bypass'
    }
    
    for ctrl_name, history in histories_dict.items():
        time = np.array(history["time"])
        vx = np.array([v[0] for v in history["base_velocity"]])
        
        # Moving average filter for visualization smoothness
        window = 20
        vx_smooth = np.convolve(vx, np.ones(window)/window, mode='same')
        
        color = colors.get(ctrl_name, 'black')
        label = labels.get(ctrl_name, ctrl_name)
        linewidth = 2.5 if ctrl_name == 'C5' else 1.8
        
        ax.plot(time, vx_smooth, label=label, color=color, linewidth=linewidth)
        
    ax.axvline(x=fault_time, color='black', linestyle='--', linewidth=1.5, label='Fault Injection')
    ax.axhline(y=0.0, color='gray', linestyle=':', linewidth=1)
    
    ax.set_xlabel('Time (s)', fontweight='bold')
    ax.set_ylabel('Forward Velocity $v_x$ (m/s)', fontweight='bold')
    ax.set_title('Online Recovery of Forward Velocity Under Joint Failure', fontweight='bold', fontsize=13)
    ax.legend(loc='upper right', frameon=True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Velocity comparison plot saved to {output_path}")

def plot_benchmark_bar_charts(benchmark_filepath="results/quick_benchmark.json", output_path="results/figures/benchmark_summary.png"):
    """Plot summary bar charts comparing Recovery Time, Performance Loss, and COT across controllers."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if not os.path.exists(benchmark_filepath):
        print(f"File not found: {benchmark_filepath}")
        return
        
    with open(benchmark_filepath, "r") as f:
        records = json.load(f)
        
    controllers = sorted(list(set(r["controller"] for r in records)))
    
    # Aggregates
    rec_times = {c: [] for c in controllers}
    l_aucs = {c: [] for c in controllers}
    cots = {c: [] for c in controllers}
    
    for r in records:
        c = r["controller"]
        m = r["metrics"]
        rec_times[c].append(m["recovery_time"])
        l_aucs[c].append(m["performance_loss_auc"])
        cots[c].append(m["cost_of_transport"])
        
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5), dpi=300)
    
    ctrl_names = list(controllers)
    x = np.arange(len(ctrl_names))
    width = 0.55
    
    # 1. Recovery Time (lower is better)
    means_t = [np.mean(rec_times[c]) for c in ctrl_names]
    stds_t = [np.std(rec_times[c]) for c in ctrl_names]
    bars1 = ax1.bar(x, means_t, width, yerr=stds_t, capsize=5, color='#3498db', edgecolor='black')
    ax1.set_ylabel('Recovery Time $T_{rec}$ (s)', fontweight='bold')
    ax1.set_title('Recovery Speed (Lower = Better)', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(ctrl_names)
    
    # 2. Performance Loss AUC (lower is better)
    means_auc = [np.mean(l_aucs[c]) for c in ctrl_names]
    stds_auc = [np.std(l_aucs[c]) for c in ctrl_names]
    bars2 = ax2.bar(x, means_auc, width, yerr=stds_auc, capsize=5, color='#e74c3c', edgecolor='black')
    ax2.set_ylabel('Performance Loss Area ($L_{AUC}$)', fontweight='bold')
    ax2.set_title('Performance Loss (Lower = Better)', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(ctrl_names)
    
    # 3. Cost of Transport (lower is better)
    means_cot = [np.mean(cots[c]) for c in ctrl_names]
    stds_cot = [np.std(cots[c]) for c in ctrl_names]
    bars3 = ax3.bar(x, means_cot, width, yerr=stds_cot, capsize=5, color='#2ecc71', edgecolor='black')
    ax3.set_ylabel('Cost of Transport (COT)', fontweight='bold')
    ax3.set_title('Energy Efficiency (Lower = Better)', fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(ctrl_names)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Benchmark summary bar chart saved to {output_path}")

if __name__ == "__main__":
    from experiments.run_single import run_single_episode
    print("Generating demo plots for paper...")
    
    # Run C5 episode for hormone heatmap
    history_c5, _ = run_single_episode(controller_type="C5", fault_joint_idx=3, gui=False)
    plot_hormone_heatmap(history_c5)
    
    # Run multiple controllers for velocity comparison
    histories = {}
    for ctrl in ["C1", "C3", "C5", "C6"]:
        h, _ = run_single_episode(controller_type=ctrl, fault_joint_idx=3, gui=False)
        histories[ctrl] = h
        
    plot_velocity_comparison(histories)
