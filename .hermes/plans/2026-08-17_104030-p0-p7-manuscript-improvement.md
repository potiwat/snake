# P0–P7 Manuscript Improvement Plan

> **For Hermes:** Execute each priority only after its entry gate passes; preserve the frozen P0 evidence contract.

**Goal:** Produce a submission-ready Bioinspiration & Biomimetics manuscript whose claims, equations, tables, figures, statistics, and generated artifacts agree with executable code and regenerated simulation data.

**Architecture:** Treat P0 as the evidence and reproducibility gate. P1–P4 improve scholarly structure and interpretation without changing the validated evidence. P5–P6 strengthen endpoint and statistical reporting. P7 is the final presentation and submission-quality gate. The LaTeX generator is the canonical source for publication copies; regression tests prevent stale claims from returning.

**Tech Stack:** Python 3.12, PyBullet, NumPy/SciPy, Matplotlib, pytest, LaTeX/IOP class, BibTeX.

---

## Status overview

| Priority | Workstream | Status | Exit gate |
|---|---|---|---|
| P0 | Evidence integrity and paper–code consistency | Completed | 138 tests pass; datasets complete; PDF compiles |
| P1 | Background and Related Work | Draft implemented; scholarly audit required | Claims supported by specific citations; no novelty overclaim |
| P2 | System Overview and architecture communication | Implemented; visual/content audit required | Diagram agrees with equations and controller code |
| P3 | Abstract and contribution framing | Implemented; final editorial pass required | ≤250 words; verified numbers only; scope and limitations explicit |
| P4 | Discussion, biological interpretation, limitations, failure cases | Implemented; evidence-boundary audit required | Simulation evidence separated from biological/hardware hypotheses |
| P5 | Adaptation and recovery endpoint reporting | Implemented under corrected contract | Censoring explicit; no mean latency over not-reached episodes |
| P6 | Paired statistics, ablation, sensitivity, multiplicity | Core paired analysis implemented; sensitivity/reporting audit remains | Experimental unit and correction family declared; no NaN/fallback p-values |
| P7 | Quantitative captions and submission QA | Partly implemented | All captions/data/figures match; clean compile; submission package complete |

## Canonical ordering

The original review document contains inconsistent P2/P3 labels in different sections. This plan fixes the canonical order as:

- P1: Related Work
- P2: System Overview Figure
- P3: Abstract
- P4: Discussion and limitations
- P5: Adaptation endpoint
- P6: Statistical and ablation rigor
- P7: Figure captions and final QA

---

## P0 — Evidence integrity and paper–code consistency

**Objective:** Freeze a defensible empirical foundation before improving prose or presentation.

**Completed work**

1. Align metric implementation and manuscript definitions:
   - pre-fault window: `[fault_time-8 s, fault_time)`;
   - post-adaptation window: `[fault_time+12 s, trial end]`;
   - recovery ratio: measured `v_post/v_pre`;
   - energy and RMS torque: recorded actuator torque/velocity;
   - trajectory-heading deviation named according to its implementation.
2. Represent unreached adaptation as `None`, never as remaining trial duration.
3. Pair benchmark tests by complete `(fault_scenario, seed)` identity.
4. Apply one Holm family across the 20 planned benchmark comparisons.
5. Use paired Wilcoxon and paired Cohen's d for matched ablation cells.
6. Remove unsupported thermal, embedded-runtime, universal-superiority, and biological-validation claims.
7. Regenerate 480 benchmark, 420 generalization, and 210 ablation records.
8. Regenerate publication tables and figures.
9. Add regression guards for metric windows, pairing, censoring, actuator signals, statistics, and unsupported manuscript claims.

**Verified exit gate**

