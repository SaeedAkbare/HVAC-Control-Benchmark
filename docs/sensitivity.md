# Sensitivity study protocol

This protocol is declared before its first sensitivity execution. The study diagnoses the initial short-budget results; it does not assume that timeouts alone caused poor control or that MPC should win.

One new module, [sensitivity.py](../src/hvac_benchmark/sensitivity.py), orchestrates the existing controllers, plant, evaluator, metrics and reporting. The controller formulation and the original reference CSV remain unchanged. Solver instrumentation adds diagnostics without changing the objective or constraints.

## Three separate questions

1. **Modeled/physical feasibility:** Was a solver incumbent valid against its MILP rows, variable bounds and integrality checks? Did the applied controls pass the existing independent plant replay and equipment audit?
2. **Practical acceptability:** Did the simulated operating period satisfy the engineering screening limits below and return to the common terminal target?
3. **Economic comparison:** Are practical service and solver quality sufficient to examine the bill? Passing this screen is not a proof of equal service or causal superiority.

An accepted MILP incumbent can violate comfort because its comfort constraints are soft. A protected applied trajectory can pass equipment checks even if the requested action was altered. The study records modeled validity, physical audit results, overrides, fallbacks, comfort and recovery separately.

## Predeclared acceptance rules

These are engineering screening assumptions for this simulation, not regulations, health limits, or a claim of field adequacy. Excursions are relative to the existing occupied/unoccupied comfort bands and CO2 ceilings.

| Operation metric | Maximum accepted value |
|---|---:|
| Temperature excursion magnitude | 0.5 C |
| Total temperature violation duration | 0.5 h |
| Temperature violation area | 0.1 K h |
| CO2 excursion magnitude | 100 ppm |
| Total CO2 violation duration | 0.25 h |
| CO2 violation area | 25 ppm h |

All six must pass; a small area cannot hide a large peak or a long duration. These absolute limits are used for both the full-day and shorter diagnostic windows; results from different window lengths are not pooled.

Equipment checks retain the existing finite flow modes, 18/16 kW heating/cooling capacities, no simultaneous heating and cooling, no coil output with the fan off, and 12–40 C supply limits at both interval endpoints. Independent ODE replay must meet the existing 1e-6 C / 1e-4 ppm tolerances. The runner uses ordinary Python, with physical assertions enabled.

Practical acceptance also requires the existing 16-hour common recovery to finish within 0.05 C of 22 C and at most 1 ppm above 600 ppm. Cost includes this continuation; separate operating/recovery metrics are retained.

The economic screen additionally requires no fallback, no plant-side override, and every optimization call to have a validated incumbent with a reported relative gap at most 1%. For the thermostat the solver-quality gate is not applicable; it is not declared economically optimal. Even after passing these gates, differences in horizon, information and total computation must be disclosed.

## Stages

### 1. Matched-model nominal day-ahead budget sweep

Winter (seed 101) and summer (seed 303), 24 operating hours, use the same plant, forecast, initial state, tariff, objective weights and airflow modes at **0.5, 2, 10 and 30 seconds per solve**. The existing open-loop controller solves once and retains that plan.

A thermostat trajectory is run once per period/repeat as a reference and a constructive **soft-MILP objective witness**. Its matched inputs/model, model-domain bounds, replay and hardware checks are verified. Minimal endpoint comfort penalties are evaluated on that trajectory for comparison with a candidate objective. This can establish the existence of a better known feasible soft-MILP objective. It does not certify that strictly zero comfort violation is feasible.

The input hash must remain the same across a period's budget and penalty runs. Time limits can produce different incumbents on different machines. One repeat is an initial observation, not a statistical estimate; `--repeats` enables additional repetitions.

### 2. Separate penalty sweep

At a fixed **30-second** budget and unchanged 24-hour horizon, the original (temperature, CO2) weights are (100, 100). The four additional settings are:

| Temperature weight | CO2 weight |
|---:|---:|
| 10 | 100 |
| 1000 | 100 |
| 100 | 10 |
| 100 | 1000 |

Temperature units are EUR/(K h); CO2 units are EUR/(1000 ppm h). Only one weight changes per diagnostic. The (100, 100), 30-second budget-sweep result is the control; it is not rerun solely to fill another table cell.

Raw objective numbers across different weights are not comparable. The study also records objective components and a common-weight endpoint score. Actual continuous comfort remains the evaluator's metric, not this endpoint score.

If a gap-qualified solution still fails practical comfort, investigate the penalty tradeoff, endpoint-versus-continuous scoring and the feasible witness before attributing the result to insufficient time. If neither the optimizer nor the witness is practically acceptable, stronger-comfort feasibility is unresolved; a failure to find such a trajectory is not an infeasibility proof. The runner does not automatically raise a budget or penalty in response to an outcome.

### 3. Freeze the continuation settings

