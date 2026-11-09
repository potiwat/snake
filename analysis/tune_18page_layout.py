import os
import subprocess
import fitz

def test_compile(scale_singles=0.66, scale_minipairs=0.47, textfloatsep=6, intextsep=4):
    with open("analysis/build_18page_manuscript.py", "r", encoding="utf-8") as f:
        code = f.read()

    # Apply adjustments to build script
    # Float separations
    code = code.replace(r"\setlength{\textfloatsep}{7pt plus 1.5pt minus 1.5pt}", f"\\setlength{{\\textfloatsep}}{{{textfloatsep}pt plus 1pt minus 1pt}}")
    code = code.replace(r"\setlength{\intextsep}{5pt plus 1pt minus 1pt}", f"\\setlength{{\\intextsep}}{{{intextsep}pt plus 1pt minus 1pt}}")
    
    # Single figure widths
    for fig in ["fig00_system_overview.jpg", "fig01_velocity_recovery.png", "fig03_joint_trajectories.png", "fig05_benchmark_boxplots.png", "fig08_bypass_ablation.png", "fig13_trajectory_paths.png", "fig14_dynamic_transitions.png"]:
        import re
        pat = rf"\\includegraphics\[width=[^\]]+\]\{{figures/{fig}\}}"
        repl = r"\includegraphics[width=" + str(scale_singles) + r"\linewidth]{figures/" + fig + r"}"
        code = re.sub(pat, lambda m: repl, code)

    # Write out temp test
    with open("analysis/build_18page_manuscript.py", "w", encoding="utf-8") as f:
        f.write(code)

    subprocess.run(["python", "analysis/build_18page_manuscript.py"], capture_output=True)
    subprocess.run(["python", "analysis/generate_iop_latex_manuscript.py"], capture_output=True)
    subprocess.run(["python", "analysis/sync_assets.py"], capture_output=True)
    
    cmd = r"C:\Users\potiwatnga\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe -interaction=nonstopmode -halt-on-error manuscript_bioinspiration.tex"
    res = subprocess.run(cmd, shell=True, capture_output=True)
    if res.returncode != 0:
        print("Compile error!")
        return -1
    # 2nd pass
    subprocess.run(cmd, shell=True, capture_output=True)
    
    doc = fitz.open("manuscript_bioinspiration.pdf")
    pages = len(doc)
    print(f"Tested scale_singles={scale_singles}, textfloatsep={textfloatsep} -> Total pages: {pages}")
    return pages

for s in [0.68, 0.65, 0.62, 0.60, 0.58]:
    p = test_compile(scale_singles=s, textfloatsep=6, intextsep=4)
    if p == 18:
        print(f"[FOUND OPTIMAL] scale_singles={s} yields exactly 18 pages!")
        break
