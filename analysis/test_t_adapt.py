import json
import os
import sys
sys.path.insert(0, '.')
from analysis.metrics import LocomotionMetrics

hist_dir = 'results/publication/data/detail_histories'
for f in sorted(os.listdir(hist_dir)):
    p = os.path.join(hist_dir, f)
    with open(p, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    hist = data['history']
    m_stored = data.get('metrics', {})
    m_recalc = LocomotionMetrics.calculate_metrics(hist, fault_time=18.0, sim_duration=60.0, total_mass=9.45)
    print(f"{f:25s}: Stored t_adapt = {m_stored.get('t_adapt', 'N/A')}, Recalc t_adapt = {m_recalc.get('t_adapt', 'N/A')}, v_fwd = {m_recalc.get('v_fwd', 0):.3f}")
