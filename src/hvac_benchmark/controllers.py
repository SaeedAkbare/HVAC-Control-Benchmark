"""Rule control, frozen day-ahead schedules and receding-horizon MILP."""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from .config import Action, Forcing, INITIAL, Model, MODES, Settings, State, comfort
from .physics import coefficients, fan_power, limit_action, step


def thermostat(state: State, observed: Forcing, model: Model,
               dt: float, recovery: bool = False) -> Action:
    """Deadband thermostat + current-occupancy ventilation; ignores prices."""
    low, high, cap = comfort(observed.people)
    target = None
    if recovery:
        target, cap = INITIAL.temperature, INITIAL.co2
    elif state.temperature < low + 0.4:
        target = low + 0.4
    elif state.temperature > high - 0.4:
        target = high - 0.4
    # Steady dilution target has a 150 ppm margin; feedback adds a purge.
    fresh_need = (observed.people * model.occupant_co2 * 1e6
                  / max(50.0, cap - 150 - model.outside_co2)
                  * model.density / 3600)
    if state.co2 > cap - 50:
        fresh_need = max(fresh_need, 1.5)
    candidates = [i for i, mode in enumerate(MODES)
                  if mode.fresh + 1e-9 >= fresh_need]
    if not candidates:
        candidates = [len(MODES) - 1]
    if target is None:
        return limit_action(state, Action(candidates[0]), observed, model, dt)[0]
    choices = []
    for mode_id in candidates:
        if not MODES[mode_id].total:
            continue
        a, b, _, _ = coefficients(model, mode_id, dt)
        q = ((target - a * state.temperature - (1 - a) * observed.outdoor) / b
             - model.background_heat - model.occupant_heat * observed.people)
        action = limit_action(state, Action(mode_id, max(q, 0), max(-q, 0)),
                              observed, model, dt)[0]
        error = abs(step(state, action, observed, model, dt).temperature - target)
        choices.append((round(error, 8), fan_power(action.mode, model), mode_id, action))
    return min(choices, key=lambda item: item[:3])[3]


@dataclass
class Plan:
    actions: list[Action]
    predicted: list[State]
    seconds: float
    status: str
    gap: float | None
    fallback: bool
    objective: float | None
    diagnostics: dict | None = None


class LinearModel:
    """Tiny row builder; indicator constants come from finite variable bounds."""

    def __init__(self):
        self.lower, self.upper, self.cost, self.integer = [], [], [], []
        self.rows, self.columns, self.values, self.lo, self.hi = [], [], [], [], []

    def variables(self, n, lower, upper, cost=0.0, integer=False):
        start = len(self.lower)
        self.lower.extend([lower] * n)
        self.upper.extend([upper] * n)
        self.cost.extend([cost] * n)
        self.integer.extend([int(integer)] * n)
        return np.arange(start, start + n)

    def add(self, row, lower=-np.inf, upper=np.inf):
        r = len(self.lo)
        for col, value in row.items():
            if value:
                self.rows.append(r)
                self.columns.append(int(col))
                self.values.append(float(value))
        self.lo.append(lower)
        self.hi.append(upper)

    def conditional(self, row, lower, upper, selector):
        minimum = sum(v * (self.lower[j] if v >= 0 else self.upper[j])
                      for j, v in row.items())
        maximum = sum(v * (self.upper[j] if v >= 0 else self.lower[j])
                      for j, v in row.items())
        # When z=1 these recover the original limits; z=0 relaxes them fully.
        if isfinite(upper):
            big_m = max(0.0, maximum - upper)
            self.add({**row, selector: big_m}, upper=upper + big_m)
        if isfinite(lower):
            big_m = max(0.0, lower - minimum)
            self.add({**row, selector: -big_m}, lower=lower - big_m)

    def matrix(self):
        return coo_matrix((self.values, (self.rows, self.columns)),
                          shape=(len(self.lo), len(self.lower))).tocsc()


