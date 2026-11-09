# Orchestrator Master Plan: AHM-CPG Snake Robot Pipeline

## Objectives
Deliver a complete, rigorous, and verified simulation, statistical benchmarking, ablation analysis, visualization, and IOP Bioinspiration & Biomimetics Q1 LaTeX publication pipeline for the AHM-CPG Snake Robot in PyBullet.

## Phased Strategy

### Phase 0: Codebase Survey & Feature Inventory
- Spawn 3 parallel Explorers to inspect existing Python modules, PyBullet simulation setup, C1-C6 controller implementations, metrics modules, test suites, and paper templates.
- Consolidate findings into `PROJECT.md` at project root with complete Feature Inventory, Architecture, and Interface Contracts.

### Phase 1: Dual-Track Execution
- **Track A (E2E Testing Track)**:
  - Test runner and test infrastructure for testing controllers, metrics calculations, statistical significance tests, ablation runs, figure generators, and LaTeX compilation.
  - Publish `TEST_INFRA.md` and `TEST_READY.md`.
- **Track B (Implementation Track)**:
  - Milestone 1: Simulation & C1-C6 Controller Pipeline Execution (locked/limp faults, multi-joint, friction regimes).
  - Milestone 2: Statistical Rigor & Metric Evaluation (N>=10 seeds, Wilcoxon, Mann-Whitney, ANOVA, Cohen's d, p < 0.001 validation).
  - Milestone 3: Ablation & Sensitivity Study (Dh, m, KB, gw, gamma contributions quantified).
  - Milestone 4: Publication-Quality High-Res Figures (300+ DPI, IOP Bioinspiration & Biomimetics styling).
  - Milestone 5: Q1 LaTeX Manuscript Compilation (manuscript_bioinspiration.tex / main.tex, .bib, tables, embedded figures).
  - Milestone 6: Final Integration & E2E Acceptance Verification.

### Phase 2: Final Verification & Delivery
- Verify all acceptance criteria from `ORIGINAL_REQUEST.md`.
- Ensure clean forensic audit (ZERO integrity violations).
- Present comprehensive final report.
