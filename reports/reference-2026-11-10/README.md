# Reference run — 10 November 2026

These are executed simulation results, using surrogate inputs. This is a **short-budget reference run**, not a certified ranking of the controllers.

- [Tested source](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/commit/322c2bcb1c45cdcfb76b3136fe75051b1e4f3595)
- [Successful GitHub Actions run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42804919624)
- [Full artifact: traces, metadata, generated plots, and report](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/42804919624/artifacts/13758946685)
- [Permanent metrics CSV](metrics.csv)
- [Run provenance](provenance.json)

## How to read the results

The full matrix contains 28 scenarios and three controllers (84 runs). Cost and energy include 24 operating hours plus 16 hours of common recovery. Comfort columns below cover the operating period. All 84 runs reached the terminal recovery target and passed independent ODE replay and actuator audits. No solver fallback occurred.

**Solver quality is a material limitation.** Every day-ahead solve reached the 0.5-second limit; none was certified within the requested 1% gap. MPC made 2,688 solves: 1,139 ended within the requested tolerance and 1,549 returned accepted time-limited incumbents. Worst reported relative gaps approached one. An accepted incumbent satisfies the MILP's hard physical constraints, but comfort is soft, so it can still have substantial comfort violations.

For example, winter nominal open-loop control cost EUR 14.809 versus EUR 16.347 for the thermostat, while accumulating 39,017.54 ppm h of excess CO2 and 2.0502 K h of temperature violation. The lower bill is not an equivalent-comfort saving. Winter nominal MPC cost EUR 18.819 with 0.0042 K h temperature violation and zero excess-CO2 area. These observations do not isolate the value of feedback from solver effort, horizon length, or the baseline's comfort margin.

A longer-budget and formulation-sensitivity study is needed before economic rankings are useful. The fixed controllers and scenarios are retained here; the result is not tuned to make MPC win. Use both comfort measures, durations/peaks in the CSV, solve status, and terminal-state checks alongside every cost.

## All executed results

