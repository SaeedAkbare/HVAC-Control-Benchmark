from dataclasses import replace
import pytest
from hvac_benchmark.config import Model
from hvac_benchmark.scenarios import CASES, DEVELOPMENT, PERIODS, forecast, generate, suite


@pytest.mark.parametrize("case", CASES)
def test_scenarios_are_reproducible_and_keep_announced_prices(case):
    first = generate(PERIODS[0], case)
    second = generate(PERIODS[0], case)
    assert first == second
    assert all(a.price == b.price for a, b in zip(first.plan, first.realized))
    assert all(point.price > 0 for point in first.plan)


def test_weather_error_persists_and_updates_without_seeing_future_truth():
    scenario = generate(PERIODS[0], "weather_severe")
    nominal = generate(PERIODS[0], "nominal")
    assert scenario.plan == nominal.plan
    for k in range(40, 64):  # 10:00 through 15:45: one coherent cold event.
        assert scenario.realized[k].outdoor - scenario.plan[k].outdoor == pytest.approx(-6)
    before = forecast(scenario.plan, 28, 24, scenario.realized[28], 0, 0.25)
    control = forecast(nominal.plan, 28, 24, nominal.realized[28], 0, 0.25)
    assert before == control  # Future weather event cannot leak into the forecast.
    updated = forecast(scenario.plan, 44, 8, scenario.realized[44], 0, 0.25)
    assert updated[0] == scenario.realized[44]
    assert updated[-1].outdoor != scenario.realized[51].outdoor
    # Only the plan and current observation can alter this interface.
    changed_future = replace(scenario, realized=scenario.realized[:45] + nominal.realized[45:])
    assert forecast(changed_future.plan, 44, 8, changed_future.realized[44], 0, 0.25) == updated


def test_occupancy_surprise_changes_both_sources_and_is_not_anticipated():
    scenario = generate(PERIODS[1], "occupancy_severe")
    early = forecast(scenario.plan, 0, 40, scenario.realized[0], 0, 0.25)
    assert early[24].people == 0
    assert scenario.realized[24].people == 40
    updated = forecast(scenario.plan, 24, 40, scenario.realized[24], 0, 0.25)
    assert all(point.people == 40 for point in updated)
    assert Model().occupant_heat * scenario.realized[24].people == pytest.approx(4.8)
    assert Model().occupant_co2 * scenario.realized[24].people == pytest.approx(0.72)


def test_loss_mismatch_does_not_change_controller_plan_or_disturbances():
    nominal = generate(PERIODS[2], "nominal")
    mismatch = generate(PERIODS[2], "loss_severe")
    assert mismatch.plan == nominal.plan
    assert mismatch.realized == nominal.realized
    assert mismatch.plant.ua == pytest.approx(1.5 * Model().ua)


def test_full_suite_is_four_seasons_and_seven_cases_without_tuning_seed():
    cases = suite("full")
    assert len(cases) == 28
    assert len({s.name for s in cases}) == 28
    assert len({s.seed for s in cases}) == 4
    assert DEVELOPMENT.seed not in {s.seed for s in cases}


def test_weather_event_does_not_repeat_during_terminal_recovery():
    scenario = generate(PERIODS[0], "weather_severe")
    assert len(scenario.realized) == 96 + 64
    for actual, announced in zip(scenario.realized[96:], scenario.plan[96:]):
        assert actual == announced
        assert actual.people == 0
