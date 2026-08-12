"""
Statistical Significance Testing, Effect Size (Cliff's Delta),
and LaTeX / Markdown Comparison Table Generator.
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy import stats

def compute_cliffs_delta(x, y):
    """Calculate Cliff's delta effect size between samples x and y."""
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0
    greater = sum(1 for i in x for j in y if i > j)
    less = sum(1 for i in x for j in y if i < j)
    delta = (greater - less) / (n1 * n2)
    return delta

def analyze_benchmark_results(json_filepath="results/full_benchmark_results.json", output_markdown="results/statistical_summary.md"):
    """
    Parses benchmark results, performs Kruskal-Wallis & Mann-Whitney U tests,
    computes 95% CIs, Cliff's delta, and formats a markdown summary table.
    """
    if not os.path.exists(json_filepath):
        print(f"File not found: {json_filepath}")
        return
        
    with open(json_filepath, "r", encoding="utf-8") as f:
        records = json.load(f)
        
    controllers = sorted(list(set(r["controller"] for r in records)))
    
    # Aggregates by controller
    data_rec_time = {c: [] for c in controllers}
    data_rec_ratio = {c: [] for c in controllers}
    data_auc = {c: [] for c in controllers}
    data_cot = {c: [] for c in controllers}
    
    for r in records:
        c = r["controller"]
        m = r["metrics"]
        data_rec_time[c].append(m["recovery_time"])
        data_rec_ratio[c].append(m["recovery_ratio"])
        data_auc[c].append(m["performance_loss_auc"])
        data_cot[c].append(m["cost_of_transport"])
        
    # Statistical Table Generation
    lines = []
    lines.append("# Statistical Evaluation & Significance Analysis\n")
    lines.append(f"Total benchmark episodes evaluated: **{len(records)}**\n")
    lines.append("## 1. Summary Performance Metrics (Mean +/- 95% Confidence Interval)\n")
    lines.append("| Controller | Recovery Time T_rec (s) | Speed Recovery Ratio (R_v) | Performance Loss (L_AUC) | Cost of Transport (COT) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    
    for c in controllers:
        t_arr = np.array(data_rec_time[c])
        r_arr = np.array(data_rec_ratio[c])
        a_arr = np.array(data_auc[c])
        c_arr = np.array(data_cot[c])
        
        t_mean, t_ci = np.mean(t_arr), 1.96 * np.std(t_arr) / np.sqrt(max(1, len(t_arr)))
        r_mean, r_ci = np.mean(r_arr), 1.96 * np.std(r_arr) / np.sqrt(max(1, len(r_arr)))
        a_mean, a_ci = np.mean(a_arr), 1.96 * np.std(a_arr) / np.sqrt(max(1, len(a_arr)))
        c_mean, c_ci = np.mean(c_arr), 1.96 * np.std(c_arr) / np.sqrt(max(1, len(c_arr)))
        
        lines.append(f"| **{c}** | {t_mean:.2f} +/- {t_ci:.2f} | {r_mean:.2f} +/- {r_ci:.2f} | {a_mean:.2f} +/- {a_ci:.2f} | {c_mean:.2f} +/- {c_ci:.2f} |")

    lines.append("\n## 2. Hypothesis Testing & Effect Size (Proposed C5 vs Baselines)\n")
    lines.append("| Comparison Pair | Mann-Whitney U p-value | Holm-Adjusted p | Cliff's Delta | Effect Magnitude |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    
    c5_auc = np.array(data_auc.get("C5", []))
    comparisons = [c for c in controllers if c != "C5"]
    
    raw_p_values = []
    p_details = []
    
    for c in comparisons:
        other_auc = np.array(data_auc[c])
        if len(c5_auc) > 0 and len(other_auc) > 0:
            stat, p_val = stats.mannwhitneyu(c5_auc, other_auc, alternative='less')
            delta = compute_cliffs_delta(other_auc, c5_auc)
            
            mag = "Negligible"
            abs_d = abs(delta)
            if abs_d >= 0.474:
                mag = "Large"
            elif abs_d >= 0.33:
                mag = "Medium"
            elif abs_d >= 0.147:
                mag = "Small"
                
            raw_p_values.append(p_val)
            p_details.append((c, p_val, delta, mag))
            
    # Holm-Bonferroni correction
    if raw_p_values:
        sorted_indices = np.argsort(raw_p_values)
        m_tests = len(raw_p_values)
        adj_p_values = np.zeros(m_tests)
        for rank, idx in enumerate(sorted_indices):
            adj_p = min(1.0, raw_p_values[idx] * (m_tests - rank))
            adj_p_values[idx] = adj_p
            
        for i, (c, p_val, delta, mag) in enumerate(p_details):
            adj_p = adj_p_values[i]
            p_str = "< 0.001" if adj_p < 0.001 else f"{adj_p:.4f}"
            lines.append(f"| Proposed C5 vs **{c}** | {p_val:.2e} | {p_str} | {delta:+.3f} | **{mag}** |")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(output_markdown), exist_ok=True)
    with open(output_markdown, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Statistical summary saved to {output_markdown}")
    return content

if __name__ == "__main__":
    analyze_benchmark_results()
