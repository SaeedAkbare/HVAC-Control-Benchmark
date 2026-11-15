# Corrected hard-constraint study protocol

Protocol `hard-constraints-v2` was declared before the corrected study was executed. The previous penalty-sweep protocol and results are preserved in Git history and the superseded archives. They do not describe the current optimization.

## Problem and interpretation

Minimize energy cost subject to hard temperature, CO2 and equipment constraints. No comfort penalties, normalized weights, Pareto analysis or automatic relaxation are used. The existing plant, six modes, comfort values, forecasts, initial state, time step and common 16-hour terminal continuation remain unchanged.

Hard comfort applies at both ends of each constant-input interval; monotonicity covers the interior. The original numerical reporting tolerance is unchanged: 1e-5 C and 0.01 ppm. Any larger operating excursion fails the service test. Recovery is a separately reported common continuation, with the original final tolerances (22 ±0.05 C; CO2 ≤601 ppm).

Prediction feasibility, realized service, solver quality and fallback use are distinct. A failed solve never acquires a feasibility claim because its emergency rule rollout runs. An already-invalid initial state and first-interval capacity limits are explicitly diagnosed. Solver-proven infeasibility is distinguished from a timeout without an incumbent or a numerical failure.

## Fixed experiments

| Stage | Cases | Controllers / budgets |
|---|---|---|
| Nominal budget | Winter 101 and summer 303, 24 hours | Open loop at 0.5, 2 and 10 seconds; thermostat and six-hour MPC at 2 seconds per MPC call |
| Full-day disturbances | Winter severe weather and UA mismatch; summer severe occupancy and UA mismatch | Thermostat, open loop (10 seconds once), MPC (2 seconds per call, six hours) |
| Matched window | Winter 08–12 nominal/severe weather; summer 04–08 nominal/severe occupancy | All three; open loop once and MPC 16 times, both 2 seconds per call, common fixed four-hour end time |

The 10-second nominal results also serve the full-day comparison; they are not rerun to fill a second table. Default nominal execution is 10 runs. The complete bounded suite has **34 runs**: 18 full-day controller comparisons, four additional nominal budget runs and 12 matched-window runs.

Settings and input definitions are fixed in `protocol.json` before inputs are generated. Every metric carries its protocol identifier and scenario input hash. No configuration is selected based on the new outcomes, and no case is altered to make constraints pass. One repeat is descriptive, not a statistical estimate.

The full-day comparison retains different horizons and total computation. Matched windows remove the initial horizon mismatch but still have one open-loop call versus 16 MPC calls. Neither comparison establishes equal-computation superiority. Failures remain in tables and traces; costs are compared as equivalent service only when both paired runs qualify.

## Resource bounds and commands

```bash
# Default: ten nominal runs, requested solver sum at most 409 seconds.
hvac-benchmark sensitivity --output results/corrected-nominal

# Explicit bounded suite: 34 runs, requested solver sum at most 1353 seconds.
hvac-benchmark sensitivity --stage all --output results/corrected-all
```

The sums exclude construction, replay and plotting overhead. CI allows 30 minutes for the corrected study. Larger budget/repeat settings require `--allow-large` if the requested sum exceeds 1800 seconds. No automatic budget expansion occurs. Output directories must be empty.

Normal CI runs tests, package checks and both smoke entry points. The 34-run corrected study requires manual workflow dispatch (`study: corrected`); the separate 84-run seasonal matrix uses `study: full`. Old soft-constraint experiments are reproduced only from their historical source revisions, not by the current workflow.

## Evidence

- `metrics.csv`: continuous violation area/duration/peak, separate meters, recovery, valid service, predicted feasibility, status counts, fallback steps, overrides, solve times and gaps.
- `solves.csv`: each call's raw status/message, incumbent validation, objective, lower bound, gap, node count, start-state validity and first-interval reachability.
- `traces/`: every predicted/applied action, state, disturbance, fallback and override.
- `protocol.json` and `manifest.json`: exact source, fixed settings, seeds, versions, completion and elapsed time.
- `figures/`: actual executed trajectories and the nominal objective/bound sweep, as PNG and SVG.
- `report.md`: all completed runs with validity gates; it does not hide failed service behind an energy score.

The current model is a physically plausible synthetic benchmark with no measured-data or deployment claim. Earlier reports under `reference-2026-11-10` and `sensitivity-2026-11-11` are superseded soft-constraint evidence.

## Executed initial correction

The [15 November corrected archive](../reports/corrected-2026-11-15/README.md) records all 34 runs and 654 optimization attempts (642 HiGHS calls and 12 initial-state prechecks). The fixed protocol was preserved. Both ten-second nominal plans were hard-feasible, but short-budget timeouts, disturbed-service failures and large remaining gaps were retained. The optional 84-run matrix was not executed. No penalty study is active.
