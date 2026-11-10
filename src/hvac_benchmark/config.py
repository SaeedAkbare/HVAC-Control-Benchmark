"""Explicit engineering assumptions; all time quantities use hours."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    total: float  # kg/s supply flow
    fresh: float  # kg/s outdoor flow


MODES = (
    Mode("off", 0.0, 0.0),
    Mode("low", 0.45, 0.12),
    Mode("recirculate", 1.50, 0.12),
    Mode("medium", 0.90, 0.35),
    Mode("high", 1.50, 0.70),
    Mode("purge", 1.50, 1.50),
)


@dataclass(frozen=True)
class Model:
    volume: float = 960.0  # m3
    capacitance: float = 20.0  # kWh/K, effective air + fabric
    ua: float = 0.38  # kW/K
    density: float = 1.20  # kg/m3
    cp: float = 1.005  # kJ/(kg K), hence kg/s * cp -> kW/K
    heat_max: float = 18.0  # delivered coil kW
    cool_max: float = 16.0  # removed coil kW
    fan_max: float = 0.60  # electrical kW at 1.5 kg/s
    supply_min: float = 12.0  # degC when fan is on
    supply_max: float = 40.0
    heat_efficiency: float = 0.96
    cooling_cop: float = 3.40
    occupant_heat: float = 0.12  # sensible kW/person
    occupant_co2: float = 0.018  # m3/hour/person
    background_heat: float = 0.60  # constant sensible kW
    outside_co2: float = 420.0  # ppm
    gas_price: float = 0.075  # illustrative EUR/kWh fuel


@dataclass(frozen=True)
class Settings:
    dt: float = 0.25
    horizon_steps: int = 24
    time_limit: float = 2.0  # seconds per MILP
    mip_gap: float = 0.01
    temperature_penalty: float = 100.0  # EUR/(K h), soft objective only
    co2_penalty: float = 100.0  # EUR/(1000 ppm h), soft objective only
    recovery_steps: int = 24  # common six-hour continuation


@dataclass(frozen=True)
class State:
    temperature: float
    co2: float


@dataclass(frozen=True)
class Forcing:
    outdoor: float
    people: float
    price: float  # EUR/kWh electricity; assumed announced day ahead


@dataclass(frozen=True)
class Action:
    mode: int
    heat: float = 0.0
    cool: float = 0.0


INITIAL = State(22.0, 600.0)


def comfort(people: float) -> tuple[float, float, float]:
    """Requirements apply to an interval if any occupants are present."""
    return (20.0, 24.0, 1000.0) if people > 0 else (18.0, 27.0, 1400.0)
