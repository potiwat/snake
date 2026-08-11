# Confirmatory Protocol Review — Solver-800 Snake Hermes

Status: REVIEW REQUIRED — do not launch new confirmatory outcomes from this file.

## Verified baseline

- Physics configuration: `SimConfig.NUM_SOLVER_ITERATIONS = 800`.
- Frozen exploratory/execution artifacts verified with `bash reproduce.sh --verify`:
  - flat: 108 paired fault records, 21 tests
  - robustness: 324 paired fault records, 63 tests
  - representative videos: 16 clips, 4 manifests, 30 fps, 300 frames, 10.0 s
- Current seed set is `{7, 26}`. It is sufficient for implementation validation but not publication-level confirmation.
- Mechanical-lock drift is a separate configuration-integrity gate, not a locomotion-performance endpoint.

## Evidence boundary

The existing solver-800 outputs remain exploratory/execution evidence. They must not be used to select a controller, practical threshold, seed count, terrain subset, or primary outcome for a confirmatory study.

## Proposed fixed design for review

| Item | Proposal | Rationale |
|---|---|---|
| Controllers | C1–C6 | Preserve the already evaluated comparison set; report all conditions. |
| Faults | LOCKED, FREE, PARTIAL_TORQUE | Preserve defined physical fault semantics. |
| Fault joints | 1, 3, 5 | Preserve proximal/mid/distal coverage. |
| Flat protocol | Separate primary confirmatory family | Do not pool flat and terrain robustness effects. |
| Robustness protocol | LOW_FRICTION, VARIABLE_FRICTION, INCLINE 10°; separate secondary/OOD family | Avoid generalization claims from flat data. |
| Duration / onset | 10 s / 4 s | Retain only if approved before new outcomes. |
| Pairing | Same controller, terrain, joint, and seed; healthy in same matched task | Preserves the existing paired design. |
| Multiplicity | Bonferroni; 21 flat tests and 63 terrain-stratified tests | Same explicit test families as the current analysis. |
| Lock integrity | Both onset-inclusive and steady-state drift <= 1e-3 rad for every LOCKED episode | Configuration gate, reported separately. |

## Workload consequences

For the current 6-controller × 3-fault × 3-joint factorial:

| Paired seeds | Flat records | Robustness records | Flat episodes | Robustness episodes |
|---:|---:|---:|---:|---:|
| 2 (current) | 108 | 324 | 144 | 432 |
| 10 | 540 | 1,620 | 720 | 2,160 |
| 20 | 1,080 | 3,240 | 1,440 | 4,320 |

The 20-seed row is a planning reference, not an approved sample size. A seed count, SESOI, and any blinded resizing rule must be frozen before running new outcomes.

## Decisions required before confirmatory execution

1. Approve the controller/fault/joint/terrain matrix or specify changes.
2. Define primary outcomes and physical SESOIs. Do not derive them from the current solver-800 effect sizes.
3. Select a seed count or a blinded variance-only resizing rule with a hard cap.
4. Decide whether terrain robustness is confirmatory or explicitly secondary/OOD.
5. Approve a Git baseline commit, then freeze normalized hashes of code, config, analysis, and protocol before launching outcomes.

## First execution steps after approval

1. Commit the reviewed baseline.
2. Create a checkout-independent freeze-hash registry and fail-closed gate.
3. Run configuration preflight before every batch.
4. Run the approved paired matrix without inspecting/ranking controller outcomes during execution.
5. Run locked statistical analysis, regenerate all plots, and update the research log.
