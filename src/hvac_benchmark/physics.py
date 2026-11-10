"""Exact zero-order-hold, well-mixed temperature and CO2 dynamics."""
from math import exp, expm1, isfinite
from .config import Action, Forcing, Model, MODES, State


def coefficients(model: Model, mode: int, dt: float):
    fresh = MODES[mode].fresh
    loss = model.ua + model.cp * fresh
    a = exp(-loss * dt / model.capacitance)
    b = -expm1(-loss * dt / model.capacitance) / loss
    rate = 3600.0 * fresh / (model.density * model.volume)
    d = exp(-rate * dt)
    source = 1e6 * model.occupant_co2 / model.volume
    g = source * (-expm1(-rate * dt) / rate if rate else dt)
    return a, b, d, g


def step(state: State, action: Action, forcing: Forcing,
         model: Model, dt: float) -> State:
    a, b, d, g = coefficients(model, action.mode, dt)
    gains = model.background_heat + model.occupant_heat * forcing.people
    return State(
        a * state.temperature + (1 - a) * forcing.outdoor
        + b * (gains + action.heat - action.cool),
        d * state.co2 + (1 - d) * model.outside_co2 + g * forcing.people,
    )


def fan_power(mode: int, model: Model) -> float:
    return model.fan_max * (MODES[mode].total / 1.5) ** 3


def supply_temperature(state: State, action: Action,
                       forcing: Forcing, model: Model) -> float | None:
    mode = MODES[action.mode]
    if mode.total == 0:
        return None
    fraction = mode.fresh / mode.total
    mixed = (1 - fraction) * state.temperature + fraction * forcing.outdoor
    return mixed + (action.heat - action.cool) / (model.cp * mode.total)


def coil_interval(state: State, forcing: Forcing, model: Model,
                  mode_id: int, dt: float) -> tuple[float, float]:
    """Bounds on constant signed coil power, including both supply endpoints.

    T(t) is monotone within a held-input interval, so endpoint limits suffice.
    """
    mode = MODES[mode_id]
    if not mode.total:
        return 0.0, 0.0
    a, b, _, _ = coefficients(model, mode_id, dt)
    fraction = mode.fresh / mode.total
    recirc = 1 - fraction
    cpflow = model.cp * mode.total
    free_end = a * state.temperature + (1 - a) * forcing.outdoor + b * (
        model.background_heat + model.occupant_heat * forcing.people
    )
    mix_start = recirc * state.temperature + fraction * forcing.outdoor
    mix_end = recirc * free_end + fraction * forcing.outdoor
    end_slope = recirc * b + 1 / cpflow
    lower = max(-model.cool_max, cpflow * (model.supply_min - mix_start),
                (model.supply_min - mix_end) / end_slope)
    upper = min(model.heat_max, cpflow * (model.supply_max - mix_start),
                (model.supply_max - mix_end) / end_slope)
    return lower, upper


def limit_action(state: State, requested: Action, forcing: Forcing,
                 model: Model, dt: float) -> tuple[Action, bool]:
    """Common ideal actuator protection, using current physical conditions.

    Infeasible airflow mode -> off. Otherwise saturate signed coil power.
    The protection is applied equally to all controllers and its uses are logged.
    """
    if not (0 <= requested.mode < len(MODES)):
        raise ValueError("unknown airflow mode")
    if not all(isfinite(x) and x >= 0 for x in (requested.heat, requested.cool)):
        raise ValueError("coil powers must be finite and nonnegative")
    lo, hi = coil_interval(state, forcing, model, requested.mode, dt)
    if lo > hi:
        return Action(0), True
    q = min(hi, max(lo, requested.heat - requested.cool))
    applied = Action(requested.mode, max(q, 0.0), max(-q, 0.0))
    changed = (abs(applied.heat - requested.heat) > 1e-5
               or abs(applied.cool - requested.cool) > 1e-5)
    return applied, changed


def energy(action: Action, model: Model, dt: float) -> tuple[float, float]:
    """Meter energy: electricity (fan + chiller), then gas input, in kWh."""
    return ((fan_power(action.mode, model) + action.cool / model.cooling_cop) * dt,
            action.heat / model.heat_efficiency * dt)
