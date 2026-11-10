from math import exp
import pytest
from hvac_benchmark.config import Action, Forcing, INITIAL, Model, MODES, State
from hvac_benchmark.physics import energy, limit_action, step, supply_temperature
from hvac_benchmark.evaluation import excess, physical_audit, replay


@pytest.mark.parametrize("mode", range(len(MODES)))
def test_exact_step_matches_independent_ode_and_subdivision(mode):
    model, forcing = Model(), Forcing(5.0, 24.0, 0.20)
    action, _ = limit_action(INITIAL, Action(mode, 8.0), forcing, model, 0.25)
    exact = step(INITIAL, action, forcing, model, 0.25)
    numerical = replay(INITIAL, [action], [forcing], model, 0.25)[-1]
    half = step(INITIAL, action, forcing, model, 0.125)
    half = step(half, action, forcing, model, 0.125)
    assert exact.temperature == pytest.approx(numerical.temperature, abs=1e-8)
    assert exact.co2 == pytest.approx(numerical.co2, abs=1e-5)
    assert exact.temperature == pytest.approx(half.temperature, abs=1e-10)
    assert exact.co2 == pytest.approx(half.co2, abs=1e-10)
    physical_audit([INITIAL, numerical], [action], [forcing], model)


def test_zero_flow_co2_is_linear_and_unoccupied_ventilation_decays():
    model = Model()
    forcing = Forcing(22, 24, 0.2)
    result = step(INITIAL, Action(0), forcing, model, 0.25)
    assert result.co2 == pytest.approx(600 + 24 * 0.018 / 960 * 1e6 * 0.25)
    mode = len(MODES) - 1
    result = step(State(22, 1000), Action(mode), Forcing(22, 0, 0.2), model, 0.25)
    rate = MODES[mode].fresh * 3600 / (model.density * model.volume)
    assert result.co2 == pytest.approx(420 + (1000 - 420) * exp(-rate * 0.25))


def test_meter_accounting_keeps_gas_and_electricity_separate():
    model = Model()
    action = Action(3, heat=9.6)
    electric, gas = energy(action, model, 0.25)
    assert gas == pytest.approx(2.5)
    assert electric == pytest.approx(0.6 * (MODES[3].total / 1.5)**3 * 0.25)
    electric2, gas2 = energy(Action(3, cool=6.8), model, 0.25)
    assert electric2 - electric == pytest.approx(0.5)
    assert gas2 == 0


def test_supply_limit_can_disable_an_infeasible_requested_mode():
    forcing, model = Forcing(-25, 24, 0.2), Model()
    action, overridden = limit_action(INITIAL, Action(len(MODES) - 1, cool=16),
                                      forcing, model, 0.25)
    assert overridden
    assert action == Action(0)
    assert supply_temperature(INITIAL, action, forcing, model) is None


def test_exceedance_counts_crossing_duration_and_area():
    area, duration, peak = excess(0, 2, 0, 1, 2)
    assert (area, duration, peak) == pytest.approx((0.5, 1.0, 1.0))
    # x(t)=2*exp(-t), crosses 1 at log(2).
    from math import log
    area, duration, peak = excess(2, 2 * exp(-2), 1, 1, 2)
    assert duration == pytest.approx(log(2))
    assert area == pytest.approx(1 - log(2))
    assert peak == 1
    assert excess(1, 1, 1, 1, 0.25) == (0, 0, 0)
