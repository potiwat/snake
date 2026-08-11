"""Environment-stratified paired analysis for the robustness benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.statistics_paired_capability import (
    ALPHA,
    METRICS,
    N_BOOTSTRAP,
    N_PERMUTATIONS,
    _finite,
    bootstrap_mean_ci,
    paired_mean_difference,
    sign_flip_pvalue,
)

ENVIRONMENTS = ("low_friction", "variable_friction", "incline")
FAULTS = ("locked", "free", "partial_torque")


def analyze(payload: dict, n_permutations: int = N_PERMUTATIONS, n_bootstrap: int = N_BOOTSTRAP) -> dict:
    tests = []
    for environment_index, environment in enumerate(ENVIRONMENTS):
        for fault_index, fault in enumerate(FAULTS):
            records = [
                record for record in payload["records"]
                if record["environment"] == environment and record["fault"] == fault
            ]
            for metric_index, metric in enumerate(METRICS):
                values = [record["paired_delta"].get(metric) for record in records]
                finite = _finite(values)
                seed = 10000 + environment_index * 1000 + fault_index * 100 + metric_index
                p_value = sign_flip_pvalue(values, n_permutations, seed)
                ci_low, ci_high = bootstrap_mean_ci(values, n_bootstrap, seed + 5000)
                tests.append({
                    "environment": environment,
                    "fault": fault,
                    "metric": metric,
                    "n": int(len(finite)),
                    "mean_difference": paired_mean_difference(finite.tolist()),
                    "bootstrap_ci_95": [ci_low, ci_high],
                    "permutation_p": p_value,
                })
    n_tests = len(tests)
    alpha_bonferroni = ALPHA / n_tests
    for test in tests:
        test["alpha_bonferroni"] = alpha_bonferroni
        test["significant_after_bonferroni"] = bool(test["permutation_p"] < alpha_bonferroni)
    return {
        "analysis": "environment-stratified paired sign-flip permutation + bootstrap mean CI",
        "input_protocol": payload.get("protocol", {}),
        "environments": list(ENVIRONMENTS),
        "faults": list(FAULTS),
        "metrics": list(METRICS),
        "n_tests": n_tests,
        "alpha_global": ALPHA,
        "alpha_bonferroni": alpha_bonferroni,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "tests": tests,
        "interpretation_note": "Each environment is analyzed separately; do not aggregate it with the flat benchmark.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="results/paired_capability_robustness.json")
    parser.add_argument("--output", default="results/paired_capability_robustness_statistics.json")
    parser.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    parser.add_argument("--bootstrap", type=int, default=N_BOOTSTRAP)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = analyze(payload, args.permutations, args.bootstrap)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"saved {output}")
    print(f"tests={result['n_tests']}")
    print(f"alpha_bonferroni={result['alpha_bonferroni']:.12g}")
    print(f"significant_after_bonferroni={sum(t['significant_after_bonferroni'] for t in result['tests'])}/{result['n_tests']}")


if __name__ == "__main__":
    main()
