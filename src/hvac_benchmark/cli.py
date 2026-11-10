"""Reproducible experiment entry point."""
import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
from . import __version__
from .config import Model, MODES, Settings
from .controllers import CONTROLLERS
from .evaluation import evaluate
from .reporting import markdown_report, plot_comparison, plot_trajectories, write_csv
from .scenarios import suite


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--time-limit", type=float, default=2.0, help="MILP seconds per call")
    parser.add_argument("--horizon-hours", type=float, default=6.0)
    parser.add_argument("--period", help="optional exact seasonal name")
    parser.add_argument("--case", help="optional exact scenario case")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    if args.time_limit <= 0:
        parser.error("--time-limit must be positive")
    steps = round(args.horizon_hours / 0.25)
    if not 1 <= steps <= 96 or abs(steps * 0.25 - args.horizon_hours) > 1e-8:
        parser.error("--horizon-hours must be a multiple of 0.25 in [0.25, 24]")
    settings = Settings(horizon_steps=steps, time_limit=args.time_limit)
    scenarios = [s for s in suite(args.suite)
                 if (args.period is None or s.period == args.period)
                 and (args.case is None or s.case == args.case)]
    if not scenarios:
        parser.error("filters selected no scenarios")
    args.output.mkdir(parents=True, exist_ok=True)
    traces = args.output / "traces"
    figures = args.output / "figures"
    traces.mkdir(exist_ok=True)
    if not args.no_plots:
        figures.mkdir(exist_ok=True)
    metrics = []
    for scenario in scenarios:
        records = {}
        for name in CONTROLLERS:
            result, rows = evaluate(scenario, name, settings)
            metrics.append(result)
            records[name] = rows
            write_csv(traces / f"{scenario.name}__{name}.csv", rows)
            print(json.dumps(result, allow_nan=False), flush=True)
        if not args.no_plots:
            plot_trajectories(scenario.name, records, figures)
    write_csv(args.output / "metrics.csv", metrics)
    metadata = {
        "package_version": __version__, "git_commit": os.environ.get("GITHUB_SHA", "not recorded"),
        "suite": args.suite, "python": sys.version, "platform": platform.platform(),
        "versions": {name: version(name) for name in ("numpy", "scipy", "matplotlib")},
        "settings": asdict(settings), "nominal_model": asdict(Model()),
        "modes": [asdict(mode) for mode in MODES],
        "scenarios": [
            {"name": s.name, "seed": s.seed, "period": s.period, "case": s.case,
             "start_hour": s.start_hour, "evaluation_steps": s.evaluation_steps,
             "plant": asdict(s.plant)} for s in scenarios],
        "data_kind": "physically plausible surrogate; not measured data",
        "timing_note": "time limits and platform can change MILP incumbents; record both",
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False),
                                              encoding="utf-8")
    report = markdown_report(metrics, args.suite)
    (args.output / "report.md").write_text(report, encoding="utf-8")
    if not args.no_plots:
        plot_comparison(metrics, figures)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(report)
    print(f"Completed {len(metrics)} controller runs. Results: {args.output}", flush=True)


if __name__ == "__main__":
    main()
