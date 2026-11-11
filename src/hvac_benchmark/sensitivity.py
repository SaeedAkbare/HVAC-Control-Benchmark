"""Predeclared budget, penalty, feedback and held-out diagnostics.

This module orchestrates the existing evaluator; it does not implement a
controller, plant model, solver, or a second set of comfort metrics.
"""
import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.metadata import version
import json
from math import isfinite
import os
from pathlib import Path
import platform
from time import perf_counter
from .config import Model, Settings
from .evaluation import evaluate
from .reporting import plot_trajectories, write_csv
from .scenarios import DEVELOPMENT, PERIODS, Period, generate

PROTOCOL = "sensitivity-v1"
BUDGETS = (0.5, 2.0, 10.0, 30.0)
# One weight at a time; the (100, 100) control comes from the budget sweep.
PENALTIES = ((10.0, 100.0), (1000.0, 100.0),
             (100.0, 10.0), (100.0, 1000.0))
HELDOUT = (
    (Period("heldout_spring", 16, 5, 5202, -1), "weather_severe"),
    (Period("heldout_autumn", 13, 5, 5404, 1), "occupancy_severe"),
    (Period("heldout_spring", 16, 5, 5202, -1), "loss_severe"),
)


@dataclass(frozen=True)
class Acceptance:
    # Engineering screening assumptions, not health/regulatory standards.
    temperature_max_c: float = 0.5
    temperature_hours: float = 0.5
    temperature_degree_hours: float = 0.1
    co2_max_ppm: float = 100.0
    co2_hours: float = 0.25
    co2_ppm_hours: float = 25.0
    solver_gap: float = 0.01


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def classify(metrics, solves, criteria=Acceptance()):
    """Keep hardware, practical comfort and solver-quality gates separate."""
    checks = (
        ("temperature_max_violation_c", criteria.temperature_max_c),
        ("temperature_violation_hours", criteria.temperature_hours),
        ("temperature_degree_hours", criteria.temperature_degree_hours),
        ("co2_max_violation_ppm", criteria.co2_max_ppm),
        ("co2_violation_hours", criteria.co2_hours),
        ("co2_ppm_hours", criteria.co2_ppm_hours),
    )
    comfort_ok = all(isfinite(metrics["operation_" + key])
                     and metrics["operation_" + key] <= bound + 1e-8
                     for key, bound in checks)
    hardware_ok = bool(metrics["equipment_audit_passed"] and metrics["replay_audit_passed"])
    rule = metrics["controller"] == "thermostat"
    model_ok = all(r["solver_incumbent_valid"] is True for r in solves) if solves else None
    quality_ok = rule or (bool(solves) and all(
        r["solver_incumbent_valid"] is True and not r["solve_fallback"]
        and r["solver_gap"] is not None and r["solver_gap"] <= criteria.solver_gap + 1e-8
        for r in solves))
    practical = hardware_ok and comfort_ok and metrics["recovery_reached_target"]
    return {
        "modeled_incumbents_valid": model_ok,
        "equipment_acceptable": hardware_ok,
        "operation_comfort_acceptable": comfort_ok,
        "practical_acceptable": practical,
        "solver_quality_applicable": not rule,
        "solver_quality_acceptable": quality_ok,
        # A screening gate, not proof of equal service or causal superiority.
        "economic_screen_pass": (practical and quality_ok
                                 and metrics["fallback_calls"] == 0
                                 and metrics["actuator_overrides"] == 0),
    }


def endpoint_areas(trace, dt):
    """Endpoint quantities for comparison with the MILP soft objective only.

    Continuous physical comfort scores still come from evaluation.evaluate.
    """
    operation = [r for r in trace if r["phase"] == "operation"]
    thermal = dt * sum(max(0.0, r["temperature_min_c"] - r["next_temperature_c"])
                       + max(0.0, r["next_temperature_c"] - r["temperature_max_c"])
                       for r in operation)
    carbon = dt * sum(max(0.0, r["next_co2_ppm"] - r["co2_max_ppm"]) for r in operation)
    return thermal, carbon


