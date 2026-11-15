import numpy as np
import pytest
from scipy.optimize import OptimizeResult
from hvac_benchmark import controllers
from hvac_benchmark.config import Action, Forcing, INITIAL, Model, Settings, State
from hvac_benchmark.controllers import MPC, OpenLoop, Plan, optimize_plan
from hvac_benchmark.evaluation import evaluate, physical_audit
from hvac_benchmark.physics import energy, step
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
        plan.diagnostics["energy_objective"], abs=1e-5)
    assert plan.diagnostics["prediction_hard_feasible"] is True
    state, states = INITIAL, [INITIAL]
    for action, forcing, predicted in zip(plan.actions, future, plan.predicted):
        assert min(action.heat, action.cool) <= 1e-5
        state = step(state, action, forcing, model, settings.dt)
        states.append(state)
        assert state.temperature == pytest.approx(predicted.temperature, abs=1e-4)
        assert state.co2 == pytest.approx(predicted.co2, abs=0.03)
    physical_audit(states, plan.actions, future, model)


def test_no_incumbent_uses_explicit_emergency_rule_without_feasibility_claim(monkeypatch):
    monkeypatch.setattr(controllers, "milp", lambda *a, **k: OptimizeResult(status=1, x=None, mip_dual_bound=0.25, fun=None))
    future = (Forcing(5, 24, 0.2),) * 3
    plan = optimize_plan(INITIAL, future, Model(), Settings())
    assert plan.fallback
    assert plan.status == "time_limit_no_incumbent"
    assert plan.diagnostics["prediction_hard_feasible"] is False
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


@pytest.mark.parametrize("raw, expected", [(1, "time_limit_no_incumbent"),
                                           (2, "proven_infeasible"),
                                           (3, "unbounded"), (4, "solver_failure")])
def test_failure_causes_stay_distinct_and_never_claim_feasible(monkeypatch, raw, expected):
    monkeypatch.setattr(controllers, "milp", lambda *a, **k: OptimizeResult(
        status=raw, x=None, message="synthetic solver status"))
    plan = optimize_plan(INITIAL, (Forcing(5, 24, 0.2),), Model(), Settings())
    assert plan.status == expected
    assert plan.fallback and plan.objective is None
    assert not plan.diagnostics["incumbent_valid"]
    assert not plan.diagnostics["prediction_hard_feasible"]