Selection uses only nominal winter/summer results. A candidate must pass the practical and economic screens in both periods and every repeat. Among qualifying candidates, retain the original weights when possible, then prefer the smaller budget, then the smaller change in weights. This is a declared engineering rule, not a search for a favorable MPC narrative.

The selected open-loop budget and weights are written to `frozen-settings.json`, with a content hash, before later scenarios are generated. MPC's six-hour horizon and two-second budget, and the matched-window two-second budget, are separately predeclared. They are not validated merely because an open-loop candidate qualified.

If no candidate qualifies, the continuation uses a clearly marked **unqualified diagnostic anchor**: original weights and the fixed penalty-sweep budget. Later runs remain diagnostic; the code does not present that anchor as a successful tuning result.

### 4. Representative matched-horizon feedback diagnostics

Two four-hour windows are each run nominally and with a disturbance:

- Winter 08:00–12:00: nominal and severe weather forecast error.
- Summer 04:00–08:00: nominal and severe early/high occupancy.

The existing open-loop controller optimizes the entire four-hour window once. MPC has the same initial four-hour lookahead and the same fixed end time, shrinking its remaining horizon as the window progresses. It reoptimizes every 15 minutes. Both use two seconds per call and the same frozen weights. The thermostat is also scored.

This explicitly changes the **experiment window**, not the open-loop controller's definition. It is not called a 24-hour day-ahead result. These checks remove the initial 24-hour-versus-six-hour horizon mismatch within the window. They do not equalize total computation or guarantee equal solve quality: open loop has one call; MPC has 16. Perfect-information nominal results and disturbed results are kept distinct.

### 5. Bounded held-out practical comparison

After freezing, three full-day scenarios use seeds not used in the nominal selection or prior reference run:

- Spring, seed 5202: severe weather error.
- Autumn, seed 5404: severe early/high occupancy.
- Spring, seed 5202: severe heat-loss mismatch.

This small held-out set uses the original practical policies: full-day open loop versus six-hour MPC, plus the thermostat. The open-loop budget comes from the frozen file; MPC stays at two seconds per call. All use the frozen weights, same realized inputs and common recovery.

The horizon, solve quality and daily computational effort remain different in this practical comparison. It does not isolate the effect of feedback. Held-out outcomes never enter the selection function and do not modify the frozen settings. New results can motivate a later, separately declared study, not retroactive tuning on this hold-out set.

## Run and resource limits

```bash
# Modest default: 18 nominal/budget/penalty runs.
hvac-benchmark sensitivity --output reports/sensitivity-nominal

# Continue from the recorded frozen settings.
hvac-benchmark sensitivity --stage feedback --freeze reports/sensitivity-nominal/frozen-settings.json --output reports/sensitivity-feedback
hvac-benchmark sensitivity --stage heldout --freeze reports/sensitivity-nominal/frozen-settings.json --output reports/sensitivity-heldout

# Explicit initial full staged study: 18 + 12 + 9 = 39 runs.
hvac-benchmark sensitivity --stage all --output reports/sensitivity-initial
```

The default nominal stage requests at most 325 seconds of solver time. The complete initial study requests at most 1,127 seconds, plus model construction, replay and reporting overhead. It does not launch a full-day 30-second MPC grid. A requested budget sum over 30 minutes requires the explicit `--allow-large` flag. CI also has a 30-minute job timeout.

Larger experiments can set `--budgets`, `--penalty-budget`, `--mpc-budget`, `--feedback-budget` and `--repeats`. Such changes define a new recorded protocol configuration. Standalone later stages take settings from the frozen file; its hash and protocol are checked. Output directories must be empty, preserving previous reports.

CI runs regression tests, both smoke entry points, and the bounded staged sensitivity experiment on main source changes. The original full 84-run reference command remains available through workflow dispatch (`study: reference` or `all`).

## Evidence written by the runner

- `metrics.csv`: all existing physical metrics, practical/quality gates, input hashes, settings, evaluation wall time, total daily solver effort, first-solve objective/bound/gap, and witness comparisons.
- `solves.csv`: every call's status, incumbent validity, objective, dual bound, relative gap, branch-node count when available, objective components, wall time, horizon length and fallback flag.
- `traces/`: existing requested/applied inputs, plant states, prices and per-call solver diagnostics.
- `figures/`: existing trajectory plots for matched-window and held-out comparisons.
- `manifest.json`: exact source revision, versions, protocol, acceptance rules, budgets, seeds, completion state and total measured time.
- `frozen-settings.json`: selection outcome and content hash, emitted before the later stages.
- `report.md`: a table generated from executed results and explicit interpretation gates.

Solve time includes model construction and any fallback rollout. Total daily solver time sums actual calls; overlapping MPC objectives are not summed into a fake daily objective. A timeout alone is neither a feasibility failure nor a causal explanation. Missing solver evidence remains missing rather than being filled with an invented bound or gap.
