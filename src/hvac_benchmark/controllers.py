"""Rule control, frozen day-ahead schedules and receding-horizon MILP."""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from .config import Action, Forcing, INITIAL, Model, MODES, Settings, State, comfort
from .physics import coefficients, coil_interval, energy, fan_power, limit_action, step


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
    """Small sparse row builder; no big-M dynamic equalities."""

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

    def matrix(self):
        return coo_matrix((self.values, (self.rows, self.columns)),
                          shape=(len(self.lo), len(self.lower))).tocsc()


def comfort_ok(state, forcing):
    """Existing reporting/validation tolerances, not comfort allowances."""
    low, high, cap = comfort(forcing.people)
    return (low - 1e-5 <= state.temperature <= high + 1e-5
            and state.co2 <= cap + 0.01)


def one_step_endpoint_reachable(state, forcing, model, dt):
    """Analytic diagnostic over all modes; does not excuse a violated start."""
    low, high, cap = comfort(forcing.people)
    for m in range(len(MODES)):
        free = step(state, Action(m), forcing, model, dt)
        if free.co2 > cap + 0.01:
            continue
        lower, upper = coil_interval(state, forcing, model, m, dt)
        _, b, _, _ = coefficients(model, m, dt)
        lower = max(lower, (low - free.temperature) / b)
        upper = min(upper, (high - free.temperature) / b)
        if lower <= upper + 1e-8:
            return True
    return False


def _build_problem(state, future, model, settings):
    """Exact finite-mode disaggregation, cost only, hard interval comfort.

    Mode-specific start/end states are zero when their binary is zero.
    Their sums equal the common states. For the selected mode, the exact
    transition and both supply limits apply. Bounds come from the unchanged
    comfort bands, intersected at boundaries where occupancy changes.
    """
    n, modes = len(future), len(MODES)
    lp = LinearModel()
    limits = [comfort(f.people) for f in future]
    bounds = []
    for k in range(n + 1):
        adjacent = limits[max(0, k - 1):min(n, k + 1)]
        bounds.append((max(v[0] for v in adjacent),
                       min(v[1] for v in adjacent),
                       min(v[2] for v in adjacent) / 1000))
    temp = lp.variables(n + 1, 0.0, 27.0)
    co2 = lp.variables(n + 1, 0.0, 1.4)
    for k, (lower, upper, cap) in enumerate(bounds):
        lp.lower[temp[k]], lp.upper[temp[k]], lp.upper[co2[k]] = lower, upper, cap
    # Equalities preserve the observed initial state; no clipping or warm-up.
    lp.add({temp[0]: 1}, state.temperature, state.temperature)
    lp.add({co2[0]: 1}, state.co2 / 1000, state.co2 / 1000)
    z = lp.variables(n * modes, 0.0, 1.0, integer=True).reshape(n, modes)
    heating = lp.variables(n, 0.0, 1.0, integer=True)
    heat = lp.variables(n * modes, 0.0, model.heat_max).reshape(n, modes)
    cool = lp.variables(n * modes, 0.0, model.cool_max).reshape(n, modes)
    t0 = lp.variables(n * modes, 0.0, 27.0).reshape(n, modes)
    t1 = lp.variables(n * modes, 0.0, 27.0).reshape(n, modes)
    c0 = lp.variables(n * modes, 0.0, 1.4).reshape(n, modes)
    c1 = lp.variables(n * modes, 0.0, 1.4).reshape(n, modes)
    for k, forcing in enumerate(future):
        lp.add({int(j): 1 for j in z[k]}, 1, 1)
        lp.add({**{int(j): 1 for j in heat[k]}, heating[k]: -model.heat_max}, upper=0)
        lp.add({**{int(j): 1 for j in cool[k]}, heating[k]: model.cool_max},
               upper=model.cool_max)
        for part, common in ((t0, temp[k]), (t1, temp[k + 1]),
                             (c0, co2[k]), (c1, co2[k + 1])):
            lp.add({**{int(j): 1 for j in part[k]}, common: -1}, 0, 0)
        gains = model.background_heat + model.occupant_heat * forcing.people
        for m, mode in enumerate(MODES):
            selector, h, q = z[k, m], heat[k, m], cool[k, m]
            for part, index in ((t0, k), (t1, k + 1)):
                lower, upper, _ = bounds[index]
                lp.add({part[k, m]: 1, selector: -lower}, lower=0)
                lp.add({part[k, m]: 1, selector: -upper}, upper=0)
            for part, index in ((c0, k), (c1, k + 1)):
                lp.add({part[k, m]: 1, selector: -bounds[index][2]}, upper=0)
            lp.add({h: 1, selector: -model.heat_max}, upper=0)
            lp.add({q: 1, selector: -model.cool_max}, upper=0)
            if mode.total == 0:
                lp.upper[h] = lp.upper[q] = 0.0
            a, b, d, g = coefficients(model, m, settings.dt)
            rhs = (1 - a) * forcing.outdoor + b * gains
            rhs_c = ((1 - d) * model.outside_co2 + g * forcing.people) / 1000
            lp.add({t1[k, m]: 1, t0[k, m]: -a, h: -b, q: b, selector: -rhs}, 0, 0)
            lp.add({c1[k, m]: 1, c0[k, m]: -d, selector: -rhs_c}, 0, 0)
            if mode.total:
                for endpoint in (t0[k, m], t1[k, m]):
                    row = {h: 1, q: -1, endpoint: model.cp * (mode.total - mode.fresh)}
                    lower = model.cp * (mode.total * model.supply_min - mode.fresh * forcing.outdoor)
                    upper = model.cp * (mode.total * model.supply_max - mode.fresh * forcing.outdoor)
                    lp.add({**row, selector: -lower}, lower=0)
                    lp.add({**row, selector: -upper}, upper=0)
            lp.cost[h] = settings.dt * model.gas_price / model.heat_efficiency
            lp.cost[q] = settings.dt * forcing.price / model.cooling_cop
            lp.cost[selector] = settings.dt * forcing.price * fan_power(m, model)
    return lp, (temp, co2, z, heat, cool)


