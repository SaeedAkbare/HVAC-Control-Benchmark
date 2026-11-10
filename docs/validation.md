# Validation record

Validation was executed on GitHub Actions, not on the maintainer's local computer.

## First runnable version

- Source revision: [22d4d090345051ee516b4e4f259f699187897573](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/commit/22d4d090345051ee516b4e4f259f699187897573).
- [Actions run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42794146594), started 10 November 2026.
- Python 3.11.18, NumPy 2.2.6, SciPy 1.15.3, Matplotlib 3.10.3, pytest 8.3.5.
- **27 regression tests passed**. Coverage includes independent ODE agreement, conservation/zero-flow behavior, supply and meter checks, threshold-crossing metrics, deterministic scenarios, causal forecasts, solver-output rejection, frozen open-loop scheduling, first-action MPC, and nominal model isolation during plant mismatch.
- **12 smoke controller runs completed**, with independent replay and physical actuator audits passing. All 12 reached the common recovery target.
- [Smoke artifact: CSVs, metadata, plots, and generated report](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42794146594/artifacts/13752733106).
- The full 84-controller-run benchmark was still running when this documentation snapshot was written. No full-suite pass or full-suite performance result is claimed here yet.

Smoke used a one-second MILP budget per call. Several accepted incumbents had large relative MIP gaps, approaching one. This means the run validates execution and feasibility, not near-optimal economic performance. The small smoke horizon is also not the all-day disturbance experiment. See the method for how recovery and comfort affect cost comparisons.

The ODE replay is independent numerical implementation of the same assumed physics. It is not validation against measured building behavior.


## Terminal protocol correction

The first full run completed all 84 controller experiments and passed replay and physical audits, but 20 runs did not reach the terminal recovery target after six hours. This is a protocol limitation, not a test failure to hide. The recovery duration is now 12 hours for every method, and a cold-start/severe-heat-loss regression was added. The single weather disturbance is also prevented from repeating in the next morning's recovery period.

The revised source requires a new complete Actions run. Results from the six-hour run must not be mixed with the revised protocol.