def _fallback(state, future, model, settings, started, status, diagnostics=None):
    actions, predicted = [], []
    for forcing in future:
        action = thermostat(state, forcing, model, settings.dt)
        state = step(state, action, forcing, model, settings.dt)
        actions.append(action)
        predicted.append(state)
    return Plan(actions, predicted, perf_counter() - started,
                status, None, True, None, diagnostics)


def optimize_plan(state: State, future: tuple[Forcing, ...],
                  model: Model, settings: Settings) -> Plan:
    """Finite-flow MILP with exact mode dynamics and continuous coil power.

    Comfort limits are soft; hardware limits are hard. Predicted CO2 is in
    thousands of ppm for numerical scaling. No plant truth is accepted here.
    """
    started = perf_counter()
    n, modes = len(future), len(MODES)
    if n == 0:
        raise ValueError("empty prediction horizon")
    lp = LinearModel()
    temp = lp.variables(n + 1, -40.0, 65.0)
    co2 = lp.variables(n + 1, 0.0, 30.0)
    lp.lower[temp[0]] = lp.upper[temp[0]] = state.temperature
    lp.lower[co2[0]] = lp.upper[co2[0]] = state.co2 / 1000
    z = lp.variables(n * modes, 0.0, 1.0, integer=True).reshape(n, modes)
    heat = lp.variables(n, 0.0, model.heat_max)
    cool = lp.variables(n, 0.0, model.cool_max)
    heating = lp.variables(n, 0.0, 1.0, integer=True)
    tl = lp.variables(n, 0.0, np.inf, settings.temperature_penalty * settings.dt)
    tu = lp.variables(n, 0.0, np.inf, settings.temperature_penalty * settings.dt)
    cs = lp.variables(n, 0.0, np.inf, settings.co2_penalty * settings.dt)
    for k, forcing in enumerate(future):
        low, high, cap = comfort(forcing.people)
        lp.add({int(j): 1.0 for j in z[k]}, 1.0, 1.0)
        lp.add({heat[k]: 1, heating[k]: -model.heat_max}, upper=0)
        lp.add({cool[k]: 1, heating[k]: model.cool_max}, upper=model.cool_max)
        lp.add({heat[k]: 1, z[k, 0]: model.heat_max}, upper=model.heat_max)
        lp.add({cool[k]: 1, z[k, 0]: model.cool_max}, upper=model.cool_max)
        lp.add({temp[k + 1]: 1, tl[k]: 1}, lower=low)
        lp.add({temp[k + 1]: 1, tu[k]: -1}, upper=high)
        lp.add({co2[k + 1]: 1, cs[k]: -1}, upper=cap / 1000)
        lp.cost[heat[k]] = settings.dt * model.gas_price / model.heat_efficiency
        lp.cost[cool[k]] = settings.dt * forcing.price / model.cooling_cop
        gains = model.background_heat + model.occupant_heat * forcing.people
        for m, mode in enumerate(MODES):
            a, b, d, g = coefficients(model, m, settings.dt)
            rhs = (1 - a) * forcing.outdoor + b * gains
            lp.conditional({temp[k + 1]: 1, temp[k]: -a, heat[k]: -b, cool[k]: b},
                           rhs, rhs, z[k, m])
            rhs_c = ((1 - d) * model.outside_co2 + g * forcing.people) / 1000
            lp.conditional({co2[k + 1]: 1, co2[k]: -d},
                           rhs_c, rhs_c, z[k, m])
            lp.cost[z[k, m]] = settings.dt * forcing.price * fan_power(m, model)
            if mode.total:
                # cp*flow*Ts = cp*(total-fresh)*T + cp*fresh*Tout + heat-cool.
                supply_low = model.cp * (mode.total * model.supply_min
                                         - mode.fresh * forcing.outdoor)
                supply_high = model.cp * (mode.total * model.supply_max
                                          - mode.fresh * forcing.outdoor)
                for endpoint in (temp[k], temp[k + 1]):
                    lp.conditional(
                        {heat[k]: 1, cool[k]: -1,
                         endpoint: model.cp * (mode.total - mode.fresh)},
                        supply_low, supply_high, z[k, m])
    matrix = lp.matrix()
    try:
        result = milp(
            np.asarray(lp.cost),
            integrality=np.asarray(lp.integer),
            bounds=Bounds(lp.lower, lp.upper),
            constraints=LinearConstraint(matrix, lp.lo, lp.hi),
            options={"time_limit": settings.time_limit,
                     "mip_rel_gap": settings.mip_gap, "presolve": True},
        )
    except (ValueError, RuntimeError) as exc:
        return _fallback(state, future, model, settings, started,
                         f"fallback_exception_{type(exc).__name__}")
    x = result.x
    valid = result.status in (0, 1) and x is not None and np.isfinite(x).all()
    if valid:
        rows = matrix @ x
        integers = np.asarray(lp.integer, dtype=bool)
        valid = (np.all(x >= np.asarray(lp.lower) - 1e-5)
                 and np.all(x <= np.asarray(lp.upper) + 1e-5)
                 and np.all(rows >= np.asarray(lp.lo) - 1e-5)
                 and np.all(rows <= np.asarray(lp.hi) + 1e-5)
                 and np.all(abs(x[integers] - np.rint(x[integers])) <= 1e-5))
    def finite_attribute(name):
        value = getattr(result, name, None)
        return float(value) if value is not None and np.isfinite(value) else None

    diagnostics = {
        "raw_status": int(result.status),
        "message": str(getattr(result, "message", "")),
        "incumbent_valid": bool(valid),
        "incumbent_objective": finite_attribute("fun"),
        "dual_bound": finite_attribute("mip_dual_bound"),
        "gap": finite_attribute("mip_gap"),
        "node_count": finite_attribute("mip_node_count"),
        "energy_objective": None,
        "temperature_penalty_objective": None,
        "co2_penalty_objective": None,
    }
    if not valid:
        return _fallback(state, future, model, settings, started,
                         f"fallback_status_{result.status}", diagnostics)
    costs = np.asarray(lp.cost)
    energy_indices = np.concatenate((heat, cool, z.ravel()))
    diagnostics.update({
        "energy_objective": float(costs[energy_indices] @ x[energy_indices]),
        "temperature_penalty_objective": float(costs[tl] @ x[tl] + costs[tu] @ x[tu]),
        "co2_penalty_objective": float(costs[cs] @ x[cs]),
    })
    actions = [Action(int(np.argmax(x[z[k]])), max(0.0, float(x[heat[k]])),
                      max(0.0, float(x[cool[k]]))) for k in range(n)]
    predicted = [State(float(x[temp[k + 1]]), float(x[co2[k + 1]]) * 1000)
                 for k in range(n)]
    gap = getattr(result, "mip_gap", None)
    gap = float(gap) if gap is not None and np.isfinite(gap) else None
    return Plan(actions, predicted, perf_counter() - started,
                "optimal_tolerance" if result.status == 0 else "feasible_limit",
                gap, False, float(result.fun), diagnostics)


@dataclass
class Decision:
    action: Action
    solve: Plan | None = None


class Thermostat:
    name = "thermostat"

    def act(self, index, state, future, model, settings):
        return Decision(thermostat(state, future[0], model, settings.dt))


class OpenLoop:
    name = "open_loop"

    def __init__(self):
        self.plan = None

    def act(self, index, state, future, model, settings):
        if self.plan is None:
            self.plan = optimize_plan(state, future, model, settings)
            return Decision(self.plan.actions[index], self.plan)
        return Decision(self.plan.actions[index])


class MPC:
    name = "mpc"

    def act(self, index, state, future, model, settings):
        plan = optimize_plan(state, future[:settings.horizon_steps], model, settings)
        return Decision(plan.actions[0], plan)


CONTROLLERS = {"thermostat": Thermostat, "open_loop": OpenLoop, "mpc": MPC}
