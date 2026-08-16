"""
Extracts and downsamples benchmark data and time-series trajectories for the interactive Web Dashboard.
Generates web/dashboard_data.json and web/dashboard_data.js
"""

import os
import json
import numpy as np

def prepare_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pub_dir = os.path.join(base_dir, "results", "publication")
    data_dir = os.path.join(pub_dir, "data")
    web_dir = os.path.join(base_dir, "web")
    os.makedirs(web_dir, exist_ok=True)

    # 1. Load Benchmark Results Summary
    b_path = os.path.join(data_dir, "benchmark_results.json")
    benchmark_summary = {}
    if os.path.exists(b_path):
        with open(b_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        
        for item in b_data:
            ctrl = item["controller"]
            if ctrl not in benchmark_summary:
                benchmark_summary[ctrl] = {
                    "v_fwd": [], "recovery_ratio": [], "cot": [], "e_total": [], "heading_error": []
                }
            m = item["metrics"]
            benchmark_summary[ctrl]["v_fwd"].append(float(m.get("v_fwd_post", m.get("mean_velocity_y", 0.0))))
            benchmark_summary[ctrl]["recovery_ratio"].append(float(m.get("recovery_ratio", 0.0) * 100.0))
            benchmark_summary[ctrl]["cot"].append(float(m.get("cot", 0.0)))
            benchmark_summary[ctrl]["e_total"].append(float(m.get("total_energy", 0.0)))
            benchmark_summary[ctrl]["heading_error"].append(float(abs(m.get("final_heading_deg", m.get("heading_error", 0.0)))))

        for ctrl in benchmark_summary:
            for k in benchmark_summary[ctrl]:
                arr = benchmark_summary[ctrl][k]
                benchmark_summary[ctrl][k] = {
                    "mean": round(float(np.mean(arr)), 3),
                    "std": round(float(np.std(arr)), 3),
                    "median": round(float(np.median(arr)), 3),
                    "p25": round(float(np.percentile(arr, 25)), 3),
                    "p75": round(float(np.percentile(arr, 75)), 3)
                }

    # 2. Load Generalization Results
    g_path = os.path.join(data_dir, "generalization_results.json")
    gen_summary = {}
    if os.path.exists(g_path):
        with open(g_path, "r", encoding="utf-8") as f:
            g_data = json.load(f)
        for item in g_data:
            ctrl = item["controller"]
            mode = item["stress_mode"]
            if mode not in gen_summary:
                gen_summary[mode] = {}
            if ctrl not in gen_summary[mode]:
                gen_summary[mode][ctrl] = []
            m = item["metrics"]
            gen_summary[mode][ctrl].append(float(m.get("recovery_ratio", 0.0) * 100.0))
        
        for mode in gen_summary:
            for ctrl in gen_summary[mode]:
                arr = gen_summary[mode][ctrl]
                gen_summary[mode][ctrl] = {
                    "mean": round(float(np.mean(arr)), 2),
                    "std": round(float(np.std(arr)), 2)
                }

    # 3. Load Ablation Results
    a_path = os.path.join(data_dir, "ablation_results.json")
    ablation_summary = {}
    if os.path.exists(a_path):
        with open(a_path, "r", encoding="utf-8") as f:
            a_data = json.load(f)
        stat_sum = a_data.get("statistical_summary", {})
        variants_meta = a_data.get("variants", {})
        for v_key, v_stats in stat_sum.items():
            name = variants_meta.get(v_key, {}).get("name", v_key)
            desc = variants_meta.get(v_key, {}).get("description", "")
            ablation_summary[v_key] = {
                "name": name,
                "desc": desc,
                "eta_rec_mean": round(float(v_stats.get("eta_rec_mean", 0.0) * 100.0), 2),
                "eta_rec_std": round(float(v_stats.get("eta_rec_std", 0.0) * 100.0), 2),
                "cot_mean": round(float(v_stats.get("cot_mean", 0.0)), 2),
                "delta_yaw_mean": round(float(v_stats.get("delta_yaw_mean", 0.0)), 2)
            }

    # 4. Downsample Detail Histories for Interactive Simulator (at 10 Hz)
    detail_dir = os.path.join(data_dir, "detail_histories")
    downsampled_histories = {}
    controllers = ["C1", "C2", "C3", "C4", "C5", "C6"]
    scenarios = ["locked_j3", "dynamic_friction", "dual_locked_j3_j4"]

    step_subsample = 20  # 200 Hz down to 10 Hz (every 20th step)

    if os.path.exists(detail_dir):
        for scen in scenarios:
            downsampled_histories[scen] = {}
            for ctrl in controllers:
                fname = f"{ctrl.lower()}_{scen}.json"
                fpath = os.path.join(detail_dir, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                        hist = raw.get("history", {})
                        t_arr = hist.get("time", [])[::step_subsample]
                        pos_arr = hist.get("base_position", [])[::step_subsample]
                        vel_arr = hist.get("base_velocity", [])[::step_subsample]
                        q_arr = hist.get("joint_angles", [])[::step_subsample]
                        qd_arr = hist.get("target_angles", [])[::step_subsample]
                        h_arr = hist.get("hormones", [])[::step_subsample]
                        r_arr = hist.get("receptors", [])[::step_subsample]

                        # Calculate forward speed magnitude from vel_arr (vx, vy, vz)
                        speed_arr = [float(np.sqrt(v[0]**2 + v[1]**2)) if len(v) >= 2 else 0.0 for v in vel_arr]

                        downsampled_histories[scen][ctrl] = {
                            "time": [round(t, 2) for t in t_arr],
                            "pos": [[round(p[0], 3), round(p[1], 3)] for p in pos_arr] if pos_arr else [],
                            "speed": [round(s, 4) for s in speed_arr],
                            "q_act": [[round(q, 3) for q in q_row] for q_row in q_arr] if q_arr else [],
                            "q_target": [[round(qd, 3) for qd in qd_row] for qd_row in qd_arr] if qd_arr else [],
                            "hormones": [[round(h, 4) for h in h_row] for h_row in h_arr] if h_arr else [],
                            "receptors": [[round(r, 4) for r in r_row] for r_row in r_arr] if r_arr else []
                        }
                    except Exception as e:
                        print(f"Error processing {fname}: {e}")

    final_payload = {
        "benchmark": benchmark_summary,
        "generalization": gen_summary,
        "ablation": ablation_summary,
        "histories": downsampled_histories
    }

    out_file = os.path.join(web_dir, "dashboard_data.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f)
    
    js_out_file = os.path.join(web_dir, "dashboard_data.js")
    with open(js_out_file, "w", encoding="utf-8") as f:
        f.write("window.DASHBOARD_DATA = " + json.dumps(final_payload) + ";\n")

    fsize_kb = os.path.getsize(out_file) / 1024
    print(f"[OK] Dashboard data prepared successfully: {out_file} ({fsize_kb:.1f} KB)")

if __name__ == "__main__":
    prepare_data()
