# Method

## Scope and units

The model represents a hypothetical 960 m3 room or office zone. A 320 m2 floor area with a 3 m ceiling is one possible interpretation, not a measured building. State variables are zone temperature in degrees C and well-mixed CO2 concentration in ppm. Controls are held for 15 minutes. All integration time is in hours.

| Parameter | Assumption | Interpretation |
|---|---:|---|
| Effective thermal capacitance | 20 kWh/K | Includes fabric and contents, not just air |
| Nominal heat-loss coefficient UA | 0.38 kW/K | Sensible heat transfer to outside |
| Air density | 1.20 kg/m3 | Constant |
| Air specific heat | 1.005 kJ/(kg K) | Flow times cp gives kW/K |
| Heating / cooling capacity | 18 / 16 kW | Delivered/removed sensible coil heat |
| Supply temperature | 12 to 40 C | Applies whenever the fan is on |
| Maximum supply flow | 1.5 kg/s | Outdoor flow never exceeds total flow |
| Maximum fan electricity | 0.60 kW | Cubic law in total flow |
| Gas efficiency / cooling COP | 0.96 / 3.40 | Constant; no part-load model |
| Background sensible gain | 0.60 kW | Constant |
| Per-person sensible gain | 0.12 kW | Hypothetical sedentary/light office load |
| Per-person CO2 generation | 0.018 m3/h | Illustrative constant, not person-specific |
| Outdoor CO2 | 420 ppm | Fixed reference for this experiment |

These are transparent design assumptions, not calibrated parameters or a claim of compliance with a building standard. For scale, the nominal no-ventilation thermal time constant is 20/0.38, about 52.6 hours. Air alone would have much less capacitance. The six airflow choices below correspond to simple equipment operating modes.

| Mode | Total kg/s | Fresh kg/s |
|---|---:|---:|
| off | 0 | 0 |
| low | 0.45 | 0.12 |
| recirculate | 1.50 | 0.12 |
| medium | 0.90 | 0.35 |
| high | 1.50 | 0.70 |
| purge | 1.50 | 1.50 |

The recirculate mode still has 0.12 kg/s of fresh air. The fan-off mode has neither mechanical ventilation nor coil output. Infiltration, latent loads, fan heat, solar gains, humidity, stratification, duct losses, and equipment start/stop costs are not modeled.

## Physical balance

Let T be temperature, c be CO2 ppm, n be occupants, f be fresh-air kg/s, and q = heat - cool be signed coil kW. With constant inputs over an interval:

```text
Cth dT/dt = (UA + cp f)(Tout - T) + 0.60 + 0.12 n + q
dc/dt = [3600 f/(rho V)](420 - c) + [1e6 * 0.018/V] n
```

The thermal and CO2 equations are solved with their exact exponential transitions. With zero fresh air, the CO2 equation becomes linear accumulation. The controller uses the same transition formula with its nominal UA; the realized plant can have a different UA.

For an active supply mode, the coil inlet is mixed outdoor and recirculated air:

```text
Tmixed = (1 - fresh/total) T + (fresh/total) Tout
Tsupply = Tmixed + q/(cp total)
Pfan = 0.60 (total/1.50)^3
```

Supply limits are checked at both ends of each held-input interval. Temperature and therefore mixed/supply temperature are monotone within that interval, so this covers the interior too.

## Comfort and energy

| Occupancy | Temperature range | CO2 upper bound |
|---|---|---|
| At least one person | 20 to 24 C | 1000 ppm |
| Empty | 18 to 27 C | 1400 ppm |

The same realized occupancy determines the scoring limits for every controller. An optimizer uses forecast occupancy when predicting its future limits. The thermostat uses current observed occupancy.

Electricity is fan power plus cooling divided by COP. Gas is delivered heat divided by efficiency. Both are integrated to kWh and kept separate. Cost is electricity times the announced electricity price plus gas times 0.075 EUR/kWh. There is no demand charge, carbon objective, export, or negative tariff. No source-energy or carbon comparison is inferred from adding the two meters.

## Controllers

The thermostat has a 0.4 C inner margin inside the relevant temperature band. Outside that inner band it requests enough sensible output to approach its boundary in one interval, subject to equipment capacity. It selects an airflow mode that can provide the required ventilation and temperature response, breaking equal-response ties by fan power. Inside the band it uses the least ventilation mode needed. Current occupancy sets a steady dilution target with a 150 ppm margin; CO2 near the limit triggers a purge. It does not use the future schedule or tariff. This is an intentionally competent software baseline, with current-load feedforward and capacity trimming.

Open-loop optimization covers the whole operating day (96 steps in the full suite) at its beginning. The resulting schedule is stored and executed without replanning. Its later calls cannot replace the cached schedule. If the initial solve fails, a thermostat rollout on the initial forecast produces a frozen fallback schedule. It does not become a feedback controller after failure.

