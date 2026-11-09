import json
import numpy as np
from scipy import stats

bm_path = 'results/publication/data/benchmark_results.json'
with open(bm_path) as f:
    bm = json.load(f)

# Focus on LOCKED fault only (most interesting)
locked_runs = [r for r in bm if r["fault_type"] == "locked"]
print(f'Locked fault runs: {len(locked_runs)}')

controllers = ['C1','C2','C3','C4','C5','C6']

print('\n=== Locked Fault Only: Recovery Ratio ===')
ctrl_data = {}
for ctrl in controllers:
    runs = [r for r in locked_runs if r["controller"] == ctrl]
    rv = np.array([r["metrics"].get("r_perf", 0) for r in runs])
    ctrl_data[ctrl] = rv
    drift = np.array([r["metrics"].get("x_drift_mean", 0) for r in runs])
    cot = np.array([r["metrics"].get("cost_of_transport", 0) for r in runs])
    tau = np.array([r["metrics"].get("tau_rms", 0) for r in runs])
    speed = np.array([r["metrics"].get("v_post_fwd", 0) for r in runs])
    print(f'{ctrl}: rv={np.mean(rv):.3f}+/-{np.std(rv):.3f} | drift={np.mean(drift):.3f}+/-{np.std(drift):.3f} | cot={np.mean(cot):.2f}+/-{np.std(cot):.2f} | tau={np.mean(tau):.3f}+/-{np.std(tau):.3f} | speed={np.mean(speed):.4f}+/-{np.std(speed):.4f}')

# C5 vs others pairwise Wilcoxon
print('\n=== Pairwise Wilcoxon (C5 vs others, locked, rv) ===')
for ctrl in ['C1','C2','C3','C4','C6']:
    stat, p = stats.mannwhitneyu(ctrl_data['C5'], ctrl_data[ctrl], alternative='two-sided')
    n1, n2 = len(ctrl_data['C5']), len(ctrl_data[ctrl])
    # Cliff's delta
    count = sum(1 for a in ctrl_data['C5'] for b in ctrl_data[ctrl] if a > b)
    count_tie = sum(1 for a in ctrl_data['C5'] for b in ctrl_data[ctrl] if a == b)
    cliff_d = (2*count + count_tie) / (n1*n2) - 1
    print(f'C5 vs {ctrl}: U={stat:.1f}, p={p:.4e}, Cliffs d={cliff_d:.3f}')

# Check by joint location
print('\n=== By Joint Location (locked, C5) ===')
joint_idxs = sorted(set(r["joint_idx"] for r in locked_runs))
for ji in joint_idxs:
    runs_c5 = [r for r in locked_runs if r["controller"] == "C5" and r["joint_idx"] == ji]
    rv = np.array([r["metrics"].get("r_perf", 0) for r in runs_c5])
    drift = np.array([r["metrics"].get("x_drift_mean", 0) for r in runs_c5])
    print(f'  J{ji+1}: n={len(runs_c5)}, rv={np.mean(rv):.3f}+/-{np.std(rv):.3f}, drift={np.mean(drift):.3f}m')

# v_pre stats (pre-fault baseline)
print('\n=== Pre-fault speed (nominal locomotion baseline, C5 free fault) ===')
c5_free = [r for r in bm if r["controller"] == "C5" and r["fault_type"] == "free"]
v_pre = np.array([r["metrics"].get("v_pre_fwd", 0) for r in c5_free])
print(f'v_pre: {np.mean(v_pre):.4f}+/-{np.std(v_pre):.4f} m/s')
c5_locked = [r for r in bm if r["controller"] == "C5" and r["fault_type"] == "locked"]
v_pre2 = np.array([r["metrics"].get("v_pre_fwd", 0) for r in c5_locked])
v_post2 = np.array([r["metrics"].get("v_post_fwd", 0) for r in c5_locked])
print(f'C5 locked: v_pre={np.mean(v_pre2):.4f}, v_post={np.mean(v_post2):.4f}, rv={np.mean(v_post2/v_pre2)*100:.1f}%')

c1_locked = [r for r in bm if r["controller"] == "C1" and r["fault_type"] == "locked"]
v_pre1 = np.array([r["metrics"].get("v_pre_fwd", 0) for r in c1_locked])
v_post1 = np.array([r["metrics"].get("v_post_fwd", 0) for r in c1_locked])
print(f'C1 locked: v_pre={np.mean(v_pre1):.4f}, v_post={np.mean(v_post1):.4f}, rv={np.mean(v_post1/v_pre1)*100:.1f}%')
