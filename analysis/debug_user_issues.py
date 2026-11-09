"""
Detailed debug script to diagnose the 6 exact issues reported by the user:
1. Fig 1: Max smoothed velocity across all 6 controllers
2. Fig 7: Joint indexing in benchmark_results.json
3. Fig 8(d): Max velocity in C5 and C6
4. Fig 10(a): recovery_success values and fault_type keys in benchmark_results.json
5. Fig 13: Exact coordinates of fault injection points across all controllers
6. Fig 14: Exact min/max of all 4 subplots from c5_dynamic_friction.json and c1_dynamic_friction.json
"""

import json
import os
import numpy as np

DATA_DIR = "results/publication/data"

def inspect_all():
    print("=" * 80)
    print("  DIAGNOSING 6 USER REPORTED ISSUES")
    print("=" * 80)

    # ── Issue 1: Fig 1 Velocity Peak ──
    print("\n--- 1. Fig 1 Velocity Peaks (all 6 controllers) ---")
    for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        fpath = os.path.join(DATA_DIR, "detail_histories", f"{c.lower()}_locked_j3.json")
        with open(fpath, "r") as f:
            d = json.load(f)
        vx = np.array([v[0] for v in d["history"]["base_velocity"]])
        vy = np.array([v[1] for v in d["history"]["base_velocity"]])
        v_planar = np.sqrt(vx**2 + vy**2)
        window = 35
        v_smooth = np.convolve(v_planar, np.ones(window)/window, mode='same')
        print(f"  {c}: v_planar max={np.max(v_planar):.3f}, v_smooth max={np.max(v_smooth):.3f}, min={np.min(v_smooth):.3f}")

    # ── Issue 2: Fig 7 Joint Indexing in Benchmark Results ──
    print("\n--- 2. Fig 7 Joint Indexing in benchmark_results.json ---")
    b_path = os.path.join(DATA_DIR, "benchmark_results.json")
    with open(b_path, "r") as f:
        recs = json.load(f)
    
    sample = recs[0]
    print(f"  Record keys: {list(sample.keys())}")
    all_joints = sorted(list(set(r.get("joint_idx", r.get("joint", r.get("fault_joint", "NOT_FOUND"))) for r in recs)))
    print(f"  All joint indices in benchmark: {all_joints}")
    for j in [0, 1, 2, 3, 4, 5, 6, 7]:
        count = sum(1 for r in recs if r.get("joint_idx") == j or r.get("fault_joint") == j)
        print(f"    Joint {j}: {count} records")

    # ── Issue 3: Fig 8(d) Velocity in C5 & C6 ──
    print("\n--- 3. Fig 8(d) Velocity in C5 & C6 ---")
    for c in ["C5", "C6"]:
        fpath = os.path.join(DATA_DIR, "detail_histories", f"{c.lower()}_locked_j3.json")
        with open(fpath, "r") as f:
            d = json.load(f)
        vx = np.array([v[0] for v in d["history"]["base_velocity"]])
        vy = np.array([v[1] for v in d["history"]["base_velocity"]])
        v_smooth = np.convolve(np.sqrt(vx**2 + vy**2), np.ones(35)/35, mode='same')
        print(f"  {c} v_smooth: max={np.max(v_smooth):.3f}, min={np.min(v_smooth):.3f}")

    # ── Issue 4: Fig 10(a) Success Rate & Fault Types ──
    print("\n--- 4. Fig 10(a) Success Rate & Fault Types in benchmark_results.json ---")
    fault_types = sorted(list(set(r.get("fault_type", "NONE") for r in recs)))
    print(f"  Unique fault_type values in dataset: {fault_types}")
    success_vals = set(r["metrics"].get("recovery_success") for r in recs)
    print(f"  recovery_success values present: {success_vals}")
    for ft in fault_types:
        for c in ["C1", "C5"]:
            sub = [r["metrics"].get("recovery_success") for r in recs if r.get("controller") == c and r.get("fault_type") == ft]
            print(f"    Controller={c}, FaultType='{ft}': count={len(sub)}, true_count={sum(1 for v in sub if v)}, avg={np.mean(sub) if sub else 'N/A'}")

    # ── Issue 5: Fig 13 Fault Injection Coordinates ──
    print("\n--- 5. Fig 13 Fault Injection Coordinates ---")
    for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        fpath = os.path.join(DATA_DIR, "detail_histories", f"{c.lower()}_locked_j3.json")
        with open(fpath, "r") as f:
            d = json.load(f)
        pos = np.array(d["history"]["base_position"])
        t = np.array(d["history"]["time"])
        f_idx = np.where(t >= 18.0)[0][0]
        print(f"  {c}: t={t[f_idx]:.1f}s, X={pos[f_idx, 0]:.3f}, Y_raw={pos[f_idx, 1]:.3f}, Y_fwd={-pos[f_idx, 1]:.3f}")

    # ── Issue 6: Fig 14 Real Data Min/Max from dynamic_friction ──
    print("\n--- 6. Fig 14 Data Ranges in dynamic_friction ---")
    for c in ["C5", "C1"]:
        fpath = os.path.join(DATA_DIR, "detail_histories", f"{c.lower()}_dynamic_friction.json")
        if not os.path.exists(fpath):
            print(f"  [MISSING] {fpath}")
            continue
        with open(fpath, "r") as f:
            d = json.load(f)
        vx = np.array([v[0] for v in d["history"]["base_velocity"]])
        vy = np.array([v[1] for v in d["history"]["base_velocity"]])
        v = np.sqrt(vx**2 + vy**2)
        v_s = np.convolve(v, np.ones(35)/35, mode='same')
        h = np.array(d["history"]["hormones"])
        hg = np.mean(h, axis=1)
        freq = 1.0 - 0.15 * hg
        tau = np.array(d["history"]["joint_torques"])
        tau_rms = np.sqrt(np.mean(tau**2, axis=1))
        tau_s = np.convolve(tau_rms, np.ones(35)/35, mode='same')
        pos = np.array(d["history"]["base_position"])
        yaw = np.rad2deg(np.arctan2(pos[:, 0], -pos[:, 1]))
        
        print(f"  [{c} dynamic_friction]:")
        print(f"    v_smooth : min={np.min(v_s):.3f}, max={np.max(v_s):.3f}")
        print(f"    H_G      : min={np.min(hg):.3f}, max={np.max(hg):.3f}")
        print(f"    freq_rat : min={np.min(freq):.3f}, max={np.max(freq):.3f}")
        print(f"    tau_rms  : min={np.min(tau_s):.3f}, max={np.max(tau_s):.3f}")
        print(f"    yaw_deg  : min={np.min(yaw):.3f}, max={np.max(yaw):.3f}")

if __name__ == "__main__":
    inspect_all()