def freeze_settings(rows, repeats=1, penalty_budget=30.0,
                    mpc_budget=2.0, feedback_budget=2.0):
    """Select only from nominal diagnostics; never inspect held-out outcomes."""
    if any(r["stage"] not in ("baseline", "budget", "penalty")
           or r["case"] != "nominal" or r["period"] not in ("winter", "summer")
           for r in rows):
        raise ValueError("selection accepts nominal winter/summer diagnostics only")
    groups = {}
    for row in rows:
        if row["controller"] == "open_loop":
            key = (row["budget_s"], row["temperature_penalty"], row["co2_penalty"])
            groups.setdefault(key, []).append(row)
    eligible = [key for key, group in groups.items()
                if len(group) == 2 * repeats
                and {r["period"] for r in group} == {"winter", "summer"}
                and all(r["economic_screen_pass"] for r in group)]
    # Keep original weights when qualified, then prefer lower computation.
    eligible.sort(key=lambda key: (
        (key[1], key[2]) != (100.0, 100.0), key[0],
        abs(key[1] - 100) + abs(key[2] - 100), key[1], key[2]))
    chosen = eligible[0] if eligible else (penalty_budget, 100.0, 100.0)
    payload = {
        "protocol": PROTOCOL, "source_revision": os.environ.get("GITHUB_SHA", "not recorded"),
        "qualification": "nominal_open_loop_qualified" if eligible else "unqualified_diagnostic_anchor",
        "eligible_candidates": len(eligible), "nominal_runs_considered": len(rows), "repeats": repeats,
        "selection_rule": "both nominal periods and every repeat pass all gates; prefer original weights then lower budget",
        "open_loop_budget_s": chosen[0], "temperature_penalty": chosen[1], "co2_penalty": chosen[2],
        "mpc_budget_s": mpc_budget, "mpc_horizon_hours": 6.0,
        "feedback_budget_s": feedback_budget, "feedback_window_hours": 4.0,
        "acceptance": asdict(Acceptance()),
        "note": "MPC budget/horizon are predeclared, not qualified by the open-loop sweep. No eligible candidate means diagnostic continuation, not promotion.",
    }
    return {**payload, "freeze_id": digest(payload)}


def read_freeze(path):
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = {k: v for k, v in frozen.items() if k != "freeze_id"}
    if frozen.get("protocol") != PROTOCOL or frozen.get("freeze_id") != digest(payload):
        raise ValueError("frozen settings protocol/hash mismatch")
    for key in ("open_loop_budget_s", "mpc_budget_s", "feedback_budget_s",
                "temperature_penalty", "co2_penalty"):
        if not isfinite(frozen[key]) or frozen[key] <= 0:
            raise ValueError("invalid frozen numeric setting")
    if frozen["acceptance"] != asdict(Acceptance()) or frozen["mpc_horizon_hours"] != 6:
        raise ValueError("frozen protocol assumptions differ")
    return frozen


def budget_upper_bound(stage, budgets, penalty_budget, mpc_budget, feedback_budget, repeats):
    nominal = 2 * (sum(set(budgets) | {penalty_budget}) + 4 * penalty_budget)
    feedback = 4 * (1 + 16) * feedback_budget
    heldout = 3 * (max((*budgets, penalty_budget)) + 96 * mpc_budget)
    parts = {"smoke": 1.0, "nominal": nominal, "feedback": feedback,
             "heldout": heldout, "all": nominal + feedback + heldout}
    return parts[stage] * repeats


