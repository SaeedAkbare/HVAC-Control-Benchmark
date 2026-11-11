# Sensitivity results — 11 November 2026

The bounded study completed, but **no nominal tuning candidate passed every predeclared gate**. Increasing the day-ahead budget from 0.5 to 30 seconds greatly improved the returned objectives; it did not produce a 1%-gap certificate. A matched-window occupancy example shows a useful feedback response, while the full-day held-out results remain unsuitable for a general economic ranking.

This report describes one executed repeat on synthetic inputs. It preserves the [earlier reference](../reference-2026-11-10/README.md) as a separate experiment.

## Execution and evidence

- Tested source: [e7ccaae](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/commit/e7ccaae6e269694bd7a18683a2d115b7667b876a).
- [Successful Actions run 43041943285](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/43041943285), 11 November 2026.
- **39 regression tests passed**; the existing 12-run smoke suite and the new three-run sensitivity smoke completed.
- **39 study runs:** two thermostat witnesses, eight budget cases, eight penalty cases, 12 matched-window feedback cases and nine held-out cases.
- All 39 passed equipment audits and independent ODE replay and reached the common recovery target. All 375 optimization calls returned validated incumbents, with zero fallback calls and zero actuator overrides.
- Of those calls, 194 ended within the requested solver tolerance and 181 returned accepted time-limited incumbents. An accepted incumbent is not a comfort or optimality certificate.
- Maximum replay discrepancy: 4.228e-13 C and 6.055e-8 ppm.
- Actual study wall time: 767.625 seconds; summed solve/build/fallback time: 764.399 seconds. The predeclared solver-budget sum was 1,127 seconds.
- Python 3.11.18; NumPy 2.2.6; SciPy 1.15.3; Matplotlib 3.10.3; pytest 8.3.5. The 14 test warnings were upstream Matplotlib/Pyparsing deprecations.

[metrics.csv](metrics.csv) contains every metric and gate for all 39 runs. [metrics.jsonl](metrics.jsonl) preserves the exact JSON metric records emitted to the job log. [manifest.json](manifest.json), [frozen-settings.json](frozen-settings.json), and [provenance.json](provenance.json) preserve the executed configuration and source/artifact identity. CSV values were reconstructed from those logged metric records; JSON records retain their original numeric spelling.