MPC solves a new optimization every 15 minutes from the observed simulated T and CO2. The default lookahead is six hours (24 steps), truncated at the end of the operating day. Only the first action is executed. Horizon length can be changed through the CLI. A failed MPC solve falls back to the thermostat for that interval.

The methods intentionally have different lookahead policies: a full day initially for open loop, six hours repeatedly for MPC. This measures a practical controller design comparison, not an isolated proof of the value of feedback. A 24-hour MPC sensitivity run is possible with `--horizon-hours 24`.

## MILP and infeasibility

Each interval chooses exactly one airflow mode using binary variables. The exact thermal and CO2 transitions for that mode are enforced by indicator inequalities. Relaxation constants are calculated from finite variable bounds, rather than a single arbitrary huge number. Temperature is bounded to -40..65 C and CO2 to 0..30000 ppm as a numerical model domain. These broad bounds are not comfort criteria.

Heating and cooling are continuous, have capacity limits, and cannot run simultaneously. Fan-off forces both to zero. Supply-temperature bounds are hard constraints. CO2 is scaled to thousands of ppm inside the optimization.

The objective is the predicted operating energy bill plus soft-comfort penalties: 100 EUR/(K h) for temperature below/above the band and 100 EUR/(1000 ppm h) for excess CO2. Penalties are numerical priorities, not social or health valuations. They are not a lexicographic guarantee of minimum violations. The MILP penalizes endpoint violations; evaluation integrates actual violations over the whole interval.

SciPy calls HiGHS with a 1% relative MIP gap and a configurable time limit. Status, solve time, and reported gap are recorded. Recorded solve time includes Python model construction, the solver, and any fallback rollout; it can exceed the solver's own budget. A thermostat's zero solve-call count means it uses no MILP, not that its control code takes zero CPU time. A finite incumbent from a time-limited solve is accepted only after explicit row, variable-bound, and integrality checks. An accepted incumbent is labeled `feasible_limit`, not optimal. No incumbent, invalid constraints, or a solver error causes an explicit fallback. A reported optimum is only within the requested solver tolerance.

Fallback counts are **solve events**. One open-loop fallback can affect an entire day; one MPC fallback affects one action. Compare these counts with the number of solve calls and the trace, not as equal-duration events.

## Shared actuator protection

Every requested action passes through the same physical limiter. It enforces coil capacity, non-simultaneous heating/cooling, and supply bounds for the actual current plant and held disturbance. If an airflow mode itself is infeasible, the unit switches off. Otherwise it saturates signed coil output. The operation is logged as a plant-side override if it changes the requested action.

This is an ideal simulation of actuator protection with the current physical conditions. It uses the plant parameters to protect supply throughout the interval. Those parameters and future realized disturbances are not passed into any controller. It is not a model-learning or forecast-update mechanism. Hardware protection can change a frozen open-loop command, as it would on real equipment; it cannot deliberately re-optimize comfort.

## Initial and terminal treatment

All methods start at 22 C and 600 ppm and run against identical realized inputs. There is no warm-up or hidden method-specific initial state.

After the scored operating day, all controllers are replaced by the same recovery thermostat for 16 hours. The zone is empty, the temperature target is 22 C, and the CO2 goal is at most 600 ppm. Recovery uses the same seasonal weather and prices, actual plant, and equipment limits. Its energy and cost are included in the primary totals. Operation and recovery comfort metrics are reported separately.

The optimizer has no artificial terminal equality or terminal value function. A common physical continuation makes end-of-day energy debt visible, but cannot guarantee identical final states under every capacity limit. The report therefore includes final T, final CO2, and a recovery-success flag (within 0.05 C of 22 C and at most 1 ppm above 600 ppm). **If that flag is false, a raw cost difference is not an equivalent-service saving.** This limitation also applies to custom severe conditions.

## Evaluation and checks

The executed actions are replayed with a separate `solve_ivp` implementation of the differential balances. That code does not call the optimizer/plant transition helper. Replay must match within 1e-6 C and 1e-4 ppm, and an independent audit checks coil capacities, mode flows, heating/cooling exclusivity, and both supply endpoints.

Violation area and time are integrated analytically from the monotone replayed trajectory, including threshold crossings. Temperature area is K h; CO2 area is ppm h. Maximum excursion and duration are separate metrics. Tiny boundary residuals below 1e-5 C and 0.01 ppm are treated as zero for the violation calculation. Stepwise peaks refer to the simulated 15-minute constant power, not sub-minute motor starts.

A successful replay checks internal consistency, not the accuracy of the building assumptions. Perfect current observations, known prices, no actuator delay, and a low-order plant are deliberate simplifications. There is no robustness or stability proof, field commissioning, occupancy estimation, or health/standards compliance claim.

## Deferred work

Measured weather/tariff ingestion with license provenance, noisy sensors, occupancy estimation, forecast ensembles, systematic horizon/penalty sensitivity, and a richer independent building model would strengthen external validity. None is represented as implemented here.
