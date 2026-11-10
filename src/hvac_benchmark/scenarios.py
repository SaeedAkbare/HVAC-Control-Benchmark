"""Deterministic surrogate days and a forecast interface with no future truth."""
from dataclasses import dataclass, replace
from math import cos, exp, pi
import numpy as np
from .config import Forcing, Model


@dataclass(frozen=True)
class Period:
    name: str
    mean: float
    amplitude: float
    seed: int
    error_sign: int


PERIODS = (
    Period("winter", 8.0, 4.0, 101, -1),
    Period("spring", 16.0, 5.0, 202, -1),
    Period("summer", 28.0, 6.0, 303, 1),
    Period("autumn", 13.0, 5.0, 404, 1),
)
# Reserved for any future tuning. Never included in evaluation suites.
DEVELOPMENT = Period("development", 19.0, 5.5, 11, 1)
CASES = ("nominal", "weather_mild", "weather_severe",
         "occupancy_mild", "occupancy_severe", "loss_mild", "loss_severe")


@dataclass(frozen=True)
class Scenario:
    name: str
    period: str
    case: str
    seed: int
    start_hour: float
    dt: float
    evaluation_steps: int
    plan: tuple[Forcing, ...]
    realized: tuple[Forcing, ...]
    plant: Model


def generate(period: Period, case: str, hours: float = 24.0,
             start_hour: float = 0.0, dt: float = 0.25) -> Scenario:
    if case not in CASES:
        raise ValueError(f"unknown case: {case}")
    if not 0 < hours <= 24 or not 0 <= start_hour < 24:
        raise ValueError("hours must be in (0, 24], start_hour in [0, 24)")
    if abs(hours / dt - round(hours / dt)) > 1e-8:
        raise ValueError("duration must be a whole number of steps")
    rng = np.random.default_rng(period.seed)
    # Smooth daily variation, not independent 15-minute noise.
    offset = float(rng.uniform(-0.7, 0.7))
    phase = float(rng.uniform(-0.35, 0.35))
    price_offset = float(rng.uniform(-0.008, 0.008))
    n = round(hours / dt)
    plan, realized = [], []
    severe = case.endswith("severe")
    for k in range(n + round(12 / dt)):
        hour = (start_hour + k * dt) % 24
        outdoor = (period.mean + offset
                   + period.amplitude * cos(2 * pi * (hour - 15 - phase) / 24)
                   + 0.6 * cos(4 * pi * (hour - 10) / 24))
        price = (0.15 + price_offset
                 + 0.08 * exp(-0.5 * ((hour - 8) / 1.6) ** 2)
                 + 0.14 * exp(-0.5 * ((hour - 19) / 2.0) ** 2))
        planned_people = 24.0 if 8 <= hour < 18 else 0.0
        people = planned_people
        actual_outdoor = outdoor
        if case.startswith("weather") and k < n:
            # One persistent event: rise 08-10, plateau 10-16, decay 16-18.
            envelope = max(0.0, min((hour - 8) / 2, 1.0, (18 - hour) / 2))
            actual_outdoor += period.error_sign * (6 if severe else 3) * envelope
        if case.startswith("occupancy"):
            arrival, count = (6, 40) if severe else (7, 30)
            people = float(count) if arrival <= hour < 18 else 0.0
        # Recovery has a common, empty-zone operating requirement.
        if k >= n:
            planned_people = people = 0.0
        plan.append(Forcing(outdoor, planned_people, price))
        realized.append(Forcing(actual_outdoor, people, price))
    multiplier = (1.50 if severe else 1.20) if case.startswith("loss") else 1.0
    return Scenario(
        f"{period.name}__{case}", period.name, case, period.seed,
        start_hour, dt, n, tuple(plan), tuple(realized),
        replace(Model(), ua=Model().ua * multiplier),
    )


def forecast(plan: tuple[Forcing, ...], now: int, length: int,
             observed: Forcing, start_hour: float, dt: float) -> tuple[Forcing, ...]:
    """Only announced plan + current observation enter this causal update.

    Weather residual decays with a four-hour time constant. Observed occupants
    persist until the known 18:00 departure; an unobserved early arrival is
    never anticipated. No realized future arrays or plant UA enter this API.
    """
    if length < 1 or now + length > len(plan):
        raise ValueError("forecast window outside plan")
    residual = observed.outdoor - plan[now].outdoor
    result = []
    for lead in range(length):
        k = now + lead
        hour = (start_hour + k * dt) % 24
        people = plan[k].people
        if observed.people > 0 and hour < 18 and (start_hour + k * dt) // 24 == (
                start_hour + now * dt) // 24:
            people = observed.people
        if lead == 0:
            people = observed.people
        result.append(Forcing(plan[k].outdoor + residual * exp(-lead * dt / 4.0),
                              people, plan[k].price))
    return tuple(result)


def suite(name: str) -> list[Scenario]:
    if name == "smoke":
        return [generate(p, c, hours=4, start_hour=6)
                for p in (PERIODS[0], PERIODS[2])
                for c in ("nominal", "occupancy_severe")]
    if name == "full":
        return [generate(p, c) for p in PERIODS for c in CASES]
    raise ValueError(f"unknown suite: {name}")