The [full artifact](https://github.com/SaeedAkbare/HVAC-Control-Benchmark/actions/runs/43041943285/artifacts/13866317642) contains all 375 per-call records in `solves.csv`, 39 trajectories, seven comparison figures, and the runner's generated report. GitHub records its expiration as 9 February 2027; these checked-in summaries, metrics and settings remain in repository history. Per-call rows and trajectory/figure files have not been copied into this permanent archive.

## Reading the gates and costs

The [protocol](../../docs/sensitivity.md) was committed before execution. All six operating comfort limits must pass: temperature peak ≤0.5 C, duration ≤0.5 h and area ≤0.1 K h; CO2 peak ≤100 ppm, duration ≤0.25 h and area ≤25 ppm h. These are simulation screening assumptions, not regulatory or health standards.

Practical acceptance also requires physical audits and the existing common recovery target. The economic screen adds a validated incumbent and reported gap ≤0.01 on **every** optimization call, with no fallback or override. Solver quality is not applicable to the thermostat.

Unless marked “Operation,” costs and electricity/gas quantities include 16 hours of common recovery: 40 hours for full-day cases and 20 hours for four-hour diagnostics. Comfort columns describe operation only. Recovery comfort metrics remain in the CSV; terminal recovery does not imply comfort throughout that continuation. Gaps are fractions, so 0.999 means 99.9%. Temperature and CO2 peaks are excursions beyond the applicable limit, not absolute room measurements.

## Nominal budget sweep

Winter seed 101 and summer seed 303 use matched model and forecast, a 24-hour open-loop plan, original weights (100, 100), identical initial conditions and identical input hashes within each period.

| Period | Budget s | Incumbent objective | Dual bound | Relative gap | Total EUR | Practical |
|---|---|---|---|---|---|---|
| winter | 0.5 | 4155.8886 | 0.002903 | 0.999999 | 14.8090 | fail |
| winter | 2 | 163.6083 | 0.003016 | 0.999982 | 32.2141 | fail |
| winter | 10 | 32.8356 | 0.003140 | 0.999904 | 16.7702 | fail |
| winter | 30 | 8.7185 | 0.003140 | 0.999640 | 17.5998 | fail |
| summer | 0.5 | 4503.0288 | 0.002903 | 0.999999 | 6.3582 | fail |
| summer | 2 | 410.4843 | 0.003094 | 0.999992 | 8.4494 | fail |
| summer | 10 | 54.5972 | 0.003160 | 0.999942 | 10.2755 | fail |
| summer | 30 | 5.5458 | 0.003161 | 0.999430 | 11.1032 | pass |

| Period | Budget s | T peak C | T duration h | T area K h | CO2 peak ppm | CO2 duration h | CO2 area ppm h |
|---|---|---|---|---|---|---|---|
| winter | 0.5 | 0.2704 | 10.0000 | 2.0502 | 3975.76 | 14.8350 | 39017.54 |
| winter | 2 | 0.6264 | 4.0000 | 1.5357 | 0.00 | 0.0000 | 0.00 |
| winter | 10 | 0.0825 | 1.5000 | 0.0928 | 309.68 | 1.7196 | 157.74 |
| winter | 30 | 0.0099 | 0.2314 | 0.0011 | 103.19 | 0.6059 | 30.71 |
| summer | 0.5 | 1.4769 | 4.5434 | 3.4505 | 4100.00 | 15.1111 | 40877.78 |
| summer | 2 | 0.9531 | 3.0346 | 1.4588 | 634.62 | 9.9057 | 2347.96 |
| summer | 10 | 0.3068 | 1.4220 | 0.2374 | 390.79 | 1.1159 | 195.27 |
| summer | 30 | 0.0000 | 0.0000 | 0.0000 | 2.54 | 0.0067 | 0.01 |

The winter incumbent objective fell from 4155.8886 to 8.7185; summer fell from 4503.0288 to 5.5458. These are improvements in the fixed soft objective, not percentages of energy savings. Dual bounds remained near 0.003, leaving all eight gaps far above 1%.

At 30 seconds the summer plan passed practical limits. Winter still failed all three CO2 criteria: 103.19 ppm peak, 0.6059 hours and 30.71 ppm h. Neither period passed the solver-quality gate. Bills were not monotone in solve budget and must be read with the service metrics.

The independently replayed thermostat witnesses passed practical limits in both periods. Their original-weight endpoint objectives were **3.6350 (winter)** and **3.8485 (summer)**, below every returned nominal open-loop incumbent, including all penalty variants evaluated under that variant's weights. Their endpoint penalties were zero; winter still had a small continuous temperature excursion (0.1471 C peak, 0.2308 hours, 0.0170 K h). Thus an acceptable trajectory and a better known soft-MILP objective exist in these cases. This does not prove strict zero continuous violation or global optimality.

Together, the poor gaps and better feasible witnesses establish unresolved solution quality. The observed time-budget improvement supports solver/search difficulty as part of the explanation; it does not establish that increasing time alone will resolve it or exclude formulation and penalty effects.

## Penalty sweep at a fixed 30 seconds

Only one weight changes at a time. The original-weight 30-second budget result is reused as the control. Components below are operating energy cost and the two weighted endpoint penalties. Their sum is the incumbent objective under that row's weights. The common-weight score reevaluates each trajectory at (100, 100); it remains an endpoint score, not the continuous comfort assessment.

| Period | T / CO2 weights | Energy / T / CO2 objective components | Common-weight score | Relative gap | Practical | Failed operating criteria |
|---|---|---|---|---|---|---|
| winter | 100 / 100 | 4.3626 / 0.2487 / 4.1073 | 8.7185 | 0.999640 | fail | CO2 peak, CO2 duration, CO2 area |
| winter | 10 / 100 | 5.1027 / 2.0394 / 0.1429 | 25.6399 | 0.999555 | fail | temperature duration, temperature area |
| winter | 1000 / 100 | 5.4565 / 16.4762 / 8.7757 | 15.8798 | 0.999907 | fail | temperature duration, CO2 peak, CO2 duration, CO2 area |
| winter | 100 / 10 | 2.8125 / 1.1854 / 1.0033 | 14.0312 | 0.999379 | fail | CO2 peak, CO2 duration, CO2 area |
| winter | 100 / 1000 | 4.8172 / 18.9142 / 0.0000 | 23.7314 | 0.999879 | fail | temperature duration, temperature area |
| summer | 100 / 100 | 5.4824 / 0.0000 / 0.0634 | 5.5458 | 0.999430 | pass | none |
| summer | 10 / 100 | 6.0238 / 0.0000 / 0.0000 | 6.0238 | 0.999446 | pass | none |
| summer | 1000 / 100 | 5.3769 / 0.0000 / 0.0000 | 5.3769 | 0.999394 | pass | none |
| summer | 100 / 10 | 4.6643 / 0.0000 / 1.5176 | 19.8405 | 0.999504 | fail | CO2 peak, CO2 duration, CO2 area |
| summer | 100 / 1000 | 5.4136 / 0.0000 / 0.0000 | 5.4136 | 0.999454 | pass | none |

All winter variants failed practical screening. Four of five summer settings passed practical screening, but all ten entries still had gaps above 99.9%. Lowering the summer CO2 weight to 10 coincided with 219.53 ppm peak CO2 excess over 1.4316 hours; raising the winter CO2 weight to 1000 removed CO2 excess but left excessive temperature duration and area.

These observations do not identify an optimal penalty scale: none of the nominal solves was gap-qualified, and every returned objective was worse than its feasible thermostat witness. There is **no nominal near-optimal-but-uncomfortable result** here from which to isolate a penalty tradeoff. Solver search, the weak bound and endpoint-versus-continuous scoring remain relevant.

## Settings frozen before continuation

No candidate qualified across both nominal periods. The recorded outcome is `unqualified_diagnostic_anchor`, not a successfully tuned configuration:

- Open loop: 30 seconds per solve; temperature and CO2 weights both 100.
- Practical full-day MPC: two seconds per solve, six-hour horizon.
- Matched-window optimization: two seconds per solve, four-hour initial horizon and a common fixed end time.
- Freeze ID: `1618a9fcfaac4ede5dd47ab41a91dcc08e7fbed23e4f989faafc5c3dec24e6c3`.

The freeze was emitted at 14:54:46 UTC, before feedback and held-out execution. Every subsequent row carries that same identifier. The code generates later scenarios only after writing the frozen settings. Input hashes match across all three controllers in each comparison. New held-out seeds 5202 and 5404 were excluded from selection.

## Matched-window feedback diagnostics

Winter covers 08:00–12:00 and summer 04:00–08:00. Open loop solves the whole four-hour window once. MPC starts with the same lookahead and replans every 15 minutes to the same fixed end time: 16 calls versus one. Equal per-call limits do not equalize daily computation or solve quality.

| Window / case | Method | Operation EUR | Total EUR | CO2 peak ppm | CO2 duration h | Max gap | Solve total s | Practical |
|---|---|---|---|---|---|---|---|---|
| winter / nominal | Thermostat | 0.1019 | 9.4492 | 0.00 | 0.0000 | — | 0.00 | pass |
| winter / nominal | Open loop | 0.1098 | 9.4515 | 0.00 | 0.0000 | 0.985103 | 2.01 | pass |
| winter / nominal | MPC | 0.0557 | 9.2302 | 0.00 | 0.0000 | 0.985103 | 12.12 | pass |
| winter / weather_severe | Thermostat | 0.1019 | 10.3916 | 0.00 | 0.0000 | — | 0.00 | pass |
| winter / weather_severe | Open loop | 0.1098 | 10.2399 | 0.00 | 0.0000 | 0.985103 | 2.01 | pass |
| winter / weather_severe | MPC | 0.0557 | 10.0736 | 0.00 | 0.0000 | 0.985103 | 12.67 | pass |
| summer / nominal | Thermostat | 0.0000 | 5.7815 | 0.00 | 0.0000 | — | 0.00 | pass |
| summer / nominal | Open loop | 0.0000 | 5.7815 | 0.00 | 0.0000 | 0.000000 | 0.01 | pass |
| summer / nominal | MPC | 0.0000 | 5.7815 | 0.00 | 0.0000 | 0.000000 | 0.07 | pass |
| summer / occupancy_severe | Thermostat | 0.2585 | 6.9545 | 0.00 | 0.0000 | — | 0.00 | pass |
| summer / occupancy_severe | Open loop | 0.0000 | 6.7202 | 1100.00 | 1.4667 | 0.000000 | 0.01 | fail |
| summer / occupancy_severe | MPC | 0.0629 | 6.7789 | 0.00 | 0.0000 | 0.006479 | 1.62 | pass |

All temperature excursion metrics in these windows were zero. The nominal summer case was a useful no-action control: all three methods had identical cost and comfort. Under early/high summer occupancy, the frozen plan retained its initially optimal zero-action schedule. Actual CO2 excess reached **1100 ppm for 1.4667 hours**, with area 806.6667 ppm h. MPC and the thermostat had zero operating CO2 excess.

Both optimization methods met the per-call gap gate in the nominal and disturbed summer windows, including every MPC call (worst disturbed-case gap 0.006479). This supports a narrow conclusion: using newly observed occupancy within this particular matched window prevented the frozen plan's service failure. MPC spent 1.62 seconds across 16 calls versus about 0.01 seconds for open loop. It does not establish equal-computation superiority, general savings, or full-day performance.

The disturbed open-loop summer solve was optimal **for its original forecast**. Its realized comfort failure is evidence of unexpected occupancy, not evidence that a nearly optimal matched-model nominal solution chose inadequate comfort penalties. The artifact's generic “gap-qualified comfort failure” count includes this disturbed row; interpret it with that distinction.

All winter window runs passed comfort. Operation costs were unchanged between nominal and weather-disturbed cases for each controller, and the optimizer gaps remained about 0.985. These windows therefore do not establish a weather-feedback advantage.

## Held-out practical comparison

These are 24-hour cases with 16-hour recovery. Open loop retains the 24-hour plan at 30 seconds; MPC uses a six-hour horizon at two seconds per call. Spring seed 5202 supplies weather/loss cases; autumn seed 5404 supplies occupancy. No held-out outcome changed the frozen settings.

| Case / seed | Method | Total EUR | Electricity kWh | Gas kWh | CO2 peak ppm | CO2 duration h | Max gap | Solve total s | Practical |
|---|---|---|---|---|---|---|---|---|---|
| weather_severe / 5202 | Thermostat | 6.6893 | 3.0243 | 82.5061 | 0.00 | 0.0000 | — | 0.00 | pass |
| weather_severe / 5202 | Open loop | 7.0989 | 3.8364 | 86.1649 | 0.00 | 0.0000 | 0.990191 | 30.03 | pass |
| weather_severe / 5202 | MPC | 7.0887 | 3.4386 | 86.9403 | 0.00 | 0.0000 | 0.996690 | 105.11 | pass |
| occupancy_severe / 5404 | Thermostat | 10.8490 | 9.3565 | 121.6518 | 0.00 | 0.0000 | — | 0.00 | pass |
| occupancy_severe / 5404 | Open loop | 8.4130 | 3.4294 | 104.5013 | 1497.65 | 6.5976 | 0.989449 | 30.02 | fail |
| occupancy_severe / 5404 | MPC | 11.0279 | 6.3482 | 131.9104 | 0.00 | 0.0000 | 0.999655 | 108.04 | pass |
| loss_severe / 5202 | Thermostat | 8.1560 | 5.3518 | 97.1327 | 0.00 | 0.0000 | — | 0.00 | pass |
| loss_severe / 5202 | Open loop | 7.2671 | 3.2430 | 89.5812 | 0.00 | 0.0000 | 0.990191 | 30.02 | pass |
| loss_severe / 5202 | MPC | 7.3723 | 2.7964 | 92.1897 | 0.00 | 0.0000 | 0.988513 | 105.16 | pass |

All nine passed the temperature criteria and recovered. In the occupancy case, open loop's lower total bill accompanied CO2 excess of 1497.65 ppm over 6.5976 hours (3008.68 ppm h); it failed practical acceptance. MPC and the thermostat passed. The other two cases passed practical limits for all methods.

No held-out optimizer run passed the every-call 1% quality gate. MPC used roughly 105–108 seconds across 96 calls per day, versus about 30 seconds and one call for open loop. These are descriptive costs and service outcomes under different horizons and computational effort. They do not isolate feedback or justify ranking the controllers economically.

## Limits and remaining work

This study used one repeat, two nominal surrogate days, four short feedback cases and three held-out cases. It provides no confidence intervals, field validation or universal controller ranking. The acceptable thermostat witnesses do not certify that the optimizer has found the best acceptable solution.

Repeated runs, stronger solver/formulation diagnostics, larger independent held-out sets, and full-day comparisons with matched horizons and explicitly controlled total computation remain unexecuted. Any next study should declare its settings and new evaluation inputs before inspecting its outcomes. The previous reference files and this study's raw evidence should remain separate.
