from analysis.plot_publication import (
    adaptation_threshold_reached,
    get_fault_location_recovery,
)


def test_adaptation_threshold_success_requires_observed_latency():
    assert adaptation_threshold_reached({"t_adapt": 3.5, "recovery_success": False})
    assert not adaptation_threshold_reached({"t_adapt": None, "recovery_success": True})


def test_fault_location_comparison_uses_matched_locked_zero_scenarios_only():
    records = [
        {
            "controller": "C5",
            "fault_scenario": "locked_0rad_head",
            "metrics": {"recovery_ratio": 1.2},
        },
        {
            "controller": "C5",
            "fault_scenario": "locked_0rad_mid",
            "metrics": {"recovery_ratio": 0.8},
        },
        {
            "controller": "C5",
            "fault_scenario": "locked_0rad_tail",
            "metrics": {"recovery_ratio": 1.0},
        },
        {
            "controller": "C5",
            "fault_scenario": "limp_mid",
            "metrics": {"recovery_ratio": 0.0},
        },
    ]

    location_values = get_fault_location_recovery(records, "C5")

    assert location_values == {
        "locked_0rad_head": [120.0],
        "locked_0rad_mid": [80.0],
        "locked_0rad_tail": [100.0],
    }
