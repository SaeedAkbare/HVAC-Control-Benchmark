# Validation record

All execution described here took place on GitHub Actions. The original local project was not used or modified.

## Sensitivity validation — 11 November 2026

- Tested source: [e7ccaae6e269694bd7a18683a2d115b7667b876a](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/commit/e7ccaae6e269694bd7a18683a2d115b7667b876a).
- [Successful Actions run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/43041943285).
- **39 regression tests passed** in 1.88 seconds; 14 upstream Matplotlib/Pyparsing deprecation warnings.
- **12 existing benchmark smoke runs and three sensitivity smoke runs completed.**
- **39 sensitivity study runs completed:** 18 nominal/budget/penalty, 12 matched-window feedback, and nine held-out runs.
- All 39 passed independent replay and equipment audits and reached the common recovery target. Maximum replay discrepancies were 4.228e-13 C and 6.055e-8 ppm.
- All 375 optimization calls returned validated incumbents: 194 within the requested tolerance and 181 accepted at the time limit. There were zero fallbacks or actuator overrides.
- No nominal tuning candidate qualified across both periods. The continuation used the predeclared, explicitly unqualified diagnostic anchor; held-out outcomes did not change it.
- [Permanent results, all metric rows, frozen settings and provenance](../reports/sensitivity-2026-11-11/README.md); [complete artifact](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/43041943285/artifacts/13866317642) with per-call solver evidence, trajectories and figures.

The new checks cover solver objective components and raw diagnostics, missing/invalid incumbents, independent peak/duration gates, practical-versus-solver-quality acceptance, nominal-only selection, frozen-file integrity, output preservation and explicit approval of oversized requested compute budgets. These supplement the original regression coverage below. Python and dependency versions are unchanged from the reference run.

The study verifies the staged runner and its recorded evidence. It does not certify optimized economics: all nominal optimizer gaps remained far above 1%, and none of the held-out optimizer runs met the every-call quality gate. The matched summer occupancy window isolates the initial horizon and shows a useful causal response to new observations, while retaining unequal total computation. See the result report for cost, comfort and qualification limits.

## Original reference run — 10 November 2026

- Tested source: [322c2bcb1c45cdcfb76b3136fe75051b1e4f3595](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/commit/322c2bcb1c45cdcfb76b3136fe75051b1e4f3595).
- [Successful Actions run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42804919624), executed 10 November 2026; results reviewed and recorded 11 November 2026.
- Python 3.11.18, NumPy 2.2.6, SciPy 1.15.3, Matplotlib 3.10.3, pytest 8.3.5.
- **29 regression tests passed**.
- **12 smoke controller runs and 84 full controller runs completed**.
- **All 84 full runs reached the terminal recovery target**, with zero solver fallbacks.
- All full runs passed independent ODE replay and physical actuator audits. Maximum replay discrepancy was 2.096e-13 C and 1.077e-7 ppm.
- [Permanent reference results and interpretation](../reports/reference-2026-11-10/README.md), including every metric row and run provenance.
- [Full artifacts](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42804919624/artifacts/13758946685) and [smoke artifacts](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42804919624/artifacts/13757209478) contain executed traces, figures, metadata, and generated reports.

Regression coverage includes exact/independent ODE agreement, zero-flow behavior, supply and meter limits, threshold-crossing metrics, deterministic inputs, causal forecasts, invalid solver-output rejection, frozen open-loop scheduling, first-action MPC, nominal model isolation under plant mismatch, and severe cold recovery.

## What the reference pass does and does not establish

The pass verifies package execution, accounting, physical consistency, and the stated tests. It is not field validation or a certificate of economically optimal control.

The full reference run used a **0.5-second solver limit**. All 28 day-ahead solves and 1,549 of 2,688 MPC solves returned accepted time-limited incumbents. The other 1,139 MPC solves ended within the requested 1% solver tolerance. Worst reported gaps approached one. Several day-ahead plans had large comfort violations, even in the nominal case: comfort constraints are soft and a hardware-feasible incumbent can still have a poor objective.

Read the complete cost/comfort table before interpreting a lower bill. These results support a runnable, audited benchmark; stronger economic comparisons need longer-budget and formulation-sensitivity experiments. No result is presented as proof that MPC always wins.

## Terminal protocol correction

The [first full run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42794146594) completed, but a six-hour recovery left 20 of 84 runs short of the terminal temperature target. A new conservative cold-case regression then found a 0.1213 C deficit at 12 hours.

The final protocol uses the same **16-hour recovery** for every controller and retains the 0.05 C final temperature tolerance. The single weather event does not repeat in the recovery period. All 28 scenarios were rerun after this change; all 84 final controller runs recovered. Operating-day controllers, objective penalties, and evaluation seeds were not tuned to favor a method. Results from different recovery protocols must not be mixed.

The common continuation includes holding energy after restoration; full-run primary totals therefore cover 40 hours. Operation and recovery metrics are also supplied separately.

Documentation and archived result files may be committed after the tested source revision without rerunning the numerical code. The source revision and artifact digest in the provenance file identify the exact executed version.
