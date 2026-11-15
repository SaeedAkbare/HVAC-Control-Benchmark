import pytest
from hvac_benchmark.config import Settings
from hvac_benchmark.evaluation import evaluate
from hvac_benchmark.scenarios import DEVELOPMENT, generate
from hvac_benchmark.sensitivity import budget_upper_bound, classify, main, run_study


def test_hard_gate_rejects_any_resolved_physical_excursion():
    scenario = generate(DEVELOPMENT, "nominal", hours=1, start_hour=8)
    metrics, rows = evaluate(scenario, "open_loop", Settings(time_limit=2, horizon_steps=4))
    calls = [r for r in rows if r["solve_called"]]
    assert metrics["comparison_eligible"] is True
    assert classify(metrics, calls)["quality_screen_pass"] is True
    # A valid incumbent and good gap cannot excuse invalid service.
    metrics["valid_service"] = metrics["comparison_eligible"] = False
    assert classify(metrics, calls)["quality_screen_pass"] is False


def test_small_gap_cannot_certify_a_fallback():
    metrics = {"controller": "mpc", "comparison_eligible": False}
    calls = [{"solver_incumbent_valid": False, "solver_prediction_hard_feasible": False,
              "solve_fallback": True, "solver_gap": 0.0}]
    assert classify(metrics, calls)["solver_quality_acceptable"] is False


def test_compute_budget_accounts_for_each_receding_horizon_call():
    assert budget_upper_bound("nominal", (0.5, 2, 10), 2, 2, 1) == 409
    assert budget_upper_bound("all", (0.5, 2, 10), 2, 2, 1) == 1353


def test_large_compute_requires_explicit_opt_in(tmp_path):
    with pytest.raises(SystemExit):
        main(["--stage", "all", "--mpc-budget", "30", "--output", str(tmp_path / "new")])


def test_previous_evidence_is_not_overwritten(tmp_path):
    existing = tmp_path / "metrics.csv"
    existing.write_text("original evidence")
    with pytest.raises(ValueError, match="empty"):
        run_study(tmp_path, stage="smoke")
    assert existing.read_text() == "original evidence"
