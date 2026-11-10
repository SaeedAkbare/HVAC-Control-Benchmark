# Attribution and assistance

This repository is an AI-assisted educational implementation. Codex assisted with design, code, tests, documentation, and remote repository setup. The maintainer is responsible for reviewing the assumptions and any claims. The project does not establish a history of building deployment, measured savings, or independently authored prior professional work.

The thermal and CO2 equations are explicit first-principles well-mixed energy and mass balances, derived and explained in [the method](docs/method.md). No proprietary building data, company material, or field measurements are included. The source was written for this repository rather than copied from a third-party building simulator.

Libraries and upstream documentation used:

| Dependency | Role | Source and license |
|---|---|---|
| NumPy | Arrays and seeded surrogate generation | [NumPy](https://github.com/numpy/numpy), [BSD-3-Clause license](https://github.com/numpy/numpy/blob/v2.2.6/LICENSE.txt) |
| SciPy | MILP interface and independent ODE replay | [SciPy](https://github.com/scipy/scipy), [MILP API source/docstring](https://github.com/scipy/scipy/blob/v1.15.3/scipy/optimize/_milp.py), [BSD-3-Clause license](https://github.com/scipy/scipy/blob/v1.15.3/LICENSE.txt) |
| HiGHS | Solver called by SciPy | [HiGHS](https://github.com/ERGO-Code/HiGHS), [MIT license](https://github.com/ERGO-Code/HiGHS/blob/master/LICENSE.txt) |
| Matplotlib | Plots generated from executed traces | [Matplotlib](https://github.com/matplotlib/matplotlib), [license](https://github.com/matplotlib/matplotlib/blob/v3.10.3/LICENSE/LICENSE) |
| pytest | Regression checks | [pytest](https://github.com/pytest-dev/pytest), [MIT license](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| GitHub Actions | Remote tests and benchmark execution | [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [upload-artifact](https://github.com/actions/upload-artifact) |

Dependencies are installed, not vendored or modified here. Their upstream notices and license terms remain applicable. The repository license covers the code and surrogate data authored for this repository, not a relicensing of those dependencies.
