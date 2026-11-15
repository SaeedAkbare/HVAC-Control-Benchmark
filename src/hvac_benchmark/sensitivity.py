"""Bounded cost-only hard-constraint feasibility and solver-budget study."""
import argparse
import base64
from dataclasses import asdict
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
from .reporting import plot_solver_budget, plot_trajectories, write_csv
from .scenarios import DEVELOPMENT, PERIODS, generate

PROTOCOL = "hard-constraints-v2"
BUDGETS = (0.5, 2.0, 10.0)
CASES = ((0, "nominal"), (0, "weather_severe"), (0, "loss_severe"),
         (2, "nominal"), (2, "occupancy_severe"), (2, "loss_severe"))


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def classify(metrics, solves):
    """Hard service, valid prediction and solve quality are separate."""
    rule = metrics["controller"] == "thermostat"
    quality = None if rule else bool(solves) and all(
        r["solver_incumbent_valid"] is True
        and r["solver_prediction_hard_feasible"] is True
        and not r["solve_fallback"] and r["solver_gap"] is not None
        and r["solver_gap"] <= 0.01 + 1e-8 for r in solves)
    return {"solver_quality_acceptable": quality,
            "quality_screen_pass": (metrics["comparison_eligible"]
                                    and (rule or quality is True))}


def budget_upper_bound(stage, budgets, mpc_budget, feedback_budget, repeats):
    nominal = 2 * (sum(set(budgets)) + 96 * mpc_budget)
    comparison = 6 * (max(budgets) + 96 * mpc_budget)
    extra = 2 * (sum(set(budgets)) - max(budgets))
    feedback = 4 * 17 * feedback_budget
    return {"smoke": 1, "nominal": nominal,
            "all": comparison + extra + feedback}[stage] * repeats


def report(rows):
    lines = ["# Hard-constraint simulation results", "",
             "Objective: energy cost only. No comfort slacks or penalties.",
             "Costs include common 16-hour recovery; comfort is continuous operating-period excess.",
             "Feasible predictions are not guarantees under realized disturbances.",
             "Fallback operation is not a valid optimization; read the cause and affected steps.",
             "Different horizons, solve quality and total computation limit causal comparisons.", "",
             "| Scenario / stage | Method | Cost EUR | T K h | CO2 ppm h | Valid service | Eligible | Quality | Fallback steps | Solve s |",
             "|---|---|---:|---:|---:|---|---|---|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['scenario']} / {r['stage']} | {r['controller']} | "
                     f"{r['total_cost_eur']:.4f} | {r['operation_temperature_degree_hours']:.5f} | "
                     f"{r['operation_co2_ppm_hours']:.3f} | {r['valid_service']} | "
                     f"{r['comparison_eligible']} | {r['solver_quality_acceptable']} | "
                     f"{r['fallback_operation_steps']} | {r['solve_seconds_total']:.3f} |")
    lines.extend(["", "Valid service requires zero operating comfort excursions (unchanged numerical",
                  "reporting tolerance) and the common terminal target. Eligible adds no fallback,",
                  "no actuator override and valid hard-feasible optimization predictions where applicable.",
                  "Quality requires every optimizer call to report gap <=1%; n/a for the rule.",
                  "Only compare costs for paired eligible runs with the same service/terminal protocol.",
                  "A single synthetic repeat does not establish field savings or a universal ranking.", ""])
    return "\n".join(lines)


