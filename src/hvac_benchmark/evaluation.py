"""Closed-loop experiment, independent numerical replay and physical metrics."""
from dataclasses import asdict
from math import exp, expm1, log
import numpy as np
from scipy.integrate import solve_ivp
from .config import Action, INITIAL, Model, MODES, Settings, State, comfort
from .controllers import CONTROLLERS, thermostat
from .physics import energy, limit_action, step
from .scenarios import Scenario, forecast


def replay(initial, actions, forcings, plant, dt):
    """Independent ODE implementation, not the optimizer's transition routine."""
    state = np.array([initial.temperature, initial.co2], dtype=float)
    states = [State(*map(float, state))]
    for action, forcing in zip(actions, forcings, strict=True):
        fresh = MODES[action.mode].fresh

        def rhs(_time, y):
            heat_flow = ((plant.ua + plant.cp * fresh) * (forcing.outdoor - y[0])
                         + plant.background_heat + plant.occupant_heat * forcing.people
                         + action.heat - action.cool)
            air_per_hour = fresh / plant.density * 3600
            co2_flow = (air_per_hour * (plant.outside_co2 - y[1])
                        + forcing.people * plant.occupant_co2 * 1e6)
            return [heat_flow / plant.capacitance, co2_flow / plant.volume]

        solution = solve_ivp(rhs, (0.0, dt), state, rtol=1e-10, atol=1e-10)
        if not solution.success:
            raise RuntimeError("independent plant replay failed")
        state = solution.y[:, -1]
        states.append(State(*map(float, state)))
    return states


def excess(x0, x1, rate, bound, dt, tolerance=1e-5):
    """Exact positive exceedance area, duration and peak for monotone dynamics."""
    if abs(x0 - bound) < tolerance:
        x0 = bound
    if abs(x1 - bound) < tolerance:
        x1 = bound
    peak = max(0.0, x0 - bound, x1 - bound)
    if peak == 0:
        return 0.0, 0.0, 0.0
    left, right = 0.0, dt
    linear = abs(rate) < 1e-12
    if linear:
        slope = (x1 - x0) / dt
        equilibrium = None
    else:
        a = exp(-rate * dt)
        equilibrium = (x1 - a * x0) / (-expm1(-rate * dt))
    if (x0 > bound) != (x1 > bound):
        crossing = ((bound - x0) / slope if linear
                    else -log((bound - equilibrium) / (x0 - equilibrium)) / rate)
        crossing = min(dt, max(0.0, crossing))
        if x0 > bound:
            right = crossing
        else:
            left = crossing
    if linear:
        area = (x0 - bound) * (right - left) + slope * (right**2 - left**2) / 2
    else:
        area = ((equilibrium - bound) * (right - left)
                + (x0 - equilibrium) * (exp(-rate * left) - exp(-rate * right)) / rate)
    return max(0.0, area), right - left, peak


def physical_audit(states, actions, forcings, plant):
    """Check recorded inputs directly, without using the actuator limiter."""
    for k, (action, forcing) in enumerate(zip(actions, forcings, strict=True)):
        mode = MODES[action.mode]
        assert -1e-7 <= action.heat <= plant.heat_max + 1e-5
        assert -1e-7 <= action.cool <= plant.cool_max + 1e-5
        assert min(action.heat, action.cool) <= 1e-5
        assert 0 <= mode.fresh <= mode.total <= 1.5
        if mode.total == 0:
            assert action.heat + action.cool <= 1e-5
            continue
        for state in states[k:k + 2]:
            mixed = ((mode.total - mode.fresh) * state.temperature
                     + mode.fresh * forcing.outdoor) / mode.total
            supply = mixed + (action.heat - action.cool) / (plant.cp * mode.total)
            assert plant.supply_min - 1e-5 <= supply <= plant.supply_max + 1e-5


