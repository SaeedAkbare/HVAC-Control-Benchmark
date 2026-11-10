"""CSV/Markdown and plots drawn only from executed simulation records."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"thermostat": "#555555", "open_loop": "#d08020", "mpc": "#147d92"}


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(metrics, suite_name):
    lines = [
        "# Simulation results", "",
        f"Suite: **{suite_name}**. All values are simulated, using surrogate inputs.",
        "Cost and meter energy include the common sixteen-hour recovery. Comfort columns",
        "cover the operation period. Read each cost alongside both comfort measures,",
        "solver fallbacks, and terminal recovery success. No field savings are implied.", "",
        "| Scenario | Controller | Cost (EUR) | Electricity (kWh) | Gas (kWh) | Temperature (K h) | CO2 (ppm h) | Fallbacks | Recovery reached |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for m in metrics:
        lines.append(
            f"| {m['scenario']} | {m['controller']} | {m['total_cost_eur']:.3f} | "
            f"{m['total_electricity_kwh']:.3f} | {m['total_gas_kwh']:.3f} | "
            f"{m['operation_temperature_degree_hours']:.4f} | "
            f"{m['operation_co2_ppm_hours']:.2f} | {m['fallback_calls']} | "
            f"{m['recovery_reached_target']} |"
        )
    lines.extend(["", "Detailed violation durations, peaks, solve timing, incumbent gaps,",
                  "actuator overrides and independent replay errors are in metrics.csv.",
                  "A failed recovery target leaves a terminal-state imbalance; do not",
                  "interpret its raw cost difference as an equivalent-service saving.", ""])
    return "\n".join(lines)


def plot_trajectories(scenario_name, records, output):
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, constrained_layout=True)
    for name, rows in records.items():
        x = [r["elapsed_h"] for r in rows] + [rows[-1]["elapsed_h"] + 0.25]
        temp = [r["temperature_c"] for r in rows] + [rows[-1]["next_temperature_c"]]
        co2 = [r["co2_ppm"] for r in rows] + [rows[-1]["next_co2_ppm"]]
        axes[0].plot(x, temp, color=COLORS[name], label=name)
        axes[1].plot(x, co2, color=COLORS[name])
        axes[2].step(x[:-1], [r["electricity_kwh"] / 0.25 for r in rows],
                     where="post", color=COLORS[name])
    rows = next(iter(records.values()))
    x = [r["elapsed_h"] for r in rows]
    axes[0].step(x, [r["temperature_min_c"] for r in rows], where="post",
                 color="black", linestyle=":", linewidth=1)
    axes[0].step(x, [r["temperature_max_c"] for r in rows], where="post",
                 color="black", linestyle=":", linewidth=1)
    axes[1].step(x, [r["co2_max_ppm"] for r in rows], where="post",
                 color="black", linestyle=":", linewidth=1)
    recovery = next(r["elapsed_h"] for r in rows if r["phase"] == "recovery")
    for ax in axes:
        ax.axvspan(recovery, rows[-1]["elapsed_h"] + 0.25, color="#dddddd", alpha=0.4)
        ax.grid(alpha=0.2)
    axes[0].set(title=scenario_name + " | shaded: common recovery", ylabel="Zone temperature (C)")
    axes[1].set(ylabel="Zone CO2 (ppm)")
    axes[2].set(ylabel="Electric power (kW)", xlabel="Elapsed time (hours)")
    axes[0].legend(ncol=3)
    fig.savefig(Path(output) / f"{scenario_name}.png", dpi=150)
    plt.close(fig)


def plot_comparison(metrics, output):
    baseline = {m["scenario"]: m for m in metrics if m["controller"] == "thermostat"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)
    measures = (("operation_temperature_degree_hours", "Change in temperature violation (K h)"),
                ("operation_co2_ppm_hours", "Change in CO2 violation (ppm h)"))
    for name in ("open_loop", "mpc"):
        selected = [m for m in metrics if m["controller"] == name]
        changes = [100 * (m["total_cost_eur"] / baseline[m["scenario"]]["total_cost_eur"] - 1)
                   for m in selected]
        for ax, (measure, label) in zip(axes, measures):
            ax.scatter(changes, [m[measure] - baseline[m["scenario"]][measure] for m in selected],
                       color=COLORS[name], label=name, alpha=0.7, s=35)
            ax.set(xlabel="Cost change vs thermostat (%)", ylabel=label)
    for ax in axes:
        ax.axhline(0, color="black", linewidth=0.7)
        ax.axvline(0, color="black", linewidth=0.7)
        ax.grid(alpha=0.2)
        ax.legend()
    fig.suptitle("Paired scenarios: cost includes recovery; comfort covers operation")
    fig.savefig(Path(output) / "paired_comparison.png", dpi=150)
    plt.close(fig)