def test_initial_violation_is_reported_without_clipping_or_softening(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a known fixed-state contradiction needs no solver")
    monkeypatch.setattr(controllers, "milp", forbidden)
    plan = optimize_plan(State(19, 1500), (Forcing(10, 24, 0.2),), Model(), Settings())
    assert plan.status == "initial_state_infeasible"
    assert plan.fallback and plan.objective is None
    assert plan.diagnostics["raw_status"] is None
    assert plan.diagnostics["initial_comfort_satisfied"] is False


def test_capacity_infeasibility_is_proven_not_purchased_with_penalties():
    plan = optimize_plan(State(20, 600), (Forcing(-80, 24, 0.2),), Model(), Settings(time_limit=5))
    assert plan.status == "proven_infeasible"
    assert plan.diagnostics["raw_status"] == 2
    assert plan.diagnostics["one_step_endpoint_reachable"] is False
    assert plan.fallback and plan.objective is None


def test_known_occupancy_transition_requires_comfort_at_interval_start():
    future = (Forcing(5, 0, 0.2), Forcing(5, 24, 0.2))
    plan = optimize_plan(State(19.9, 600), future, Model(), Settings(time_limit=5))
    assert not plan.fallback
    # The first interval is empty; its end is also the occupied interval start.
    assert plan.predicted[0].temperature >= 20 - 1e-5
    for previous, following, forcing in zip([State(19.9, 600)] + plan.predicted,
                                            plan.predicted, future):
        assert controllers.comfort_ok(previous, forcing)
        assert controllers.comfort_ok(following, forcing)


def test_cost_objective_is_exactly_the_two_energy_meters():
    future = tuple(Forcing(34, 24, p) for p in (0.3, 0.15, 0.4, 0.2))
    model, settings = Model(), Settings(time_limit=5)
    plan = optimize_plan(State(23.9, 850), future, model, settings)
    assert not plan.fallback
    metered = sum(e * forcing.price + g * model.gas_price
                  for action, forcing in zip(plan.actions, future)
                  for e, g in [energy(action, model, settings.dt)])
    assert plan.objective == pytest.approx(metered, abs=1e-6)
    assert not any("penalty" in key for key in vars(settings))


def test_forecast_feasibility_does_not_hide_realized_occupancy_violation():
    scenario = generate(PERIODS[2], "occupancy_severe", hours=4, start_hour=4)
    metrics, rows = evaluate(scenario, "open_loop", Settings(time_limit=2, horizon_steps=16))
    assert metrics["all_predictions_hard_feasible"] is True
    assert metrics["fallback_operation_steps"] == 0
    assert metrics["operation_co2_max_violation_ppm"] > 100
    assert metrics["operation_hard_comfort_satisfied"] is False
    assert metrics["comparison_eligible"] is False
    assert all(r["active_prediction_hard_feasible"] for r in rows[:16])


def test_frozen_fallback_counts_affected_steps_not_only_one_solve(monkeypatch):
    monkeypatch.setattr(controllers, "milp", lambda *a, **k: OptimizeResult(status=1, x=None))
    scenario = generate(PERIODS[0], "nominal", hours=1, start_hour=8)
    metrics, rows = evaluate(scenario, "open_loop", Settings())
    assert metrics["fallback_calls"] == 1
    assert metrics["fallback_operation_steps"] == 4
    assert metrics["time_limit_no_incumbent_calls"] == 1
    assert metrics["all_predictions_hard_feasible"] is False
    assert metrics["comparison_eligible"] is False
    assert rows[1]["solve_status"] == "frozen_fallback"


@pytest.mark.parametrize("state, outdoor", [(State(20.1, 950), 5), (State(23.9, 950), 35)])
def test_two_step_disaggregation_matches_independent_exhaustive_lp(state, outdoor):
    # Enumerate modes and heat/cool signs; derive a dense LP in signed coil
    # powers directly from the physical equations, independently of the MILP.
    from itertools import product
    from scipy.optimize import linprog
    from hvac_benchmark.config import MODES, comfort
    from hvac_benchmark.physics import coefficients, fan_power
    model, dt = Model(), 0.25
    future = (Forcing(outdoor, 24, 0.3), Forcing(outdoor, 24, 0.15))
    best = float("inf")
    for modes in product(range(len(MODES)), repeat=2):
        for signs in product((False, True), repeat=2):
            aub, bub, qbounds, costs = [], [], [], []
            t_const, t_coeff, carbon, fan = state.temperature, np.zeros(2), state.co2, 0.0
            possible = True
            for k, (m, heating, forcing) in enumerate(zip(modes, signs, future)):
                mode = MODES[m]
                a, b, d, g = coefficients(model, m, dt)
                next_const = a * t_const + (1 - a) * forcing.outdoor + b * (
                    model.background_heat + model.occupant_heat * forcing.people)
                next_coeff = a * t_coeff.copy()
                next_coeff[k] += b
                next_carbon = d * carbon + (1 - d) * model.outside_co2 + g * forcing.people
                low, high, cap = comfort(forcing.people)
                if max(carbon, next_carbon) > cap + 1e-8:
                    possible = False
                    break
                for constant, vector in ((t_const, t_coeff), (next_const, next_coeff)):
                    aub.extend([vector.copy(), -vector.copy()])
                    bub.extend([high - constant, constant - low])
                    if mode.total:
                        recirc = 1 - mode.fresh / mode.total
                        supply_const = recirc * constant + mode.fresh / mode.total * forcing.outdoor
                        supply_coeff = recirc * vector.copy()
                        supply_coeff[k] += 1 / (model.cp * mode.total)
                        aub.extend([supply_coeff, -supply_coeff])
                        bub.extend([model.supply_max - supply_const, supply_const - model.supply_min])
                qbounds.append((0, model.heat_max) if heating else (-model.cool_max, 0))
                if mode.total == 0:
                    qbounds[-1] = (0, 0)
                costs.append(dt * (model.gas_price / model.heat_efficiency if heating
                                   else -forcing.price / model.cooling_cop))
                fan += dt * forcing.price * fan_power(m, model)
                t_const, t_coeff, carbon = next_const, next_coeff, next_carbon
            if possible:
                result = linprog(costs, A_ub=aub, b_ub=bub, bounds=qbounds, method="highs")
                if result.success:
                    best = min(best, result.fun + fan)
    assert np.isfinite(best)
    plan = optimize_plan(state, future, model, Settings(time_limit=10, mip_gap=1e-9))
    assert not plan.fallback, plan.status
    assert plan.objective == pytest.approx(best, abs=1e-5)