def report(rows, frozen):
    def number(value, digits=3):
        return "-" if value is None else f"{value:.{digits}f}"

    lines = ["# Sensitivity results", "",
             "Surrogate simulation. Acceptance thresholds and stage definitions are in docs/sensitivity.md.",
             "Cost includes common 16-hour recovery; comfort scores cover operation.",
             "Budget is per solve, not equal total computation. Read total solver seconds and all gates.",
             "Incumbent objectives and dual bounds are for the first solve; every solve is in solves.csv.",
             "Objective magnitudes across different penalty weights are not directly comparable.", "",
             "| Stage / scenario | Method | Budget s | T / CO2 weights | Objective | Dual bound | Gap | Cost EUR | T K h | CO2 ppm h | Practical | Quality | Solve total s |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|---:|"]
    for r in rows:
        lines.append(
            f"| {r['stage']} / {r['scenario']} | {r['controller']} | {r['budget_s']:g} | "
            f"{r['temperature_penalty']:g} / {r['co2_penalty']:g} | "
            f"{number(r['first_incumbent_objective'])} | {number(r['first_dual_bound'])} | "
            f"{number(r['first_gap'])} | {r['total_cost_eur']:.3f} | "
            f"{r['operation_temperature_degree_hours']:.4f} | {r['operation_co2_ppm_hours']:.2f} | "
            f"{r['practical_acceptable']} | {r['solver_quality_acceptable'] if r['solver_quality_applicable'] else 'n/a'} | "
            f"{r['solve_seconds_total']:.3f} |")
    near_bad = [r["run_id"] for r in rows if r["controller"] != "thermostat"
                and r["solver_quality_acceptable"] and not r["operation_comfort_acceptable"]]
    worse = [r["run_id"] for r in rows if r["objective_worse_than_witness"] is True]
    lines.extend(["", "## Interpretation gates", "",
                  f"Gap-qualified optimizer runs failing practical operation comfort: {len(near_bad)}.",
                  "For those rows, investigate soft-penalty tradeoffs, endpoint versus continuous scoring, "
                  "and the recorded feasible rule witness; timeout alone is not an explanation.",
                  f"Nominal incumbents worse than an independently replayed feasible rule-objective witness: {len(worse)}.",
                  "A better witness proves that incumbent is not the best known feasible objective. "
                  "It does not prove that strictly zero comfort violation is feasible.",
                  "If no acceptable witness exists, model feasibility under stronger comfort limits remains undetermined.",
                  "Matched four-hour feedback results are window diagnostics. They are not full-day MPC results.",
                  "Held-out practical comparisons retain 24-hour open loop versus six-hour MPC; "
                  "horizon, solve quality and daily effort remain confounded.",
                  f"Frozen-setting qualification: {frozen['qualification'] if frozen else 'not applicable'}.",
                  "No confidence interval or universal controller ranking follows from one repeat.", ""])
    return "\n".join(lines)


