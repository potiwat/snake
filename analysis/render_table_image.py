"""
Render Option C Table 1 as a 300-DPI high-resolution PNG image.
"""

import os
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_PATH = "results/publication/figures/table1_option_c_summary.png"

def render_table():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    headers = [
        "Controller", 
        "Recovery Ratio\n$R_{perf}$ (%)", 
        "Forward Speed\n$v_{fwd}$ (m/s)", 
        "Lateral Drift\n$Y_{drift}$ (m)", 
        "Adapt Latency\n$T_{adapt}$ (s)", 
        "Cost of Transport\nCOT", 
        "Torque Load\n$\\tau_{RMS}$ (Nm)", 
        "Success\nRate (%)"
    ]
    
    data = [
        ["C1 (Fixed CPG)", "54.3% [44.7%, 63.8%]", "0.136", "0.285", "15.81", "11.85", "3.42", "62%"],
        ["C2 (Error-Adaptive)", "12.1% [10.5%, 13.6%]", "0.030", "0.642", "41.86", "54.31", "8.12", "0%"],
        ["C3 (Shape Recovery)", "67.2% [56.9%, 77.4%]", "0.168", "0.210", "9.30", "10.76", "3.89", "78%"],
        ["C4 (Oracle Baseline)", "71.5% [61.8%, 80.5%]", "0.179", "0.185", "6.51", "10.86", "3.75", "84%"],
        ["C5 (Proposed AHM-CPG)", "84.3% [69.3%, 99.5%]", "0.211", "0.142", "12.09", "12.57", "3.55", "71%"],
        ["C6 (AHM w/o Bypass)", "81.8% [65.9%, 97.1%]", "0.205", "0.165", "11.16", "14.35", "3.91", "73%"],
    ]
    
    fig, ax = plt.subplots(figsize=(14, 4.5), dpi=300)
    ax.axis('off')
    
    table = ax.table(
        cellText=data,
        colLabels=headers,
        cellLoc='center',
        loc='center'
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)
    
    # Style Header
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white', fontsize=10)
            cell.set_facecolor('#1F2937')  # Dark navy gray
            cell.set_height(0.12)
        else:
            # Highlight C5 (Row 5 -> idx 5)
            if row == 5:
                cell.set_facecolor('#DCFCE7')  # Soft green highlight
                cell.set_text_props(weight='bold', color='#166534')
            elif row % 2 == 0:
                cell.set_facecolor('#F9FAFB')  # Light gray zebra stripe
            else:
                cell.set_facecolor('#FFFFFF')
            cell.set_height(0.09)
            
    plt.title("Option C: Synthesized Hybrid Master Suite Performance Metrics (270 Benchmark Episodes)", 
              fontsize=13, weight='bold', pad=20, color='#111827')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"[OK] Saved Option C Table Image: {OUTPUT_PATH}")

if __name__ == "__main__":
    render_table()
