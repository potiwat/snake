"""
Publication Statistical Analysis with LaTeX Table Export.
- Kruskal-Wallis omnibus test
- Mann-Whitney U pairwise tests with Holm-Bonferroni correction
- Bootstrap 95% CI (10,000 resamples)
- Cliff's delta effect size
- Recovery success rate
- Output: Markdown + LaTeX tables
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy import stats

DATA_DIR = "results/publication/data"
TABLE_DIR = "results/publication/tables"


def compute_cliffs_delta(x, y):
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0
    greater = sum(1 for a in x for b in y if a > b)
    less = sum(1 for a in x for b in y if a < b)
    return (greater - less) / (n1 * n2)


def bootstrap_ci(data, n_boot=10000, ci=0.95):
    data = np.array(data)
    if len(data) < 2:
        return np.mean(data), np.mean(data)
    boot_means = np.array([
        np.mean(np.random.choice(data, size=len(data), replace=True))
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    return np.percentile(boot_means, alpha * 100), np.percentile(boot_means, (1 - alpha) * 100)


def effect_magnitude(delta):
    d = abs(delta)
    if d >= 0.474:
        return "Large"
    elif d >= 0.33:
        return "Medium"
    elif d >= 0.147:
        return "Small"
    return "Negligible"


def analyze_benchmark():
    fpath = os.path.join(DATA_DIR, "benchmark_results.json")
    if not os.path.exists(fpath):
        print(f"File not found: {fpath}")
        return

    with open(fpath, "r", encoding="utf-8") as f:
        records = json.load(f)

    ctrls = sorted(set(r["controller"] for r in records))
    n_episodes = len(records)

    # Aggregate data
    data = {c: {"rec_time": [], "rec_ratio": [], "l_auc": [], "cot": [],
                "success": [], "distance": [], "y_drift": [], "di_linear": [], "v_post": [],
                "tau_rms": [], "c_hormone": []}
            for c in ctrls}

    for r in records:
        c = r["controller"]
        m = r["metrics"]
        data[c]["rec_time"].append(m.get("recovery_time", m.get("t_adapt", 0.0)))
        data[c]["rec_ratio"].append(m.get("recovery_ratio", m.get("r_perf", 0.0)))
        data[c]["l_auc"].append(m.get("performance_loss_auc", 0.0))
        data[c]["cot"].append(m.get("cost_of_transport", 0.0))
        data[c]["success"].append(1 if m.get("recovery_success", False) else 0)
        data[c]["distance"].append(m.get("distance_traveled", 0.0))
        data[c]["y_drift"].append(m.get("y_drift_mean", 0.0))
        data[c]["di_linear"].append(m.get("di_linear", 95.0))
        data[c]["v_post"].append(m.get("v_post", 0.0))
        data[c]["tau_rms"].append(m.get("tau_rms", 0.0))
        data[c]["c_hormone"].append(m.get("c_hormone", 1.0))

    # ─── Table 1: Summary Metrics (Option C Hybrid Master Suite) ──
    md = []
    md.append("# Table 1: Option C Synthesized Hybrid Master Suite Performance Metrics\n")
    md.append(f"Total benchmark episodes: **{n_episodes}** "
              f"(6 controllers × 3 fault types × 3 joints × 5 seeds)\n")
    md.append("| Controller | $R_{perf}$ (%) | $v_{fwd}$ (m/s) | $DI$ (%) [Dr. Potiwat] | $Y_{drift}$ (m) | "
              "$T_{adapt}$ (s) | COT | $\\tau_{RMS}$ (Nm) | Success Rate (%) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for c in ctrls:
        r_m = np.mean(data[c]["rec_ratio"]) * 100
        r_lo, r_hi = np.array(bootstrap_ci(data[c]["rec_ratio"])) * 100
        v_m = np.mean(data[c]["v_post"])
        di_m = np.mean(data[c]["di_linear"])
        yd_m = np.mean(data[c]["y_drift"])
        t_m = np.mean(data[c]["rec_time"])
        cot_m = np.mean(data[c]["cot"])
        tau_m = np.mean(data[c]["tau_rms"])
        sr = np.mean(data[c]["success"]) * 100

        md.append(f"| **{c}** | {r_m:.1f}% [{r_lo:.1f}%, {r_hi:.1f}%] | "
                  f"{v_m:.3f} | {di_m:.1f}% | {yd_m:.3f} | "
                  f"{t_m:.2f} | {cot_m:.2f} | {tau_m:.2f} | "
                  f"{sr:.0f}% |")

    # ─── Kruskal-Wallis Omnibus ───────────────────────────────────
    md.append("\n## Omnibus Test (Kruskal-Wallis)\n")
    for metric_name, metric_key in [("Recovery Ratio (R_perf)", "rec_ratio"),
                                      ("Forward Speed (v_fwd)", "v_post"),
                                      ("Lateral Drift (Y_drift)", "y_drift"),
                                      ("Adaptation Latency (T_adapt)", "rec_time")]:
        groups = [data[c][metric_key] for c in ctrls]
        try:
            stat, p_val = stats.kruskal(*groups)
        except ValueError:
            stat, p_val = 0.0, 1.0
        p_str = f"p < 0.001" if p_val < 0.001 else f"p = {p_val:.4f}"
        md.append(f"- **{metric_name}**: H = {stat:.2f}, {p_str}")

    # ─── Table 2: Pairwise Tests (C5 vs baselines) ──────────────────
    md.append("\n## Table 2: Pairwise Statistical Tests (C5 vs Baselines)\n")
    md.append("| Comparison | Metric | Mann-Whitney U | p-value (raw) | "
              "p (Holm) | Cliff's δ | Effect |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    comparisons = [c for c in ctrls if c != "C5"]
    for metric_key, metric_name in [("rec_ratio", "$R_{perf}$"),
                                     ("y_drift", "$Y_{drift}$"),
                                     ("rec_time", "$T_{adapt}$")]:
        raw_ps = []
        details = []
        c5_data = np.array(data["C5"][metric_key])
        alt = 'less' if metric_key == "y_drift" else ('greater' if metric_key == "rec_ratio" else 'less')

        for c in comparisons:
            other = np.array(data[c][metric_key])
            try:
                stat_u, p_val = stats.mannwhitneyu(c5_data, other, alternative=alt)
            except ValueError:
                stat_u, p_val = 0.0, 1.0
            if metric_key == "rec_ratio":
                delta = compute_cliffs_delta(list(c5_data), list(other))
            else:
                delta = compute_cliffs_delta(list(other), list(c5_data))
            raw_ps.append(p_val)
            details.append((c, stat_u, p_val, delta, metric_name))

        # Holm-Bonferroni
        m_tests = len(raw_ps)
        sorted_idx = np.argsort(raw_ps)
        adj_ps = np.ones(m_tests)
        for rank, idx in enumerate(sorted_idx):
            adj_ps[idx] = min(1.0, raw_ps[idx] * (m_tests - rank))

        for i, (c, stat_u, p_val, delta, mname) in enumerate(details):
            adj_p = adj_ps[i]
            p_adj_s = "$<$0.001" if adj_p < 0.001 else f"{adj_p:.4f}"
            mag = effect_magnitude(delta)
            md.append(f"| C5 vs {c} | {mname} | {stat_u:.1f} | {p_val:.4f} | "
                      f"{p_adj_s} | {delta:+.3f} | **{mag}** |")

    md_content = "\n".join(md)

    # ─── LaTeX Export ─────────────────────────────────────────────
    tex = []
    tex.append("\\begin{table}[ht]")
    tex.append("\\centering")
    tex.append("\\caption{Option C Hybrid Master Suite Performance Metrics (Mean [Bootstrap 95\\% CI])}")
    tex.append("\\label{tab:benchmark}")
    tex.append("\\small")
    tex.append("\\begin{tabular}{lccccccc}")
    tex.append("\\toprule")
    tex.append("Controller & $R_{perf}$ (\\%) & $v_{fwd}$ (m/s) & $Y_{drift}$ (m) & "
               "$T_{adapt}$ (s) & COT & $\\tau_{RMS}$ (Nm) & Success (\\%) \\\\")
    tex.append("\\midrule")

    for c in ctrls:
        r_m = np.mean(data[c]["rec_ratio"]) * 100
        v_m = np.mean(data[c]["v_post"])
        yd_m = np.mean(data[c]["y_drift"])
        t_m = np.mean(data[c]["rec_time"])
        cot_m = np.mean(data[c]["cot"])
        tau_m = np.mean(data[c]["tau_rms"])
        sr = np.mean(data[c]["success"]) * 100

        cname = f"\\textbf{{{c}}}" if c == "C5" else c

        tex.append(f"{cname} & {r_m:.1f}\\% & "
                   f"{v_m:.3f} & {yd_m:.3f} & "
                   f"{t_m:.2f} & {cot_m:.2f} & {tau_m:.2f} & "
                   f"{sr:.0f}\\% \\\\")

    tex.append("\\bottomrule")
    tex.append("\\end{tabular}")
    tex.append("\\end{table}")
    tex_content = "\n".join(tex)

    # ─── Save ─────────────────────────────────────────────────────
    os.makedirs(TABLE_DIR, exist_ok=True)

    md_path = os.path.join(TABLE_DIR, "table1_benchmark_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  [OK] {md_path}")

    tex_path = os.path.join(TABLE_DIR, "table1_benchmark_summary.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)
    print(f"  [OK] {tex_path}")

    # Pairwise LaTeX table
    tex2 = []
    tex2.append("\\begin{table}[ht]")
    tex2.append("\\centering")
    tex2.append("\\caption{Pairwise Statistical Tests (C5 vs Baselines)}")
    tex2.append("\\label{tab:statistical}")
    tex2.append("\\small")
    tex2.append("\\begin{tabular}{llcccc}")
    tex2.append("\\toprule")
    tex2.append("Pair & Metric & $p$ (Holm) & Cliff's $\\delta$ & Effect \\\\")
    tex2.append("\\midrule")

    # Re-compute for LaTeX
    for metric_key, metric_name in [("l_auc", "$L_{AUC}$"),
                                     ("rec_ratio", "$R_v$")]:
        c5_data = np.array(data["C5"][metric_key])
        alt = 'less' if metric_key == "l_auc" else 'greater'
        raw_ps = []
        details2 = []

        for c in comparisons:
            other = np.array(data[c][metric_key])
            try:
                _, p_val = stats.mannwhitneyu(c5_data, other, alternative=alt)
            except ValueError:
                p_val = 1.0
            if metric_key == "rec_ratio":
                delta = compute_cliffs_delta(list(c5_data), list(other))
            else:
                delta = compute_cliffs_delta(list(other), list(c5_data))
            raw_ps.append(p_val)
            details2.append((c, p_val, delta))

        m_t = len(raw_ps)
        si = np.argsort(raw_ps)
        adj = np.ones(m_t)
        for rank, idx in enumerate(si):
            adj[idx] = min(1.0, raw_ps[idx] * (m_t - rank))

        for i, (c, p_val, delta) in enumerate(details2):
            adj_p = adj[i]
            ps = "$<$0.001" if adj_p < 0.001 else f"{adj_p:.4f}"
            mag = effect_magnitude(delta)
            tex2.append(f"C5 vs {c} & {metric_name} & {ps} & "
                        f"{delta:+.3f} & {mag} \\\\")

    tex2.append("\\bottomrule")
    tex2.append("\\end{tabular}")
    tex2.append("\\end{table}")

    tex2_path = os.path.join(TABLE_DIR, "table2_statistical_tests.tex")
    with open(tex2_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex2))
    print(f"  [OK] {tex2_path}")

    # Also save as markdown
    md2_path = os.path.join(TABLE_DIR, "table2_statistical_tests.md")
    with open(md2_path, "w", encoding="utf-8") as f:
        f.write(md_content)  # full content already includes table 2
    print(f"  [OK] {md2_path}")


if __name__ == "__main__":
    print("\n  Generating Statistical Tables...\n", flush=True)
    np.random.seed(0)
    analyze_benchmark()
    print("\n  Done.\n", flush=True)
