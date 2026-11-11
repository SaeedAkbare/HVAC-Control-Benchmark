import json
from dataclasses import replace
import pytest
from hvac_benchmark.sensitivity import (
    Acceptance, classify, freeze_settings, read_freeze, main, run_study,
)


def metrics():
    return {
        "controller": "open_loop", "equipment_audit_passed": True,
        "replay_audit_passed": True, "recovery_reached_target": True,
        "fallback_calls": 0, "actuator_overrides": 0,
        "operation_temperature_max_violation_c": 0.0,
        "operation_temperature_violation_hours": 0.0,
        "operation_temperature_degree_hours": 0.0,
        "operation_co2_max_violation_ppm": 0.0,
        "operation_co2_violation_hours": 0.0,
        "operation_co2_ppm_hours": 0.0,
    }


def solve(gap=0.0):
    return {"solver_incumbent_valid": True, "solve_fallback": False, "solver_gap": gap}


@pytest.mark.parametrize("field,value", [
    ("operation_temperature_violation_hours", 0.51),
    ("operation_co2_violation_hours", 0.26),
    ("operation_temperature_max_violation_c", 0.51),
    ("operation_co2_max_violation_ppm", 101),
])
def test_magnitude_and_duration_are_independent_acceptance_gates(field, value):
    observed = metrics()
    observed[field] = value
    decision = classify(observed, [solve()])
    assert decision["equipment_acceptable"]
    assert not decision["practical_acceptable"]
    assert not decision["economic_screen_pass"]


def test_feasible_and_comfortable_does_not_certify_an_economic_comparison():
    decision = classify(metrics(), [solve(0.8)])
    assert decision["modeled_incumbents_valid"]
    assert decision["practical_acceptable"]
    assert not decision["solver_quality_acceptable"]
    assert not decision["economic_screen_pass"]


def test_physical_audit_and_recovery_cannot_be_replaced_by_a_good_gap():
    for field in ("equipment_audit_passed", "recovery_reached_target"):
        observed = metrics()
        observed[field] = False
        assert not classify(observed, [solve()])["practical_acceptable"]


def candidate(period, budget, passed=True):
    return {
        "stage": "budget", "case": "nominal", "period": period,
        "controller": "open_loop", "budget_s": budget,
        "temperature_penalty": 100.0, "co2_penalty": 100.0,
        "economic_screen_pass": passed,
    }


def test_selection_requires_both_nominal_periods_and_excludes_heldout():
    rows = [candidate("winter", 0.5), candidate("summer", 0.5, False),
            candidate("winter", 2), candidate("summer", 2)]
    frozen = freeze_settings(rows)
    assert frozen["qualification"] == "nominal_open_loop_qualified"
    assert frozen["open_loop_budget_s"] == 2
    assert frozen["mpc_budget_s"] == 2  # Separately predeclared, not inferred from this win.
    with pytest.raises(ValueError, match="nominal"):
        freeze_settings(rows + [{**candidate("winter", 2), "stage": "heldout"}])


def test_unqualified_fallback_is_explicit_and_frozen_file_detects_edits(tmp_path):
    frozen = freeze_settings([candidate("winter", 0.5, False), candidate("summer", 0.5, False)])
    assert frozen["qualification"] == "unqualified_diagnostic_anchor"
    assert frozen["open_loop_budget_s"] == 30
    path = tmp_path / "frozen-settings.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")
    assert read_freeze(path) == frozen
    frozen["temperature_penalty"] = 1000
    path.write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        read_freeze(path)


def test_large_mpc_matrix_needs_explicit_cli_opt_in(monkeypatch):
    def never_run(*args, **kwargs):
        pytest.fail("oversized experiment launched without opt-in")
    monkeypatch.setattr("hvac_benchmark.sensitivity.run_study", never_run)
    with pytest.raises(SystemExit) as error:
        main(["--stage", "all", "--mpc-budget", "30"])
    assert error.value.code == 2


def test_previous_outputs_are_preserved(tmp_path):
    existing = tmp_path / "report.md"
    existing.write_text("keep this result", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        run_study(tmp_path, stage="smoke", plots=False)
    assert existing.read_text(encoding="utf-8") == "keep this result"
