from analysis.statistics_robustness_capability import analyze


def test_environment_stratified_analysis_counts_all_tests():
    delta = {
        "forward_progress_delta": -1.0,
        "lateral_drift_delta": 0.1,
        "stall_fraction_delta": 0.1,
        "heading_deviation_deg_delta": 1.0,
        "fall_fraction_delta": 0.0,
        "torque_saturation_fraction_delta": -0.1,
        "survival_delta": 0.0,
    }
    payload = {
        "records": [
            {"environment": environment, "fault": fault, "paired_delta": delta}
            for environment in ("low_friction", "variable_friction", "incline")
            for fault in ("locked", "free", "partial_torque")
        ]
    }

    result = analyze(payload, n_permutations=100, n_bootstrap=100)

    assert result["n_tests"] == 63
    assert result["alpha_bonferroni"] == 0.05 / 63
    assert all(test["n"] == 1 for test in result["tests"])