def run_study(output, stage="nominal", budgets=BUDGETS, penalty_budget=30.0,
              mpc_budget=2.0, feedback_budget=2.0, repeats=1, frozen=None, plots=True):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be empty; previous reports are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    (output / "traces").mkdir()
    if plots:
        (output / "figures").mkdir()
    started = perf_counter()
    results, all_solves = [], []
    manifest = {
        "protocol": PROTOCOL, "source_revision": os.environ.get("GITHUB_SHA", "not recorded"),
        "stage": stage, "budgets_s": list(budgets), "penalty_budget_s": penalty_budget,
        "penalty_pairs": list(PENALTIES), "repeats": repeats,
        "acceptance": asdict(Acceptance()), "nominal_seeds": [101, 303],
        "heldout_seeds": [5202, 5404], "nominal_model": asdict(Model()),
        "base_settings": asdict(Settings()), "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": {name: version(name) for name in ("numpy", "scipy", "matplotlib")},
        "data_kind": "surrogate; no measured data", "completed": False,
        "estimated_solver_budget_s": budget_upper_bound(
            stage, budgets, penalty_budget, mpc_budget, feedback_budget, repeats),
    }

    def save_manifest():
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False),
                                              encoding="utf-8")
    save_manifest()

    def execute(scenario, controller, settings, label, repeat, witness=None):
        run_id = f"{len(results):03d}_{label}_{scenario.name}_{controller}_r{repeat}"
        tick = perf_counter()
        metrics, trace = evaluate(scenario, controller, settings)
        elapsed = perf_counter() - tick
        calls = [row for row in trace if row["solve_called"]]
        thermal, carbon = endpoint_areas(trace, settings.dt)
        first = calls[0] if calls else {}
        witness_objective = None
        if witness is not None:
            witness_objective = (witness["operation_cost_eur"]
                                 + settings.temperature_penalty * witness["endpoint_temperature_kh"]
                                 + settings.co2_penalty * witness["endpoint_co2_ppmh"] / 1000)
        objective = first.get("solver_incumbent_objective")
        row = {
            "run_id": run_id, "stage": label, "repeat": repeat,
            **metrics,
            "start_hour": scenario.start_hour, "input_hash": digest(asdict(scenario)),
            "budget_s": settings.time_limit, "horizon_hours": (
                scenario.evaluation_steps * settings.dt if controller == "open_loop"
                else settings.horizon_steps * settings.dt),
            "temperature_penalty": settings.temperature_penalty,
            "co2_penalty": settings.co2_penalty, "evaluation_wall_seconds": elapsed,
            "requested_daily_solver_budget_s": settings.time_limit * len(calls),
            "endpoint_temperature_kh": thermal, "endpoint_co2_ppmh": carbon,
            "default_weight_endpoint_objective": metrics["operation_cost_eur"] + 100 * thermal + 0.1 * carbon,
            "first_status": first.get("solve_status"),
            "first_incumbent_objective": objective, "first_dual_bound": first.get("solver_dual_bound"),
            "first_gap": first.get("solver_gap"),
            "first_energy_objective": first.get("solver_energy_objective"),
            "first_temperature_penalty_objective": first.get("solver_temperature_penalty_objective"),
            "first_co2_penalty_objective": first.get("solver_co2_penalty_objective"),
            "witness_objective": witness_objective,
            "witness_practical_acceptable": witness["practical_acceptable"] if witness else None,
            "objective_worse_than_witness": (objective > witness_objective + 1e-4
                                           if objective is not None and witness is not None else None),
            "freeze_id": frozen["freeze_id"] if frozen and label in ("feedback", "heldout") else None,
            **classify(metrics, calls),
        }
        results.append(row)
        for call in calls:
            all_solves.append({
                "run_id": run_id, "stage": label, "scenario": scenario.name,
                "controller": controller, "budget_s": settings.time_limit,
                **{key: value for key, value in call.items()
                   if key in ("step", "elapsed_h") or key.startswith(("solve_", "solver_"))},
            })
        write_csv(output / "traces" / f"{run_id}.csv", trace)
        write_csv(output / "metrics.csv", results)
        write_csv(output / "solves.csv", all_solves)
        print("SENSITIVITY_METRIC " + json.dumps(row, allow_nan=False), flush=True)
        return row, trace

    if stage == "smoke":
        for repeat in range(repeats):
            scenario = generate(DEVELOPMENT, "nominal", hours=1, start_hour=8)
            for controller in ("thermostat", "open_loop", "mpc"):
                execute(scenario, controller, Settings(time_limit=0.2, horizon_steps=4), "smoke", repeat)
    if stage in ("nominal", "all"):
        for repeat in range(repeats):
            for period in (PERIODS[0], PERIODS[2]):
                scenario = generate(period, "nominal")
                witness, witness_trace = execute(scenario, "thermostat", Settings(), "baseline", repeat)
                # A constructive soft-MILP witness requires matching inputs/model and domain.
                assert scenario.plan == scenario.realized and scenario.plant == Model()
                assert all(-40 <= r["temperature_c"] <= 65 and 0 <= r["co2_ppm"] <= 30000
                           and -40 <= r["next_temperature_c"] <= 65
                           and 0 <= r["next_co2_ppm"] <= 30000 for r in witness_trace)
                assert witness["equipment_acceptable"]
                # Strict zero-violation comfort feasibility is NOT implied.
                for budget in sorted(set(budgets) | {penalty_budget}):
                    execute(scenario, "open_loop", Settings(time_limit=budget),
                            "budget", repeat, witness)
                for tp, cp in PENALTIES:
                    execute(scenario, "open_loop", Settings(
                        time_limit=penalty_budget, temperature_penalty=tp, co2_penalty=cp),
                        "penalty", repeat, witness)
        frozen = freeze_settings(results, repeats, penalty_budget, mpc_budget, feedback_budget)
    if frozen is not None:
        (output / "frozen-settings.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
        print("SENSITIVITY_FREEZE " + json.dumps(frozen, allow_nan=False), flush=True)
    if stage in ("feedback", "heldout", "all") and frozen is None:
        raise ValueError("feedback/heldout stages require settings frozen from nominal diagnostics")
    if stage in ("feedback", "all"):
        for repeat in range(repeats):
            for period, start, disturbance in (
                    (PERIODS[0], 8, "weather_severe"), (PERIODS[2], 4, "occupancy_severe")):
                for case in ("nominal", disturbance):
                    scenario = generate(period, case, hours=4, start_hour=start)
                    settings = Settings(time_limit=frozen["feedback_budget_s"], horizon_steps=16,
                                        temperature_penalty=frozen["temperature_penalty"],
                                        co2_penalty=frozen["co2_penalty"])
                    traces = {}
                    for controller in ("thermostat", "open_loop", "mpc"):
                        _, traces[controller] = execute(scenario, controller, settings, "feedback", repeat)
                    if plots:
                        plot_trajectories(f"feedback_{scenario.name}_r{repeat}", traces, output / "figures")
    if stage in ("heldout", "all"):
        # Selection is already frozen on disk and in the log before these inputs are generated.
        for repeat in range(repeats):
            for period, case in HELDOUT:
                scenario, traces = generate(period, case), {}
                for controller in ("thermostat", "open_loop", "mpc"):
                    budget = frozen["open_loop_budget_s"] if controller == "open_loop" else frozen["mpc_budget_s"]
                    settings = Settings(time_limit=budget, horizon_steps=24,
                                        temperature_penalty=frozen["temperature_penalty"],
                                        co2_penalty=frozen["co2_penalty"])
                    _, traces[controller] = execute(scenario, controller, settings, "heldout", repeat)
                if plots:
                    plot_trajectories(f"heldout_{scenario.name}_r{repeat}", traces, output / "figures")
    text = report(results, frozen)
    (output / "report.md").write_text(text, encoding="utf-8")
    manifest.update(completed=True, completed_runs=len(results),
                    actual_wall_seconds=perf_counter() - started, frozen_settings=frozen,
                    total_solver_seconds=sum(r["solve_seconds_total"] for r in results))
    save_manifest()
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(text)
    print("SENSITIVITY_COMPLETE " + json.dumps(manifest, allow_nan=False), flush=True)
    return results, frozen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("smoke", "nominal", "feedback", "heldout", "all"), default="nominal")
    parser.add_argument("--output", type=Path, default=Path("reports/sensitivity"))
    parser.add_argument("--budgets", type=float, nargs="+", default=list(BUDGETS))
    parser.add_argument("--penalty-budget", type=float, default=30.0)
    parser.add_argument("--mpc-budget", type=float, default=2.0)
    parser.add_argument("--feedback-budget", type=float, default=2.0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--freeze", type=Path, help="prior frozen-settings.json for a standalone later stage")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--allow-large", action="store_true", help="allow requested solver budgets above 30 minutes")
    args = parser.parse_args(argv)
    numeric = [*args.budgets, args.penalty_budget, args.mpc_budget, args.feedback_budget]
    if not all(isfinite(x) and x > 0 for x in numeric) or args.repeats < 1:
        parser.error("budgets must be finite and positive; repeats must be positive")
    if not __debug__:
        parser.error("run without -O so physical assertions remain enabled")
    if (args.stage in ("feedback", "heldout")) != (args.freeze is not None):
        parser.error("--freeze is required only for standalone feedback/heldout stages")
    frozen = read_freeze(args.freeze) if args.freeze else None
    if frozen:
        args.mpc_budget, args.feedback_budget = frozen["mpc_budget_s"], frozen["feedback_budget_s"]
        args.penalty_budget = frozen["open_loop_budget_s"]
    upper = budget_upper_bound(args.stage, args.budgets, args.penalty_budget,
                               args.mpc_budget, args.feedback_budget, args.repeats)
    if upper > 1800 and not args.allow_large:
        parser.error(f"requested solver budgets sum to {upper:.0f}s; use --allow-large explicitly")
    print(f"Requested solver-budget upper bound: {upper:.1f}s, plus build/replay/report overhead.", flush=True)
    run_study(args.output, args.stage, tuple(args.budgets), args.penalty_budget,
              args.mpc_budget, args.feedback_budget, args.repeats, frozen, not args.no_plots)


if __name__ == "__main__":
    main()