- `python3 -m pytest -q` → `138 passed`.
- Benchmark 480/480, generalization 420/420, ablation 210/210; no NaN/Inf.
- 80 benchmark scenario–seed cells retained.
- All 15 referenced figures and 37 citation keys exist.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript_bioinspiration.tex` succeeds.

**Freeze rule:** P1–P7 must not alter metric contracts, seeds, controller definitions, test families, or validated numerical claims without reopening P0 and rerunning the full evidence pipeline.

---

## P1 — Background and Related Work

**Objective:** Establish the literature gap without using a single reference paper as a template for novelty claims.

**Target structure**

1. CPG-based snake locomotion.
2. Fault-tolerant and damage-recovery control.
3. Artificial hormone systems and neuromodulation.
4. Reaction–diffusion mechanisms in robotics.
5. Explicit research gap and bounded contributions.

**Actions**

1. Audit every prior-work claim against the cited source, not merely the general topic.
2. Separate exact reproductions, conceptual influences, and internal heuristic baselines.
3. Describe C2 as threshold feedback, C3 as a local heuristic, and C4 as an oracle-informed single-fault reference.
4. Add a comparison matrix covering sensing assumptions, explicit fault identification, spatial coordination, adaptation mechanism, and validation domain.
5. Remove “first”, “novel”, or “state-of-the-art” unless a documented search supports the wording.
6. Include recent work relevant to fault-tolerant locomotion and neuromodulation; do not rely only on historical CPG citations.

**Files likely to change**

- `analysis/generate_iop_latex_manuscript.py`
- `manuscript.tex`
- `manuscript_bioinspiration.tex`
- `references.bib`
- `results/publication/references.bib`

**Validation**

- Citation-specificity review for each paragraph.
- All cited keys resolve.
- No unsupported priority or novelty wording.
- Literature section leads directly to the stated contribution rather than repeating the Introduction.

---

## P2 — System Overview and architecture communication

**Objective:** Make the four-stage control and feedback loop understandable before detailed equations.

**Required diagram content**

1. Snake robot and measured joint state.
2. Kinematic-coherence stimulus `S_i`.
3. Reaction–diffusion hormone state `H_i`.
4. Hill receptor response `R_i`.
5. CPG reconfiguration:
   - amplitude modulation;
   - global frequency modulation;
   - dynamic bypass;
   - curvature-offset neutralization.
6. Joint commands and closed-loop return path.

**Actions**

1. Cross-check every arrow, variable, and stage against controller code.
2. Distinguish local joint signals from global hormone/frequency terms visually.
3. Mark measured quantities, internal states, and commanded outputs with distinct styles.
4. Avoid depicting thermal protection, biological receptors, or hardware timing as validated components.
5. Ensure joint indexing in the diagram matches manuscript and simulation indexing.
6. Add a concise caption explaining information flow without causal biological overclaim.

**Files likely to change**

- `analysis/plot_publication.py` or the source used to create `fig00_system_overview`
- `results/publication/figures/fig00_system_overview.*`
- manuscript generator and manuscript copies

**Validation**

- Diagram-to-code variable checklist passes.
- Every stage shown has an implemented code path.
- Every major implemented stage is represented once.
- Figure remains legible at journal column/page width.

---

## P3 — Abstract and contribution framing

**Objective:** Produce a concise, evidence-bounded abstract suitable for Bioinspiration & Biomimetics.

**Required narrative**

1. Engineering problem and why it matters.
2. Gap in existing fault-recovery approaches.
3. Proposed AHM-CPG mechanism at a conceptual level.
4. Experimental design: 480 episodes, six controllers, eight scenarios, matched seeds.
5. Verified findings and negative result.
6. Simulation-only boundary and practical implication.

**Verified numbers allowed**

- C5 speed: `0.173 m/s`.
- C5 recovery: `69.7%`, bootstrap 95% CI approximately `[61.2%, 78.0%]`.
- Higher C5 speed/recovery than C1–C3 after global Holm correction.
- No aggregate C5–C6 difference (`p_adj=1.0000`, negligible effects).
- Higher C5 mechanical energy than C1–C3 as a trade-off.

**Actions**

1. Keep the abstract at or below 250 words.
2. Remove raw parameter listings unless essential to identify the method.
3. Include the C5–C6 null result and energy trade-off so the abstract is not selectively positive.
4. Avoid “model-free” unless the exact meaning is defined and defensible.
5. Avoid physiological, hardware, real-time, and thermal claims.

**Validation**

- Automated word count ≤250.
- Every numerical statement cross-checks against generated tables.
- Claim-guard tests pass.
- No undefined abbreviation or equation symbol.

---

## P4 — Discussion, biological interpretation, limitations, and failure cases

**Objective:** Interpret findings without turning computational analogies into biological evidence.

**Target subsections**

1. Engineering role of nonlinear Hill gating.
2. Dynamic bypass: mechanism, null aggregate result, and scenario-specific questions.
3. Biological analogy and its evidential limits.
4. Performance–energy trade-off.
5. Failure cases and boundary conditions.
6. Sim-to-real limitations and future validation.

**Actions**

1. Interpret the strong `m=1` ablation degradation as evidence for nonlinear gating in this implementation, not proof of biological receptor kinetics.
2. State that no-diffusion, no-bypass, and no-global-frequency variants do not show aggregate degradation under the tested ablation protocol.
3. Report the dynamic-friction failure explicitly: C5 recovery `17.8%`.
4. Explain recovery ratios above 100% as post-fault speed exceeding the measured pre-fault reference.
5. State limitations:
   - PyBullet simulation only;
   - planar locomotion and chosen friction model;
   - manually selected parameters;
   - limited morphology and fault distribution;
   - no motor electrical/thermal model;
   - no communication-delay or embedded-runtime benchmark;
   - no physical-robot or physiological validation.
6. Convert biological claims into analogy, hypothesis, or future-test language.
7. Define concrete future experiments rather than generic future work.

**Validation**

- Each interpretation is linked to a table, figure, code mechanism, or citation.
- Negative and null findings are visible, not confined to supplementary text.
- No causal biological inference from simulation alone.

---

## P5 — Adaptation and recovery endpoint reporting

**Objective:** Report adaptation honestly in the presence of episodes that never reach the threshold.

**Frozen endpoint**

`T_adapt` is the first post-fault time at which forward speed reaches at least 90% of measured pre-fault speed and remains there for 2.5 s. If never reached, `T_adapt=None`.

**Actions**

1. Report threshold-reached counts/proportions for every controller.
2. Do not compute an ordinary mean latency over reached episodes and present it as an unconditional controller latency.
3. If latency distributions are added, use censoring-aware analysis:
   - Kaplan–Meier curves;
   - median time-to-recovery where estimable;
   - confidence intervals;
   - prespecified handling of trial end.
4. Keep Table 1 and Figures 9–10 aligned with the sustained-threshold definition.
5. Distinguish steady-state recovery ratio from time-to-threshold.
6. Treat hormone settling time and gait-frequency CV as optional new endpoints requiring P0 reopening, tests, and rerun; do not add them from selected trajectories alone.

**Current verified counts**

- C1: 10/80.
- C2: 37/80.
- C3: 26/80.
- C4: 34/80.
- C5: 58/80.
- C6: 59/80.

**Validation**

- No fallback duration masquerades as latency.
- Tables, captions, and prose use the same threshold and sustained duration.
- Not-reached episodes remain visible in denominators.

---

## P6 — Paired statistics, ablation, sensitivity, and multiplicity

**Objective:** Make every inferential claim match the factorial design and avoid selective significance reporting.

**Actions**

1. Preserve `(fault_scenario, seed)` as the benchmark paired unit.
2. Preserve `(scenario, seed)` as the ablation paired unit.
3. Declare planned endpoints, directional alternatives, baseline comparisons, and the Holm family before interpreting p-values.
4. Report paired effect sizes and confidence intervals alongside adjusted p-values.
5. Replace any exception path that creates artificial significance with conservative failure or explicit analysis error.
6. For identical paired samples, report `p=1`, effect `0`, and no warning/NaN.
7. Clarify that C4 is excluded from non-oracle superiority claims and is not a universal upper bound.
8. Add ablation uncertainty intervals if the table remains readable; otherwise move full intervals to supplementary material.
9. Treat parameter sensitivity as descriptive unless its grid, seeds, and multiplicity plan are prespecified.
10. If many parameter combinations are compared, add permutation tests and appropriate family-wise or false-discovery control.
11. Record exact seeds, workers, and avoidance of nested parallelism.

**Files likely to change**

- `analysis/statistics_publication.py`
- `experiments/run_ablation_study.py`
- `experiments/run_sensitivity_analysis.py`
- `tests/test_adversarial_stress.py`
- generated Tables 1–3 and supplementary tables

**Validation**

- Benchmark comparisons use 80 paired cells.
- Ablation comparisons use 30 paired cells when all planned records are present.
- One documented Holm family covers the 20 primary benchmark tests.
- No Mann–Whitney test is presented as the primary test for matched episodes.
- No NaN, fabricated fallback p-value, or unlabelled exploratory inference.

---

## P7 — Quantitative captions and final submission QA

**Objective:** Ensure every figure and table is self-contained, numerically correct, and submission-ready.

**Caption requirements**

Each caption should state, where relevant:

1. quantity shown and units;
2. controller/scenario/seed sample size;
3. aggregation and uncertainty definition;
4. statistical unit and correction method;
5. threshold/censoring definition;
6. whether the panel is descriptive or inferential;
7. one evidence-supported takeaway;
8. a limitation when a selected trajectory is shown.

**Actions**

1. Cross-check every caption number against regenerated JSON/tables.
2. Remove stale trajectory-specific numbers unless derived from the displayed trajectory file.
3. Label Figures 7 and 9 as descriptive.
4. State that Figure 10 pools eight scenarios into three fault-type groups with unequal cell sizes.
5. Ensure recovery values above 100% are explained.
6. Standardize terminology, symbols, units, controller names, and joint indexing.
7. Verify all figure files at publication resolution and inspect visual legibility.
8. Run final claim search for withdrawn values and phrases.
9. Compile with `latexmk`, inspect the PDF page by page, and review the log.
10. Prepare a submission inventory: `.tex`, `.bib`, class/style files, figure files, supplementary files, and reproducibility statement.

**Final verification commands**

```bash
python3 -m pytest -q
python3 analysis/statistics_publication.py
python3 analysis/generate_iop_latex_manuscript.py
latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript_bioinspiration.tex
```

Run LaTeX from:

`E:/hermes-projects/snake_hermes_2/results/publication`

**Final exit gate**

- Tests pass with no warnings.
- Datasets have planned counts and no invalid numerics.
- No unsupported-claim regression.
- All figures and citations resolve.
- No undefined reference/citation or LaTeX error.
- PDF is manually inspected for clipping, unreadable text, and table overflow.
- No commit, push, or submission occurs without explicit approval.

---

## Execution order and dependencies

```text
P0 evidence freeze
  ├── P1 literature grounding
  ├── P2 architecture communication
  └── P3 abstract framing
        ↓
P4 evidence-bounded interpretation
        ↓
P5 censoring-aware adaptation reporting
        ↓
P6 paired statistics and sensitivity control
        ↓
P7 captions, compile, visual QA, submission inventory
```

Any P1–P7 edit that introduces a new metric, new experiment, changed controller, new parameter grid, or changed statistical family returns the project to P0 for tests, rerun, and evidence regeneration.

## Risks and trade-offs

1. Stronger biological language may improve narrative but is not justified without biological measurements; retain analogy language.
2. More metrics increase multiple-testing burden and should not be added merely to improve apparent novelty.
3. C5–C6 null results weaken the bypass claim but improve scientific credibility.
4. Recovery above 100% is mathematically valid under the ratio definition but requires clear explanation.
5. Generated manuscript copies can become stale; keep generator regression tests mandatory.
6. The repository has unrelated modified/untracked work; avoid cleanup or broad staging during manuscript revisions.
