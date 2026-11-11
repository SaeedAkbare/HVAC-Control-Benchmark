# HVAC Control Benchmark

A small, reproducible simulation comparing a software thermostat, a frozen day-ahead schedule, and model predictive control (MPC) for one building zone.

The question is practical: **when do updated measurements and forecasts justify the extra optimization work?** Cost is reported beside temperature and CO2 violations, computation time, actuator limits, and fallback use. The benchmark does not assume that MPC always wins.

[![CI](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/workflows/ci.yml)

## Run it

Python 3.11 is the reference environment.

```bash
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m pytest -q
hvac-benchmark --suite smoke --output results
```

The smoke suite runs 12 controller experiments: winter and summer, nominal and early/high occupancy, four operating hours plus 16 hours of common recovery. It is an integration check, not an all-day performance study.

```bash
hvac-benchmark --suite full --output results-full
hvac-benchmark --suite full --period winter --case weather_severe --output winter-check
```

The full suite has four seasonal days, seven scenario cases, and three controllers: **84 controller runs**. MILP execution can take tens of minutes. The default horizon is six hours and the solver budget is two seconds per call. For example, `--time-limit 0.5 --horizon-hours 6` reproduces the original full-reference CI configuration. Short solver budgets can change the feasible schedules and fallback rate; they are recorded with the results.

## What is compared?

| Controller | Information and behavior |
|---|---|
| Thermostat | Current temperature, CO2, outdoor temperature, and occupancy. Deadband temperature control with occupancy ventilation and CO2 purge. No prices or future schedule optimization. |
| Day-ahead open loop | Optimizes the complete operating day once using the initial forecast, then executes that schedule. Subsequent observations do not replan it. |
| MPC | Reoptimizes every 15 minutes from observed temperature and CO2, using a causal forecast update and a six-hour horizon; executes only the first action. |

All methods see the same realized plant, weather, occupancy, tariff, comfort requirements, and actuator protection. Heating uses gas; cooling and fans use electricity. The optimizer uses a finite menu of airflow modes and continuous heating/cooling through SciPy MILP/HiGHS.

## Experiments and outputs

The nominal case matches the plant and controller model. Other cases introduce mild or severe persistent weather forecast error, earlier/more occupants, or an increased plant heat-loss coefficient. Each seasonal scenario uses a fixed seed. Inputs are **physically plausible surrogates**, not measured weather, market prices, or field data.

Each output directory contains:

- `metrics.csv`: cost, separate electricity/gas use, peak meter power, violation area/duration/peak, solver times and gaps, fallback counts, and terminal recovery checks.
- `traces/`: every requested/applied action, disturbance, state, meter value, solver status, and plant-side override.
- `figures/`: simulated trajectories and paired cost/comfort comparisons.
- `metadata.json`: source revision in CI, package versions, assumptions, seeds, and solver settings.
- `report.md`: readable results, produced from the actual run.

Cost includes a common 16-hour recovery under the same rule controller. Final-state differences are still reported; a failed recovery target prevents a simple equivalent-service savings claim.

GitHub Actions runs regression tests, both smoke entry points, and the bounded sensitivity study on main source changes. The original full reference suite remains available through manual workflow dispatch. Download `smoke-results`, `sensitivity-results`, or `full-results` from the corresponding successful [Actions run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions).

## Verified reference run

The [reference run](reports/reference-2026-11-10/README.md) completed **29 tests, 12 smoke runs, and 84 full controller runs** on GitHub Actions. All full runs passed independent replay and actuator audits and reached the common recovery target.

The 0.5-second full-CI solver budget was too short to certify any day-ahead plan within the requested optimality tolerance. Several returned plans had large comfort violations. The archived results show those limitations explicitly; controller economic rankings require a stronger solver-budget study.

## Sensitivity study

[The predeclared sensitivity protocol](docs/sensitivity.md) separates solver-budget effects, penalty-weight effects, matched-window feedback diagnostics, and a small evaluation on new seeds. It reuses the existing controllers and evaluator.

```bash
hvac-benchmark sensitivity --output reports/sensitivity-nominal
hvac-benchmark sensitivity --stage all --output reports/sensitivity-initial
```

The default nominal stage runs winter and summer at 0.5, 2, 10 and 30 seconds per day-ahead solve, then changes one penalty weight at a time at a fixed budget. Later stages use a hashed settings file frozen before held-out evaluation. Acceptance checks distinguish equipment feasibility, practical comfort and solver quality; equal per-call time is not equal total computation.

The [executed sensitivity report](reports/sensitivity-2026-11-11/README.md) records **39 passing tests, 12 benchmark smoke runs, three sensitivity smoke runs, and 39 study runs**. All study runs passed physical audits and recovered. Longer nominal budgets improved incumbent objectives, but no tuning candidate passed both practical and solver-quality gates. A matched four-hour occupancy case demonstrated a useful feedback response; the held-out full-day results do not establish a general economic ranking.

## Read the method

- [Model, control formulation, fairness, and limitations](docs/method.md)
- [Surrogate data, scenarios, and reproducibility](docs/data.md)
- [Library/source attribution and AI assistance](ACKNOWLEDGMENTS.md)
- [Validation record](docs/validation.md)

The code is organized as [physics](src/hvac_benchmark/physics.py), [controllers](src/hvac_benchmark/controllers.py), [scenarios](src/hvac_benchmark/scenarios.py), and [evaluation](src/hvac_benchmark/evaluation.py), with a small CLI and reporting module.

This is an AI-assisted educational portfolio project. It has no field-validation or deployment claim. Humidity, solar gains, equipment dynamics, measurement noise, parameter estimation, and multi-zone operation are outside the current model.
