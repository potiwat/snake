import json
import os
import numpy as np

hist_dir = 'results/publication/data/detail_histories'
ctrls = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6']

for c in ctrls:
    f = f"{c}_locked_j3.json"
    p = os.path.join(hist_dir, f)
    with open(p, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    hist = data['history']
    time = np.array(hist['time'])
    base_pos = np.array(hist['base_position'])
    
    # Instantaneous planar velocity
    dt = 0.005
    win = int(0.5 / dt) # 0.5s moving window
    v = np.zeros(len(time))
    for i in range(win, len(time)):
        dy = abs(base_pos[i, 1] - base_pos[i-win, 1])
        v[i] = dy / 0.5
        
    print(f"=== {c.upper()} Locked J3 ===")
    print(f"  t=17.5s (pre-fault):  v = {v[int(17.5/dt)]:.3f} m/s")
    print(f"  t=18.5s (post-0.5s): v = {v[int(18.5/dt)]:.3f} m/s")
    print(f"  t=19.5s (post-1.5s): v = {v[int(19.5/dt)]:.3f} m/s")
    print(f"  t=20.8s (post-2.8s): v = {v[int(20.8/dt)]:.3f} m/s")
    print(f"  t=25.0s (post-7.0s): v = {v[int(25.0/dt)]:.3f} m/s")
    print(f"  t=50.0s (steady):    v = {v[int(50.0/dt)]:.3f} m/s")
