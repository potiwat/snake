## 2026-08-15T08:50:47Z
You are Explorer M5 (Q1 LaTeX Manuscript Specialist).
Working directory: e:/agy/snake - Copy/.agents/teamwork_preview_explorer_m5/
Project Scope: e:/agy/snake - Copy/PROJECT.md
User Requirements: e:/agy/snake - Copy/.agents/ORIGINAL_REQUEST.md

Your task:
1. Inspect `analysis/generate_full_latex_manuscript.py`, `results/publication/manuscript.tex`, and IOP journal formatting guidelines.
2. Formulate the exact implementation plan to satisfy Requirement R5:
   - Create `analysis/generate_iop_latex_manuscript.py` producing publication-ready LaTeX manuscript `results/publication/manuscript_bioinspiration.tex` formatted for IOPscience *Bioinspiration & Biomimetics* (`\documentclass[12pt]{iopart}`, `\usepackage{iopams}`, `\usepackage{graphicx}`, `\usepackage{booktabs}`, `\usepackage{cite}`).
   - Generate a dedicated BibTeX bibliography `results/publication/references.bib` containing 30+ comprehensive peer-reviewed references (vertebrate neuro-endocrine biology, spinal cord lesions, snake robotics, CPG nonlinear oscillators, reaction-diffusion modeling).
   - Synchronize all mathematical parameters in Section 2 text with calibrated `config.py` ($w_q=0.44, w_v=0.03, w_\tau=0.44, w_p=0.10, \alpha_h=0.37, d_0=0.10, k_d=0.07, n=2.0, D_h=0.06, K_h=0.65, m=4.0, g_a=0.15, g_n=0.95, \sigma=1.42, g_w=0.15, \gamma_{steer}=-0.18, K_B=2.80$).
   - Embed all figures (Fig 1–Fig 14) and statistical performance tables cleanly with detailed descriptive captions.
   - Verify self-contained LaTeX source and syntax.
3. Document exact generator design, section outlines, bibliography entries, and verification commands in `handoff.md` in your working directory.
4. Send a message with your report path when complete. Maintain `progress.md`. Do not modify source code.
