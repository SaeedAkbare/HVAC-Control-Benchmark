# LinkedIn draft

Draft only; not published or sent to LinkedIn. Before posting, replace MAIN_REPOSITORY_URL with the final repository URL on the intended account. Findings refer only to the corrected source and executed study.

I’ve published an AI-assisted HVAC control benchmark comparing a thermostat, a frozen day-ahead schedule and model predictive control.

The problem is energy-cost minimization subject to hard temperature, CO2 and equipment constraints. It uses exact finite-mode dynamics, causal forecast updates and independent replay of the applied controls.

One finding: under unexpected early/high occupancy, the frozen plan exceeded the CO2 limit by about 1,561 ppm, while MPC maintained the operating limits. Under heat-loss mismatch, MPC also failed temperature constraints—those failures remain in the results.

The corrected study includes 46 passing tests and 34 simulation runs, with solver gaps, infeasibility and fallback operation reported explicitly. Horizons and computation differ between controllers, so the comparison has limits.

All weather, occupancy and prices are synthetic. These are simulation findings, with no field-savings claim.

Repository: MAIN_REPOSITORY_URL

#ModelPredictiveControl #Optimization #HVAC

Suggested image: [executed summer occupancy comparison](../reports/corrected-2026-11-15/figures/full_summer__occupancy_severe_r0.png).

Image caption: “Synthetic summer occupancy disturbance. Temperature, CO2 and electrical power for three controllers; shaded region is common recovery. The frozen plan violates realized comfort despite being feasible for its original forecast.”

Evidence: [corrected report](../reports/corrected-2026-11-15/README.md), [CI run](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/43710709106).
