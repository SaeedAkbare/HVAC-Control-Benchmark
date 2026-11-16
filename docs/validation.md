# Validation record

All execution recorded below took place on GitHub Actions.

## Portfolio cleanup verification — 15 November 2026

- Tested source: `aa92ace73802355ddc85d2a4b1e0c03f00cfb33e`.
- Successful Actions run `43769888254`; test job `132983204303`.
- **58 tests passed**, 14 upstream Matplotlib/Pyparsing deprecation warnings, 2.08 seconds.
- **12 benchmark smoke runs and three corrected-study smoke runs completed.**
- `pip check` found no broken requirements. The wheel built successfully; its MIT license expression and bundled license file were checked.
- The long research jobs were skipped. The corrected 34-run results below were preserved, not rerun for the portfolio cleanup.

The cleanup adds CLI checks for non-finite or excessive horizons and existing output files, package/license validation and clearer English documentation. It removes unused imports and makes long studies explicit manual workflow choices. It does not change the optimizer objective, hard constraints, physics, scenario inputs, reporting tolerances, horizons or archived numerical results.

## Corrected hard-constraint version — 15 November 2026

- Tested source: `1150f15ee7211b57f0d24907268616854276c8a2`.
- Successful Actions run `43710709106`.
- **46 tests passed**, 14 upstream Matplotlib/Pyparsing deprecation warnings, 1.76 seconds.
- **12 benchmark smoke runs and three corrected-study smoke runs completed.**
- **34 study runs and 654 optimization calls completed.**
- All 34 passed independent ODE replay and equipment audits and reached the common terminal target; no actuator override occurred.
- **22 runs had valid operating service, 20 were comparison eligible.** Physical audit/recovery success does not mean comfort succeeded.
- Calls: 332 valid within tolerance, 304 valid at the time limit, four timeouts without incumbent, two solver-proven infeasible, 12 invalid initial states.
- The 18 fallback events affected 398 operation steps. No numerical/invalid-incumbent failure was observed.
- [Permanent corrected evidence](../reports/corrected-2026-11-15/README.md) includes all metrics, all per-call records, protocol, manifest, provenance and selected executed PNG/SVG plots.
- Complete artifact (artifact `14160459146`, run `43710709106`) includes the trajectories and remaining figures.

The correction removes comfort slack variables and penalty costs from the optimizer, rather than merely changing reported scores. Hard limits apply to both ends of each held-input interval. The existing physics, scenario generator, comfort values, equipment capacities, horizons and common recovery goals were retained.

The disaggregated finite-mode formulation is tested against an independent exhaustive two-step mode/sign enumeration with dense LPs in both cold and hot conditions. Additional checks cover exact metered energy objectives, occupancy-bound transitions, explicit initial-state/capacity infeasibility, solver-status distinctions, rejected invalid incumbents, fallback duration and realized violations despite valid forecast plans. Existing exact/ODE agreement, meters, supply limits, causal forecasts, frozen open-loop scheduling, first-action MPC and severe recovery regressions remain.

The study is one fixed synthetic repeat. Nominal day-ahead plans at ten seconds passed hard feasibility but retained 42.68%/26.78% gaps. None of the full-day optimizer runs met the every-call 1% quality screen. Winter heat-loss mismatch caused genuine service failures, which remain reported. This validates an executable audited model and its stated tests, not field performance or universal economic superiority.

## Superseded soft-constraint evidence

The original implementation mistakenly used comfort slacks and weighted penalties. Its successful tests validated that different formulation, not the corrected cost-only hard-constraint problem.

- [10 November reference](../reports/reference-2026-11-10/README.md): 29 tests, 12 smoke runs and 84 full controller runs; source `322c2bcb1c45cdcfb76b3136fe75051b1e4f3595`.
- [11 November sensitivity archive](../reports/sensitivity-2026-11-11/README.md): 39 tests and 39 study runs; source `e7ccaae6e269694bd7a18683a2d115b7667b876a`.

Raw historical metrics and settings remain unchanged. Explanatory archive banners identify the superseded formulation; the later privacy cleanup removes personal hosting URLs from provenance and records those redactions explicitly. Source revisions, numeric evidence identifiers and scientific values are retained. Historical recovery corrections and earlier failed runs remain documented in that evidence and Git history. The current corrected suite retains the established 16-hour common continuation.

Documentation, archived data and figures may be committed after the tested source. Provenance identifies the executed revision; a documentation-only follow-up does not imply the numerical code was rerun.

## Current-file privacy review — 16 November 2026

Documentation and provenance received a further privacy-only edit after the tested cleanup revision. The reviewed tree contained 50 files, including three PNG figures unchanged from the executed evidence. The earlier historical text review covered 12 reachable main-line commits through archive revision `4ca956979aa0e5d0ba7c3a3f96175f8450cc3d39`; it does not cover every ref or unreachable object.

Known personal repository identifiers were removed from current documentation and provenance. Current source, tests, workflow, dependencies, scientific data, figures, license and third-party credits remain unchanged from the tested cleanup revision. Relative file links and the final text overlay were checked before publication.

**Personal commit metadata and earlier file versions remain in reachable Git history.** The connector cannot specify author/committer identities, so it cannot complete the requested history anonymization. [Privacy status](privacy.md) records the exact scope and remaining work. This documentation-only follow-up does not represent a new test or research run.
