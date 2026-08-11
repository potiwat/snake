# Simulation Validation and Capability Benchmark Plan

> **For Hermes:** Use this plan as the implementation and verification checklist.

**Goal:** ตรวจสอบ simulation configuration ให้ถูกต้อง และประเมินความสามารถของ snake robot หลัง fault ด้วย task-level locomotion metrics ที่ไม่พึ่ง `recovery_ratio` หรือ `recovery_time` เพียงอย่างเดียว

**Architecture:** แยกงานเป็น 3 gates: (1) configuration/fault integrity, (2) metric validity, (3) paired healthy-versus-fault capability benchmark. ใช้ raw trajectory จาก PyBullet เดียวกันในการคำนวณทุก metric และใช้ healthy reference ที่จับคู่ controller, condition และ seed เดียวกัน

**Tech Stack:** Python 3, PyBullet, NumPy, Matplotlib, pytest

---

## Current Verified State

- Robot model: 9 segments, 8 revolute yaw joints
- Physics/control timestep: 0.005 s, 200 Hz
- Environments: FLAT, LOW_FRICTION, VARIABLE_FRICTION, INCLINE
- Faults: NONE, LOCKED, FREE, PARTIAL_TORQUE
- `LOCKED` uses mechanical fixed constraint and commanded torque 0
- `VARIABLE_FRICTION` has surface friction values 0.25, 0.8, 1.2
- Metrics use explicit model forward axis `-Y`
- Heading and lateral drift use windowed trajectory displacement
- Current regression tests: 8 passed

## Gate 1: Configuration Integrity

1. Run all environment/fault combinations.
2. Verify joint count, joint type, joint axis and timestep.
3. Verify torque semantics:
   - NONE: normal command
   - LOCKED: 0 N·m and mechanical angle hold
   - FREE: 0 N·m
   - PARTIAL: `gamma_f * MAX_TORQUE`
4. Verify multi-joint fault state and fault-type transitions.
5. Record any mechanical-lock numerical drift separately from controller performance.

**Validation:** `PYTHONPATH=. python3 -m pytest -q` plus focused PyBullet matrix checks.

## Gate 2: Metric Validity

1. Use the explicit forward axis `(0, -1)` for the current model.
2. Compute forward velocity by projection, not by `vx` alone.
3. Compute forward progress from post-fault displacement.
4. Compute lateral drift as accumulated absolute lateral displacement over windows.
5. Compute heading deviation from windowed displacement vectors.
6. Report stall fraction and bounded performance-loss AUC.
7. Test synthetic trajectories:
   - forward motion along `-Y`
   - pure lateral motion
   - lateral zigzag that cancels at the endpoint
   - backward motion
8. Run a short real C5 PyBullet episode and verify all metric keys and bounds.

**Validation:** metric regression tests, Python compilation, and ad-hoc real-run verification.

## Gate 3: Paired Capability Benchmark

### Conditions

- Controllers: C1, C2, C3, C4, C5, C6
- Environments: start with FLAT; add other environments as separate robustness analyses
- Faults: LOCKED, FREE, PARTIAL_TORQUE
- Fault joints: 1, 3, 5
- Seeds: shared across controllers for paired comparisons
- Healthy reference: same controller, environment, joint configuration and seed with no fault
- Fault time and duration: freeze before opening benchmark outcomes

### Primary capability outcomes

- Post-fault forward progress
- Forward-progress retention relative to matched healthy reference
- Stall fraction degradation relative to healthy reference
- Heading deviation degradation
- Lateral drift degradation
- Survival/no-fall status

### Secondary outcomes

- Forward velocity and velocity-deficit AUC
- Energy per meter / cost of transport
- Joint tracking error
- Torque saturation fraction
- Mechanical-lock drift

### Success definition

Do not define success from one scalar. A fault episode is successful only if it:

- maintains positive forward progress;
- does not exceed the pre-registered stall degradation threshold;
- does not exceed the heading/lateral degradation threshold;
- does not fall or violate the safety condition.

Thresholds must be calibrated from healthy runs and frozen before confirmatory comparison.

## Analysis and Reporting

1. Save raw episode records with controller, environment, fault, joint, seed, protocol and metrics.
2. Keep healthy and fault results separate but paired by identifiers.
3. Plot distributions and paired differences, not only means.
4. Report all controllers and all conditions, including null/negative results.
5. Use bootstrap confidence intervals and paired permutation tests.
6. Apply Bonferroni correction over all planned metrics and contrasts.
7. Do not use the current legacy `results/` summaries as confirmatory evidence unless regenerated under the frozen protocol.

## Planned Files

- Modify: `analysis/metrics.py`
- Test: `tests/test_metrics.py`
- Modify or add: `analysis/plot_capability_metrics.py`
- Add: `results/validation/capability_metrics_healthy_calibration.png`
- Add: `results/validation/capability_metrics_healthy_calibration.json`
- Add later: paired benchmark raw data and statistical tables

## Risks and Open Questions

- C5/C6 currently show large healthy lateral drift; this may be a real controller behavior and must not be hidden by normalization.
- C2 has very low healthy forward progress and should remain a weak baseline, not define success thresholds.
- Fixed `-Y` forward axis is valid for the current model convention; if body orientation or spawn direction changes, the protocol must update explicitly.
- Mechanical lock drift around 1e-3 rad was observed in a multi-joint probe and should be reported separately.
- A 10-second smoke benchmark is for execution validation only, not publication evidence.