def _fallback(state, future, model, settings, started, status, diagnostics):
    """Emergency rule rollout, explicitly not a hard-feasible optimization."""
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
    """Minimize only energy cost, subject to hard comfort and equipment."""
    started = perf_counter()
    if not future:
        raise ValueError("empty prediction horizon")
    diagnostics = {
        "raw_status": None, "message": "", "incumbent_valid": False,
        "incumbent_objective": None, "dual_bound": None, "gap": None,
        "node_count": None, "energy_objective": None,
        "prediction_hard_feasible": False,
        "initial_comfort_satisfied": comfort_ok(state, future[0]),
        "one_step_endpoint_reachable": one_step_endpoint_reachable(
            state, future[0], model, settings.dt),
    }
    if not diagnostics["initial_comfort_satisfied"]:
        diagnostics["message"] = "Fixed initial state violates hard comfort at the interval start."
        return _fallback(state, future, model, settings, started,
                         "initial_state_infeasible", diagnostics)
    lp, (temp, co2, z, heat, cool) = _build_problem(state, future, model, settings)
    matrix = lp.matrix()
    try:
        result = milp(
            np.asarray(lp.cost), integrality=np.asarray(lp.integer),
            bounds=Bounds(lp.lower, lp.upper),
            constraints=LinearConstraint(matrix, lp.lo, lp.hi),
            options={"time_limit": settings.time_limit,
                     "mip_rel_gap": settings.mip_gap, "presolve": True})
    except (ValueError, RuntimeError) as exc:
        diagnostics["message"] = str(exc)
        return _fallback(state, future, model, settings, started,
                         "solver_exception_" + type(exc).__name__, diagnostics)

    def finite_attribute(name):
        value = getattr(result, name, None)
        return float(value) if value is not None and np.isfinite(value) else None

    diagnostics.update({
        "raw_status": int(result.status), "message": str(getattr(result, "message", "")),
        "incumbent_objective": finite_attribute("fun"),
        "dual_bound": finite_attribute("mip_dual_bound"),
        "gap": finite_attribute("mip_gap"), "node_count": finite_attribute("mip_node_count"),
    })
    x = getattr(result, "x", None)
    valid = result.status in (0, 1) and x is not None and np.isfinite(x).all()
    if valid:
        rows = matrix @ x
        integers = np.asarray(lp.integer, dtype=bool)
        valid = (np.all(x >= np.asarray(lp.lower) - 1e-5)
                 and np.all(x <= np.asarray(lp.upper) + 1e-5)
                 and np.all(rows >= np.asarray(lp.lo) - 1e-5)
                 and np.all(rows <= np.asarray(lp.hi) + 1e-5)
                 and np.all(abs(x[integers] - np.rint(x[integers])) <= 1e-5))
    if not valid:
        status = {1: "time_limit_no_incumbent", 2: "proven_infeasible",
                  3: "unbounded", 4: "solver_failure"}.get(int(result.status), "invalid_incumbent")
        if x is not None and result.status in (0, 1):
            status = "invalid_incumbent"
        return _fallback(state, future, model, settings, started, status, diagnostics)

    actions = [Action(int(np.argmax(x[z[k]])), max(0.0, float(sum(x[heat[k]]))),
                      max(0.0, float(sum(x[cool[k]])))) for k in range(len(future))]
    predicted, current, objective = [], state, 0.0
    for k, (action, forcing) in enumerate(zip(actions, future, strict=True)):
        next_state = step(current, action, forcing, model, settings.dt)
        _, changed = limit_action(current, action, forcing, model, settings.dt)
        if (changed or min(action.heat, action.cool) > 1e-5
                or not comfort_ok(current, forcing) or not comfort_ok(next_state, forcing)
                or abs(next_state.temperature - x[temp[k + 1]]) > 1e-5
                or abs(next_state.co2 - 1000 * x[co2[k + 1]]) > 0.01):
            return _fallback(state, future, model, settings, started,
                             "invalid_prediction", diagnostics)
        electricity, gas = energy(action, model, settings.dt)
        objective += electricity * forcing.price + gas * model.gas_price
        predicted.append(next_state)
        current = next_state
    if diagnostics["incumbent_objective"] is None or abs(objective - result.fun) > 1e-5:
        return _fallback(state, future, model, settings, started,
                         "invalid_objective", diagnostics)
    diagnostics.update(incumbent_valid=True, prediction_hard_feasible=True,
                       energy_objective=objective)
    return Plan(actions, predicted, perf_counter() - started,
                "optimal_tolerance" if result.status == 0 else "feasible_limit",
                diagnostics["gap"], False, objective, diagnostics)


@dataclass
class Decision:
    action: Action
    solve: Plan | None = None
    active_plan: Plan | None = None
    plan_index: int = 0


class Thermostat:
    name = "thermostat"

    def act(self, index, state, future, model, settings):
        return Decision(thermostat(state, future[0], model, settings.dt))


class OpenLoop:
    name = "open_loop"

    def __init__(self):
        self.plan = None

    def act(self, index, state, future, model, settings):
        fresh = self.plan is None
        if fresh:
            self.plan = optimize_plan(state, future, model, settings)
        return Decision(self.plan.actions[index], self.plan if fresh else None,
                        self.plan, index)


class MPC:
    name = "mpc"

    def act(self, index, state, future, model, settings):
        plan = optimize_plan(state, future[:settings.horizon_steps], model, settings)
        return Decision(plan.actions[0], plan, plan, 0)


CONTROLLERS = {"thermostat": Thermostat, "open_loop": OpenLoop, "mpc": MPC}