def evaluate(scenario: Scenario, controller_name: str, settings: Settings):
    if abs(settings.dt - scenario.dt) > 1e-10:
        raise ValueError("scenario/controller timestep mismatch")
    if settings.recovery_steps != round(16 / settings.dt):
        raise ValueError("this experiment requires the common sixteen-hour recovery")
    nominal = Model()
    controller = CONTROLLERS[controller_name]()
    state = INITIAL
    states, actions, rows, solves = [state], [], [], []
    n = scenario.evaluation_steps
    count = n + settings.recovery_steps
    for k in range(count):
        observed = scenario.realized[k]
        recovery = k >= n
        solve = None
        if recovery:
            requested = thermostat(state, observed, nominal, settings.dt, recovery=True)
            status = "common_recovery"
        else:
            # The open-loop controller caches its first plan and ignores later calls.
            length = n - k if controller_name == "open_loop" else min(
                settings.horizon_steps, n - k)
            future = forecast(scenario.plan, k, length, observed,
                              scenario.start_hour, settings.dt)
            decision = controller.act(k, state, future, nominal, settings)
            requested, solve = decision.action, decision.solve
            status = solve.status if solve else (
                "frozen_schedule" if controller_name == "open_loop" else "rule")
            if solve:
                solves.append(solve)
        action, changed = limit_action(state, requested, observed,
                                       scenario.plant, settings.dt)
        next_state = step(state, action, observed, scenario.plant, settings.dt)
        electricity, gas = energy(action, scenario.plant, settings.dt)
        low, high, cap = ((21.8, 22.2, 600.0) if recovery else comfort(observed.people))
        rows.append({
            "scenario": scenario.name, "controller": controller_name,
            "step": k, "phase": "recovery" if recovery else "operation",
            "elapsed_h": k * settings.dt,
            "hour": (scenario.start_hour + k * settings.dt) % 24,
            "outdoor_c": observed.outdoor, "planned_outdoor_c": scenario.plan[k].outdoor,
            "people": observed.people, "planned_people": scenario.plan[k].people,
            "electricity_price_eur_kwh": observed.price,
            "temperature_c": state.temperature, "next_temperature_c": next_state.temperature,
            "co2_ppm": state.co2, "next_co2_ppm": next_state.co2,
            "temperature_min_c": low, "temperature_max_c": high, "co2_max_ppm": cap,
            "requested_mode": requested.mode, "mode": action.mode,
            "total_flow_kg_s": MODES[action.mode].total,
            "fresh_flow_kg_s": MODES[action.mode].fresh,
            "requested_heat_kw": requested.heat, "requested_cool_kw": requested.cool,
            "heat_kw": action.heat, "cool_kw": action.cool,
            "electricity_kwh": electricity, "gas_kwh": gas,
            "cost_eur": electricity * observed.price + gas * scenario.plant.gas_price,
            "actuator_override": int(changed), "solve_status": status,
            "solve_seconds": solve.seconds if solve else 0.0,
            "solve_gap": solve.gap if solve else None,
            "predicted_next_temperature_c": solve.predicted[0].temperature if solve else None,
            "predicted_next_co2_ppm": solve.predicted[0].co2 if solve else None,
        })
        actions.append(action)
        state = next_state
        states.append(state)
    checked = replay(INITIAL, actions, scenario.realized[:count], scenario.plant, settings.dt)
    t_error = max(abs(a.temperature - b.temperature) for a, b in zip(states, checked))
    c_error = max(abs(a.co2 - b.co2) for a, b in zip(states, checked))
    if t_error > 1e-6 or c_error > 1e-4:
        raise AssertionError(f"independent replay mismatch: {t_error}, {c_error}")
    physical_audit(checked, actions, scenario.realized[:count], scenario.plant)
    metrics = {
        "scenario": scenario.name, "period": scenario.period, "case": scenario.case,
        "seed": scenario.seed, "controller": controller_name,
        "evaluation_hours": n * settings.dt, "plant_ua_kw_k": scenario.plant.ua,
        "total_cost_eur": sum(r["cost_eur"] for r in rows),
        "total_electricity_kwh": sum(r["electricity_kwh"] for r in rows),
        "total_gas_kwh": sum(r["gas_kwh"] for r in rows),
        "solve_calls": len(solves),
        "solve_seconds_total": sum(s.seconds for s in solves),
        "solve_seconds_mean": float(np.mean([s.seconds for s in solves])) if solves else 0.0,
        "solve_seconds_p95": float(np.percentile([s.seconds for s in solves], 95)) if solves else 0.0,
        "fallback_calls": sum(s.fallback for s in solves),
        "feasible_limit_calls": sum(s.status == "feasible_limit" for s in solves),
        "optimal_tolerance_calls": sum(s.status == "optimal_tolerance" for s in solves),
        "max_reported_mip_gap": max((s.gap for s in solves if s.gap is not None), default=None),
        "actuator_overrides": sum(r["actuator_override"] for r in rows),
        "replay_temperature_error_c": t_error, "replay_co2_error_ppm": c_error,
        "terminal_temperature_c": checked[-1].temperature,
        "terminal_temperature_error_c": abs(checked[-1].temperature - INITIAL.temperature),
        "terminal_co2_ppm": checked[-1].co2,
        "terminal_co2_excess_ppm": max(0.0, checked[-1].co2 - INITIAL.co2),
    }
    for phase, begin, end in (("operation", 0, n), ("recovery", n, count)):
        part = rows[begin:end]
        totals = {"temperature_degree_hours": 0.0, "temperature_violation_hours": 0.0,
                  "temperature_max_violation_c": 0.0, "co2_ppm_hours": 0.0,
                  "co2_violation_hours": 0.0, "co2_max_violation_ppm": 0.0}
        for k in range(begin, end):
            row = rows[k]
            a, b = checked[k:k + 2]
            mode = MODES[actions[k].mode]
            tr = (scenario.plant.ua + scenario.plant.cp * mode.fresh) / scenario.plant.capacitance
            cr = 3600 * mode.fresh / (scenario.plant.density * scenario.plant.volume)
            lower = excess(-a.temperature, -b.temperature, tr,
                           -row["temperature_min_c"], settings.dt)
            upper = excess(a.temperature, b.temperature, tr,
                           row["temperature_max_c"], settings.dt)
            carbon = excess(a.co2, b.co2, cr, row["co2_max_ppm"], settings.dt, tolerance=0.01)
            totals["temperature_degree_hours"] += lower[0] + upper[0]
            totals["temperature_violation_hours"] += lower[1] + upper[1]
            totals["temperature_max_violation_c"] = max(
                totals["temperature_max_violation_c"], lower[2], upper[2])
            totals["co2_ppm_hours"] += carbon[0]
            totals["co2_violation_hours"] += carbon[1]
            totals["co2_max_violation_ppm"] = max(totals["co2_max_violation_ppm"], carbon[2])
        totals.update({
            "cost_eur": sum(r["cost_eur"] for r in part),
            "electricity_kwh": sum(r["electricity_kwh"] for r in part),
            "gas_kwh": sum(r["gas_kwh"] for r in part),
            "peak_electric_kw": max(r["electricity_kwh"] / settings.dt for r in part),
            "peak_gas_kw": max(r["gas_kwh"] / settings.dt for r in part),
        })
        metrics.update({f"{phase}_{key}": value for key, value in totals.items()})
    metrics["recovery_reached_target"] = (
        metrics["terminal_temperature_error_c"] <= 0.05
        and metrics["terminal_co2_excess_ppm"] <= 1.0)
    return metrics, rows