def run_study(output, stage="nominal", budgets=BUDGETS, mpc_budget=2.0,
              feedback_budget=2.0, repeats=1, plots=True):
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output must be an empty directory; previous evidence is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    (output / "traces").mkdir()
    if plots:
        (output / "figures").mkdir()
    started = perf_counter()
    protocol = {
        "protocol": PROTOCOL, "source_revision": os.environ.get("GITHUB_SHA", "not recorded"),
        "objective": "operating energy cost only", "comfort": "hard at both interval endpoints",
        "stage": stage, "budgets_s": list(budgets), "open_loop_budget_s": max(budgets),
        "mpc_budget_s": mpc_budget, "mpc_horizon_hours": 6.0,
        "feedback_budget_s": feedback_budget, "feedback_window_hours": 4.0,
        "repeats": repeats, "model": asdict(Model()), "base_settings": asdict(Settings()),
        "cases": [{"period": PERIODS[i].name, "seed": PERIODS[i].seed, "case": case}
                  for i, case in CASES],
        "feedback": [{"period": "winter", "seed": 101, "start": 8, "case": "weather_severe"},
                     {"period": "summer", "seed": 303, "start": 4, "case": "occupancy_severe"}],
        "note": "Fixed before inputs are generated. No outcome-based selection or relaxation.",
    }
    protocol["protocol_id"] = digest(protocol)
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    print("HARD_PROTOCOL " + json.dumps(protocol, allow_nan=False), flush=True)
    manifest = {"protocol": protocol, "python": platform.python_version(),
                "platform": platform.platform(),
                "versions": {name: version(name) for name in ("numpy", "scipy", "matplotlib")},
                "data_kind": "synthetic surrogates; not measured data", "completed": False,
                "estimated_solver_budget_s": budget_upper_bound(
                    stage, budgets, mpc_budget, feedback_budget, repeats)}
    rows, all_solves = [], []

    def save_manifest():
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False),
                                              encoding="utf-8")
    save_manifest()

    def execute(scenario, controller, settings, label, repeat):
        run_id = f"{len(rows):03d}_{label}_{scenario.name}_{controller}_r{repeat}"
        tick = perf_counter()
        metrics, trace = evaluate(scenario, controller, settings)
        elapsed = perf_counter() - tick
        calls = [r for r in trace if r["solve_called"]]
        first = calls[0] if calls else {}
        row = {"run_id": run_id, "stage": label, "repeat": repeat, **metrics,
               "start_hour": scenario.start_hour, "input_hash": digest(asdict(scenario)),
               "protocol_id": protocol["protocol_id"],
               "budget_s": settings.time_limit if controller != "thermostat" else None,
               "horizon_hours": (scenario.evaluation_steps * settings.dt if controller == "open_loop"
                                 else settings.horizon_steps * settings.dt if controller == "mpc" else None),
               "evaluation_wall_seconds": elapsed,
               "requested_solver_budget_s": settings.time_limit * len(calls),
               "first_status": first.get("solve_status"),
               "first_incumbent_objective": first.get("solver_incumbent_objective"),
               "first_dual_bound": first.get("solver_dual_bound"),
               "first_gap": first.get("solver_gap"), **classify(metrics, calls)}
        rows.append(row)
        for call in calls:
            record = {"run_id": run_id, "stage": label, "scenario": scenario.name,
                      "controller": controller, "budget_s": settings.time_limit,
                      **{k: v for k, v in call.items()
                         if k in ("step", "elapsed_h") or k.startswith(("solve_", "solver_"))}}
            all_solves.append(record)
            print("HARD_SOLVE " + json.dumps(record, allow_nan=False), flush=True)
        write_csv(output / "traces" / f"{run_id}.csv", trace)
        write_csv(output / "metrics.csv", rows)
        write_csv(output / "solves.csv", all_solves)
        print("HARD_METRIC " + json.dumps(row, allow_nan=False), flush=True)
        return trace

    for repeat in range(repeats):
        cases = CASES if stage == "all" else ((0, "nominal"), (2, "nominal"))
        if stage == "smoke":
            scenario = generate(DEVELOPMENT, "nominal", hours=1, start_hour=8)
            for name in ("thermostat", "open_loop", "mpc"):
                execute(scenario, name, Settings(time_limit=0.2, horizon_steps=4), "smoke", repeat)
            continue
        for i, case in cases:
            scenario, traces = generate(PERIODS[i], case), {}
            for name in ("thermostat", "open_loop", "mpc"):
                budget = max(budgets) if name == "open_loop" else mpc_budget
                label = "budget" if case == "nominal" and name == "open_loop" else "comparison"
                traces[name] = execute(scenario, name, Settings(time_limit=budget), label, repeat)
            if plots:
                plot_trajectories(f"full_{scenario.name}_r{repeat}", traces, output / "figures")
            if case == "nominal":
                for budget in sorted(set(budgets) - {max(budgets)}):
                    execute(scenario, "open_loop", Settings(time_limit=budget), "budget", repeat)
        if stage == "all":
            for i, start, disturbance in ((0, 8, "weather_severe"), (2, 4, "occupancy_severe")):
                for case in ("nominal", disturbance):
                    scenario = generate(PERIODS[i], case, hours=4, start_hour=start)
                    traces = {}
                    for name in ("thermostat", "open_loop", "mpc"):
                        traces[name] = execute(scenario, name, Settings(
                            time_limit=feedback_budget, horizon_steps=16), "feedback", repeat)
                    if plots:
                        plot_trajectories(f"feedback_{scenario.name}_r{repeat}", traces, output / "figures")
    if plots and stage != "smoke":
        plot_solver_budget(rows, output / "figures")
        # Preserve selected executed figures through the text-only GitHub API.
        for name in ("full_winter__nominal_r0.svg", "full_summer__occupancy_severe_r0.svg",
                     "solver_budget.svg"):
            path = output / "figures" / name
            if path.exists():
                print("HARD_FIGURE " + json.dumps({"name": name, "svg": path.read_text(encoding="utf-8"),
                                                     "png_base64": base64.b64encode(path.with_suffix(".png").read_bytes()).decode("ascii")}),
                      flush=True)
    result_report = report(rows)
    (output / "report.md").write_text(result_report, encoding="utf-8")
    manifest.update(completed=True, completed_runs=len(rows), solve_calls=len(all_solves),
                    actual_wall_seconds=perf_counter() - started,
                    total_solver_seconds=sum(r["solve_seconds_total"] for r in rows))
    save_manifest()
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(result_report)
    print("HARD_COMPLETE " + json.dumps(manifest, allow_nan=False), flush=True)
    return rows, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("smoke", "nominal", "all"), default="nominal")
    parser.add_argument("--output", type=Path, default=Path("reports/hard-constraints"))
    parser.add_argument("--budgets", type=float, nargs="+", default=list(BUDGETS))
    parser.add_argument("--mpc-budget", type=float, default=2.0)
    parser.add_argument("--feedback-budget", type=float, default=2.0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--allow-large", action="store_true", help="explicitly allow >30 minutes requested solver time")
    args = parser.parse_args(argv)
    if not all(isfinite(v) and v > 0 for v in (*args.budgets, args.mpc_budget, args.feedback_budget)) or args.repeats < 1:
        parser.error("budgets must be finite and positive; repeats must be positive")
    if not __debug__:
        parser.error("run without -O so physical assertions remain enabled")
    upper = budget_upper_bound(args.stage, args.budgets, args.mpc_budget, args.feedback_budget, args.repeats)
    if upper > 1800 and not args.allow_large:
        parser.error(f"requested solver budgets sum to {upper:.0f}s; use --allow-large explicitly")
    print(f"Requested solver-budget upper bound: {upper:.1f}s plus construction/replay/report overhead.", flush=True)
    run_study(args.output, args.stage, tuple(args.budgets), args.mpc_budget,
              args.feedback_budget, args.repeats, not args.no_plots)


if __name__ == "__main__":
    main()
