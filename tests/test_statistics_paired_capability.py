from analysis.statistics_paired_capability import analyze, bootstrap_mean_ci, sign_flip_pvalue


def test_sign_flip_pvalue_detects_nonzero_constant_difference():
    p_value = sign_flip_pvalue([1.0] * 12, n_permutations=5000, seed=1)
    assert p_value < 0.01


def test_bootstrap_ci_contains_constant_mean():
    low, high = bootstrap_mean_ci([2.0] * 8, n_bootstrap=1000, seed=1)
    assert low == 2.0
    assert high == 2.0


def test_analysis_counts_all_fault_metric_tests_and_applies_bonferroni():
    metrics = {
        "forward_progress_delta": -1.0,
        "lateral_drift_delta": 0.1,
        "stall_fraction_delta": 0.1,
        "heading_deviation_deg_delta": 1.0,
        "fall_fraction_delta": 0.0,
        "torque_saturation_fraction_delta": -0.1,
        "survival_delta": 0.0,
    }
    payload = {
        "protocol": {"seeds": [7]},
        "records": [
            {"fault": fault, "paired_delta": metrics}
            for fault in ("locked", "free", "partial_torque")
        ],
    }

    result = analyze(payload, n_permutations=100, n_bootstrap=100)

    assert result["n_tests"] == 21
    assert result["alpha_bonferroni"] == 0.05 / 21
    assert all(test["n"] == 1 for test in result["tests"])
