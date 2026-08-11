"""Honest paired analysis for the frozen snake capability benchmark.

The unit of analysis is one matched controller/environment/joint/seed pair.
No controller condition is treated as an independent replicate across faults.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

METRICS = (
    "forward_progress_delta",
    "lateral_drift_delta",
    "stall_fraction_delta",
    "heading_deviation_deg_delta",
    "fall_fraction_delta",
    "torque_saturation_fraction_delta",
    "survival_delta",
)
FAULTS = ("locked", "free", "partial_torque")
ALPHA = 0.05
N_PERMUTATIONS = 5000
N_BOOTSTRAP = 5000


def _finite(values: list[float | None]) -> np.ndarray:
    return np.asarray([value for value in values if value is not None and np.isfinite(value)], dtype=float)


def paired_mean_difference(values: list[float]) -> float:
    return float(np.mean(values)) if values else float("nan")


def sign_flip_pvalue(values: list[float], n_permutations: int = N_PERMUTATIONS, seed: int = 0) -> float:
    x = _finite(values)
    if len(x) == 0:
        return float("nan")
    observed = abs(float(np.mean(x)))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_permutations, len(x)))
    null = np.abs(np.mean(signs * x, axis=1))
    return float((1 + np.count_nonzero(null >= observed)) / (n_permutations + 1))


def bootstrap_mean_ci(
    values: list[float],
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = 0,
) -> tuple[float, float]:
    x = _finite(values)
    if len(x) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(x), size=(n_bootstrap, len(x)))
    means = np.mean(x[indices], axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def analyze(payload: dict, n_permutations: int = N_PERMUTATIONS, n_bootstrap: int = N_BOOTSTRAP) -> dict:
    records = payload["records"]
    tests = []
    for fault_index, fault in enumerate(FAULTS):
        fault_records = [record for record in records if record["fault"] == fault]
        for metric_index, metric in enumerate(METRICS):
            values = [record["paired_delta"].get(metric) for record in fault_records]
            finite = _finite(values)
            p_value = sign_flip_pvalue(values, n_permutations, seed=1000 + fault_index * 100 + metric_index)
            ci_low, ci_high = bootstrap_mean_ci(values, n_bootstrap, seed=2000 + fault_index * 100 + metric_index)
            tests.append({
                "fault": fault,
                "metric": metric,
                "n": int(len(finite)),
                "mean_difference": paired_mean_difference(finite.tolist()),
                "median_difference": float(np.median(finite)) if len(finite) else float("nan"),
                "bootstrap_ci_95": [ci_low, ci_high],
                "permutation_p": p_value,
            })
    n_tests = len(tests)
    alpha_bonferroni = ALPHA / n_tests if n_tests else float("nan")
    for test in tests:
        test["alpha_bonferroni"] = alpha_bonferroni
        test["significant_after_bonferroni"] = bool(test["permutation_p"] < alpha_bonferroni)
    return {
        "analysis": "paired sign-flip permutation + bootstrap mean CI",
        "input_protocol": payload.get("protocol", {}),
        "metrics": list(METRICS),
        "faults": list(FAULTS),
        "n_tests": n_tests,
        "alpha_global": ALPHA,
        "alpha_bonferroni": alpha_bonferroni,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "tests": tests,
        "interpretation_note": "Descriptive/inferential analysis of the frozen flat-environment benchmark; not a claim of generalization to other environments.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="results/paired_capability_benchmark.json")
    parser.add_argument("--output", default="results/paired_capability_statistics.json")
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
