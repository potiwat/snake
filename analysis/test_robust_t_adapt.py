import json
import os
import sys
sys.path.insert(0, '.')
import numpy as np

hist_dir = 'results/publication/data/detail_histories'

def compute_t_adapt_proper(history, fault_time=18.0, dt=0.005, sim_duration=60.0):
    time = np.array(history["time"])
    base_poss = np.array(history.get("base_position", history.get("base_positions", [])))
    
    # Calculate rolling forward speed
    win_len = int(1.0 / dt)
    N = len(time)
    
    # Forward velocity magnitude along longitudinal axis
    vel_forward = np.zeros(N)
    for i in range(win_len, N):
        dy = abs(base_poss[i, 1] - base_poss[i - win_len, 1])
        vel_forward[i] = dy / (time[i] - time[i - win_len])
        
    # Pre-fault velocity (t in [10, 18])
    pre_mask = (time >= 10.0) & (time < fault_time)
    v_pre = np.mean(vel_forward[pre_mask]) if np.any(pre_mask) else 0.25
    
    # Post-fault steady state velocity (t in [35, 60])
    post_mask = (time >= 35.0) & (time <= sim_duration)
    v_post = np.mean(vel_forward[post_mask]) if np.any(post_mask) else 0.0
    
    # If robot fails to recover forward speed (v_post < 0.25 * v_pre), t_adapt = 42.0 (unrecovered)
    if v_post < 0.05 or v_post < 0.25 * v_pre:
        return 42.0, v_pre, v_post
        
    # Find first time after fault_time + 0.2s where vel_forward reaches 85% of v_post
    target = 0.85 * v_post
    post_indices = np.where(time >= fault_time + 0.1)[0]
    for idx in post_indices:
        if vel_forward[idx] >= target:
            # check if it stays sustained
            check_end = min(N-1, idx + int(1.0/dt))
            if np.mean(vel_forward[idx:check_end]) >= 0.70 * target:
                return float(time[idx] - fault_time), v_pre, v_post
                
    return 42.0, v_pre, v_post

for f in sorted(os.listdir(hist_dir)):
    p = os.path.join(hist_dir, f)
    with open(p, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    hist = data['history']
    t_ad, v_pre, v_post = compute_t_adapt_proper(hist)
    print(f"{f:25s}: T_adapt = {t_ad:5.2f} s | v_pre = {v_pre:.3f} | v_post = {v_post:.3f}")
