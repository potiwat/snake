"""Paired controller contrasts for the frozen Snake Hermes protocol.

For each fault/joint/seed cell, this compares the proposed controller's paired
fault-minus-healthy delta to the same delta for a declared control controller.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.statistics_paired_capability import ALPHA, bootstrap_mean_ci, sign_flip_pvalue


FAULTS = ("locked", "free", "partial_torque")
PRIMARY_METRIC = "forward_progress_delta"
DEFAULT_PROPOSED = "C5"
DEFAULT_CONTROLS = ("C1", "C2", "C3", "C4", "C6")


def _record_key(record: dict) -> tuple[str, str, int, int]:
    return (
        record["controller"],
        record["fault"],
        int(record["fault_joint"]),
        int(record["seed"]),
    )


def _lookup(records: list[dict], environment: str) -> dict[tuple[str, str, int, int], dict]:
    filtered = [record for record in records if record["environment"] == environment]
    lookup = {_record_key(record): record for record in filtered}
    if len(lookup) != len(filtered):
        raise ValueError(f"duplicate controller/fault/joint/seed records for {environment}")
    return lookup


def analyze(
    payload: dict,
    proposed_controller: str = DEFAULT_PROPOSED,
    control_controllers: tuple[str, ...] = DEFAULT_CONTROLS,
    environment: str = "flat",
    metric: str = PRIMARY_METRIC,
    n_permutations: int = 5000,
    n_bootstrap: int = 5000,
) -> dict:
    lookup = _lookup(payload["records"], environment)
    proposed_keys = sorted(
        key for key in lookup if key[0] == proposed_controller and key[1] in FAULTS
    )
    if not proposed_keys:
        raise ValueError(f"no proposed-controller records for {proposed_controller=} {environment=}")

    tests = []
    for control_index, control in enumerate(control_controllers):
        for fault_index, fault in enumerate(FAULTS):
            differences = []
            for _, proposed_fault, joint, seed in proposed_keys:
                if proposed_fault != fault:
                    continue
                proposed = lookup[(proposed_controller, fault, joint, seed)]["paired_delta"][metric]
                control_key = (control, fault, joint, seed)
                if control_key not in lookup:
                    raise ValueError(f"missing matched record: {control_key}")
                control_value = lookup[control_key]["paired_delta"][metric]
                if proposed is None or control_value is None:
                    raise ValueError(f"non-finite primary metric for {control_key}")
                differences.append(float(proposed) - float(control_value))
            seed_offset = 10000 + control_index * 100 + fault_index
            ci_low, ci_high = bootstrap_mean_ci(differences, n_bootstrap, seed_offset + 5000)
            tests.append(
                {
                    "environment": environment,
                    "proposed_controller": proposed_controller,
                    "control_controller": control,
                    "fault": fault,
                    "metric": metric,
                    "n": len(differences),
                    "mean_difference": sum(differences) / len(differences),
                    "bootstrap_ci_95": [ci_low, ci_high],
                    "permutation_p": sign_flip_pvalue(differences, n_permutations, seed_offset),
                    "direction": "positive means proposed controller has less fault-induced loss",
                }
            )
    alpha_bonferroni = ALPHA / len(tests)
    for test in tests:
        test["alpha_bonferroni"] = alpha_bonferroni
        test["significant_after_bonferroni"] = test["permutation_p"] < alpha_bonferroni
    return {
        "analysis": "paired controller contrast on fault-minus-healthy deltas",
        "input_protocol": payload.get("protocol", {}),
        "environment": environment,
        "proposed_controller": proposed_controller,
        "control_controllers": list(control_controllers),
        "metric": metric,
        "n_tests": len(tests),
        "alpha_global": ALPHA,
        "alpha_bonferroni": alpha_bonferroni,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "tests": tests,
        "interpretation_note": "Only use as confirmatory inference when controllers, contrasts, seed list, and SESOI were frozen before outcomes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--environment", default="flat")
    parser.add_argument("--proposed", default=DEFAULT_PROPOSED)
    parser.add_argument("--controls", nargs="+", default=list(DEFAULT_CONTROLS))
    parser.add_argument("--permutations", type=int, default=5000)
    parser.add_argument("--bootstrap", type=int, default=5000)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = analyze(
        payload,
        proposed_controller=args.proposed,
        control_controllers=tuple(args.controls),
        environment=args.environment,
        n_permutations=args.permutations,
        n_bootstrap=args.bootstrap,
    )
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"saved {args.output}")
    print(f"tests={result['n_tests']}")
    print(f"alpha_bonferroni={result['alpha_bonferroni']:.12g}")


if __name__ == "__main__":
    main()
