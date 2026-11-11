from dataclasses import replace
import numpy as np
import pytest
from scipy.optimize import OptimizeResult
from hvac_benchmark import controllers
from hvac_benchmark.config import Action, Forcing, INITIAL, Model, Settings, State
from hvac_benchmark.controllers import MPC, OpenLoop, Plan, optimize_plan
from hvac_benchmark.evaluation import evaluate, physical_audit
from hvac_benchmark.physics import step
from hvac_benchmark.scenarios import PERIODS, generate


def test_milp_predictions_replay_under_the_matched_model():
    model, settings = Model(), Settings(time_limit=10)
    future = tuple(Forcing(7, 24, price) for price in (0.15, 0.20, 0.30, 0.25))
    plan = optimize_plan(INITIAL, future, model, settings)
    assert not plan.fallback, plan.status
    assert plan.diagnostics["incumbent_valid"] is True
    assert plan.diagnostics["raw_status"] in (0, 1)
    assert plan.diagnostics["dual_bound"] <= plan.objective + 1e-5
    assert plan.objective == pytest.approx(
        plan.diagnostics["energy_objective"]
        + plan.diagnostics["temperature_penalty_objective"]
        + plan.diagnostics["co2_penalty_objective"], abs=1e-5)
    state, states = INITIAL, [INITIAL]
    for action, forcing, predicted in zip(plan.actions, future, plan.predicted):
        assert min(action.heat, action.cool) <= 1e-5
        state = step(state, action, forcing, model, settings.dt)
        states.append(state)
        assert state.temperature == pytest.approx(predicted.temperature, abs=1e-4)
        assert state.co2 == pytest.approx(predicted.co2, abs=0.03)
    physical_audit(states, plan.actions, future, model)


def test_no_incumbent_uses_an_explicit_feasible_rule_plan(monkeypatch):
    monkeypatch.setattr(controllers, "milp", lambda *a, **k: OptimizeResult(status=1, x=None, mip_dual_bound=0.25, fun=None))
    future = (Forcing(5, 24, 0.2),) * 3
    plan = optimize_plan(INITIAL, future, Model(), Settings())
    assert plan.fallback
    assert plan.status == "fallback_status_1"
    assert plan.diagnostics["dual_bound"] == 0.25
    assert plan.diagnostics["incumbent_objective"] is None
    assert plan.diagnostics["incumbent_valid"] is False
    assert len(plan.actions) == 3
    physical_audit([INITIAL] + plan.predicted, plan.actions, future, Model())


def test_invalid_incumbent_is_not_silently_executed(monkeypatch):
    def invalid(cost, **kwargs):
        return OptimizeResult(status=0, x=np.zeros(len(cost)))
    monkeypatch.setattr(controllers, "milp", invalid)
    plan = optimize_plan(INITIAL, (Forcing(5, 24, 0.2),), Model(), Settings())
    assert plan.fallback
    assert plan.diagnostics["incumbent_valid"] is False


def test_open_loop_keeps_initial_schedule_and_mpc_only_uses_first_action(monkeypatch):
    calls = []

    def fake(state, future, model, settings):
        calls.append(state)
        marker = len(calls)
        return Plan([Action(1, heat=marker + k) for k in range(len(future))],
                    [state] * len(future), 0.01, "test", 0, False, 0)

    monkeypatch.setattr(controllers, "optimize_plan", fake)
    future, model, settings = (Forcing(10, 24, 0.2),) * 4, Model(), Settings()
    open_loop = OpenLoop()
    first = open_loop.act(0, INITIAL, future, model, settings)
    second = open_loop.act(1, State(18, 1500), future[1:], model, settings)
    assert len(calls) == 1
    assert first.action.heat == 1
    assert second.action.heat == 2
    mpc = MPC()
    third = mpc.act(0, INITIAL, future, model, settings)
    fourth = mpc.act(1, State(18, 1500), future[1:], model, settings)
    assert len(calls) == 3
    assert third.action.heat == 2
    assert fourth.action.heat == 3  # Not the second action (4) of the new plan.
    assert calls[-1] == State(18, 1500)


def test_closed_loop_metrics_include_common_recovery_and_independent_replay():
    scenario = generate(PERIODS[0], "nominal", hours=1, start_hour=8)
    metrics, rows = evaluate(scenario, "thermostat", Settings())
    assert len(rows) == 4 + Settings().recovery_steps
    assert sum(r["phase"] == "recovery" for r in rows) == Settings().recovery_steps
    assert metrics["total_cost_eur"] == pytest.approx(
        metrics["operation_cost_eur"] + metrics["recovery_cost_eur"])
    assert metrics["replay_temperature_error_c"] < 1e-6
    assert metrics["replay_co2_error_ppm"] < 1e-4
    assert metrics["solve_calls"] == 0


def test_controller_receives_nominal_model_under_loss_mismatch(monkeypatch):
    seen = []
    original = controllers.Thermostat.act

    def spy(self, index, state, future, model, settings):
        seen.append(model.ua)
        return original(self, index, state, future, model, settings)

    monkeypatch.setattr(controllers.Thermostat, "act", spy)
    scenario = generate(PERIODS[0], "loss_severe", hours=1, start_hour=8)
    evaluate(scenario, "thermostat", Settings())
    assert seen == [Model().ua] * 4
    assert scenario.plant.ua != Model().ua


def test_common_recovery_can_restore_a_cold_zone_with_severe_heat_loss():
    # The initial six-hour protocol left some winter runs with energy debt.
    # Start conservatively below the occupied band and exercise the shared rule.
    from hvac_benchmark.physics import limit_action
    scenario = generate(PERIODS[0], "loss_severe")
    state, nominal, settings = State(16.0, 1400.0), Model(), Settings()
    for forcing in scenario.realized[scenario.evaluation_steps:]:
        request = controllers.thermostat(state, forcing, nominal, settings.dt, recovery=True)
        applied, _ = limit_action(state, request, forcing, scenario.plant, settings.dt)
        state = step(state, applied, forcing, scenario.plant, settings.dt)
    assert abs(state.temperature - 22.0) <= 0.05
    assert state.co2 <= 601.0