| Scenario | Controller | Cost EUR | Electricity kWh | Gas kWh | Temperature K h | CO2 ppm h | Time-limited solves |
|---|---|---:|---:|---:|---:|---:|---:|
| winter__nominal | thermostat | 16.347 | 4.766 | 207.289 | 0.0170 | 0.00 | 0/0 |
| winter__nominal | open_loop | 14.809 | 4.642 | 187.080 | 2.0502 | 39017.54 | 1/1 |
| winter__nominal | mpc | 18.819 | 6.612 | 235.555 | 0.0042 | 0.00 | 60/96 |
| winter__weather_mild | thermostat | 17.712 | 4.766 | 225.498 | 0.0170 | 0.00 | 0/0 |
| winter__weather_mild | open_loop | 15.324 | 4.934 | 193.052 | 4.1510 | 39017.54 | 1/1 |
| winter__weather_mild | mpc | 20.263 | 7.119 | 253.837 | 0.0136 | 0.00 | 60/96 |
| winter__weather_severe | thermostat | 19.078 | 4.766 | 243.707 | 0.0170 | 0.00 | 0/0 |
| winter__weather_severe | open_loop | 15.834 | 5.226 | 198.949 | 6.2518 | 39017.54 | 1/1 |
| winter__weather_severe | mpc | 21.289 | 6.470 | 268.889 | 0.0100 | 16.62 | 60/96 |
| winter__occupancy_mild | thermostat | 19.853 | 10.098 | 240.119 | 0.0000 | 0.00 | 0/0 |
| winter__occupancy_mild | open_loop | 14.227 | 4.350 | 180.162 | 0.1058 | 60088.48 | 1/1 |
| winter__occupancy_mild | mpc | 19.357 | 7.248 | 241.065 | 0.0106 | 0.00 | 60/96 |
| winter__occupancy_severe | thermostat | 19.301 | 10.670 | 231.210 | 0.0000 | 0.00 | 0/0 |
| winter__occupancy_severe | open_loop | 13.289 | 3.648 | 169.457 | 0.0000 | 96346.92 | 1/1 |
| winter__occupancy_severe | mpc | 20.833 | 8.764 | 256.925 | 0.0000 | 0.00 | 60/96 |
| winter__loss_mild | thermostat | 19.160 | 5.350 | 243.335 | 0.2752 | 0.00 | 0/0 |
| winter__loss_mild | open_loop | 17.141 | 5.692 | 214.942 | 7.5168 | 39017.54 | 1/1 |
| winter__loss_mild | mpc | 21.752 | 7.496 | 272.353 | 0.0768 | 0.00 | 60/96 |
| winter__loss_severe | thermostat | 23.282 | 6.400 | 295.156 | 1.2388 | 0.00 | 0/0 |
| winter__loss_severe | open_loop | 19.975 | 7.123 | 249.120 | 16.9061 | 39017.54 | 1/1 |
| winter__loss_severe | mpc | 27.221 | 10.066 | 338.639 | 0.1811 | 0.00 | 60/96 |
| spring__nominal | thermostat | 5.311 | 2.285 | 65.369 | 0.0000 | 0.00 | 0/0 |
| spring__nominal | open_loop | 5.605 | 1.431 | 71.698 | 0.0000 | 39017.54 | 1/1 |
| spring__nominal | mpc | 5.831 | 2.809 | 71.145 | 0.0000 | 0.00 | 53/96 |
| spring__weather_mild | thermostat | 6.368 | 2.869 | 78.261 | 0.0000 | 0.00 | 0/0 |
| spring__weather_mild | open_loop | 6.165 | 1.723 | 78.561 | 0.0000 | 39017.54 | 1/1 |
| spring__weather_mild | mpc | 7.067 | 3.612 | 86.000 | 0.0000 | 0.00 | 51/96 |
| spring__weather_severe | thermostat | 7.552 | 3.189 | 93.376 | 0.0000 | 0.00 | 0/0 |
| spring__weather_severe | open_loop | 6.719 | 2.015 | 85.336 | 0.0000 | 39017.54 | 1/1 |
| spring__weather_severe | mpc | 8.229 | 4.098 | 100.375 | 0.0000 | 0.00 | 54/96 |
| spring__occupancy_mild | thermostat | 6.399 | 7.589 | 66.000 | 0.0000 | 0.00 | 0/0 |
| spring__occupancy_mild | open_loop | 4.993 | 1.021 | 64.381 | 0.0000 | 60088.48 | 1/1 |
| spring__occupancy_mild | mpc | 6.089 | 4.053 | 71.262 | 0.0000 | 0.00 | 53/96 |
| spring__occupancy_severe | thermostat | 5.853 | 7.897 | 57.693 | 0.0000 | 0.00 | 0/0 |
| spring__occupancy_severe | open_loop | 3.920 | 1.074 | 49.968 | 0.0000 | 96346.92 | 1/1 |
| spring__occupancy_severe | mpc | 5.792 | 5.156 | 64.542 | 0.0000 | 0.00 | 54/96 |
| spring__loss_mild | thermostat | 6.534 | 2.605 | 81.007 | 0.0000 | 0.00 | 0/0 |
| spring__loss_mild | open_loop | 6.849 | 1.751 | 87.625 | 0.0000 | 39017.54 | 1/1 |
| spring__loss_mild | mpc | 7.126 | 3.299 | 87.198 | 0.0000 | 0.00 | 52/96 |
| spring__loss_severe | thermostat | 10.838 | 10.351 | 119.856 | 0.0000 | 0.00 | 0/0 |
| spring__loss_severe | open_loop | 8.526 | 2.335 | 108.776 | 0.0365 | 39017.54 | 1/1 |
| spring__loss_severe | mpc | 8.513 | 3.328 | 105.853 | 0.0214 | 0.00 | 53/96 |
| summer__nominal | thermostat | 9.094 | 52.069 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__nominal | open_loop | 6.358 | 38.466 | 0.000 | 3.4505 | 40877.78 | 1/1 |
| summer__nominal | mpc | 9.227 | 53.958 | 0.000 | 0.0000 | 0.00 | 52/96 |
| summer__weather_mild | thermostat | 9.933 | 57.074 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__weather_mild | open_loop | 6.622 | 40.102 | 0.000 | 5.0930 | 40877.78 | 1/1 |
| summer__weather_mild | mpc | 11.484 | 64.960 | 0.000 | 0.0000 | 0.00 | 56/96 |
| summer__weather_severe | thermostat | 10.876 | 62.242 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__weather_severe | open_loop | 6.860 | 41.541 | 0.000 | 6.8437 | 40877.78 | 1/1 |
| summer__weather_severe | mpc | 11.523 | 64.934 | 0.000 | 0.0000 | 26.01 | 56/96 |
| summer__occupancy_mild | thermostat | 12.296 | 69.043 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__occupancy_mild | open_loop | 6.646 | 40.245 | 0.000 | 5.4850 | 62098.47 | 1/1 |
| summer__occupancy_mild | mpc | 11.824 | 67.885 | 0.000 | 0.0000 | 0.00 | 53/96 |
| summer__occupancy_severe | thermostat | 13.331 | 74.741 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__occupancy_severe | open_loop | 7.125 | 43.100 | 0.000 | 9.5760 | 98506.67 | 1/1 |
| summer__occupancy_severe | mpc | 13.489 | 74.757 | 0.000 | 0.0000 | 34.70 | 56/96 |
| summer__loss_mild | thermostat | 9.998 | 57.202 | 0.000 | 0.0000 | 0.00 | 0/0 |
| summer__loss_mild | open_loop | 7.005 | 42.276 | 0.000 | 4.4603 | 40877.78 | 1/1 |
| summer__loss_mild | mpc | 12.020 | 68.786 | 0.000 | 0.0001 | 0.00 | 56/96 |
| summer__loss_severe | thermostat | 11.230 | 64.081 | 0.030 | 0.0000 | 0.00 | 0/0 |
| summer__loss_severe | open_loop | 7.807 | 46.818 | 0.000 | 6.0148 | 40877.78 | 1/1 |
| summer__loss_severe | mpc | 12.602 | 71.743 | 0.010 | 0.0005 | 0.00 | 56/96 |
| autumn__nominal | thermostat | 9.801 | 3.628 | 122.853 | 0.0000 | 0.00 | 0/0 |
| autumn__nominal | open_loop | 30.284 | 18.336 | 359.338 | 0.0094 | 0.00 | 1/1 |
| autumn__nominal | mpc | 10.426 | 4.451 | 129.447 | 0.0171 | 0.00 | 53/96 |
| autumn__weather_mild | thermostat | 8.727 | 3.069 | 109.608 | 0.0000 | 0.00 | 0/0 |
| autumn__weather_mild | open_loop | 29.038 | 17.607 | 344.414 | 0.0094 | 0.00 | 1/1 |
| autumn__weather_mild | mpc | 9.174 | 3.790 | 114.130 | 0.0000 | 0.00 | 53/96 |
| autumn__weather_severe | thermostat | 7.653 | 2.468 | 96.479 | 0.0000 | 0.00 | 0/0 |
| autumn__weather_severe | open_loop | 27.768 | 16.877 | 328.968 | 0.0094 | 0.00 | 1/1 |
| autumn__weather_severe | mpc | 8.229 | 3.543 | 101.788 | 0.0000 | 0.00 | 53/96 |
| autumn__occupancy_mild | thermostat | 11.603 | 9.048 | 133.343 | 0.0000 | 0.00 | 0/0 |
| autumn__occupancy_mild | open_loop | 30.031 | 18.190 | 356.325 | 0.0523 | 0.00 | 1/1 |
| autumn__occupancy_mild | mpc | 11.099 | 5.432 | 135.647 | 0.0838 | 0.00 | 53/96 |
| autumn__occupancy_severe | thermostat | 11.152 | 9.385 | 126.292 | 0.0000 | 0.00 | 0/0 |
| autumn__occupancy_severe | open_loop | 29.565 | 18.016 | 350.529 | 0.0304 | 0.00 | 1/1 |
| autumn__occupancy_severe | mpc | 11.153 | 6.510 | 133.702 | 0.0006 | 0.00 | 54/96 |
| autumn__loss_mild | thermostat | 12.095 | 5.377 | 149.649 | 0.0007 | 0.00 | 0/0 |
| autumn__loss_mild | open_loop | 31.445 | 18.774 | 373.657 | 2.5714 | 0.00 | 1/1 |
| autumn__loss_mild | mpc | 12.799 | 5.128 | 159.510 | 0.0317 | 0.00 | 53/96 |
| autumn__loss_severe | thermostat | 14.707 | 5.353 | 184.639 | 0.2007 | 0.00 | 0/0 |
| autumn__loss_severe | open_loop | 33.058 | 19.476 | 393.094 | 6.2756 | 0.00 | 1/1 |
| autumn__loss_severe | mpc | 17.408 | 6.827 | 216.786 | 0.0500 | 0.00 | 55/96 |

CSV values were preserved from the JSON metric records emitted by the completed Actions job. No measured-building or field-savings claim is implied. The archive contains the original per-step traces, figures, and environment metadata; it may require GitHub sign-in and has an expiration date. This CSV and provenance file remain in Git history.
