"""Signals, balance boundaries and the hourly record all calculations use.

Pure Python, no Home Assistant imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Signal(StrEnum):
    """What a source entity delivers."""

    CHARGED = "charged"  # energy into the battery, cumulative (kWh/Wh/MWh)
    DISCHARGED = "discharged"  # energy out of the battery, cumulative
    SOC = "soc"  # state of charge in %


REQUIRED = (Signal.CHARGED, Signal.DISCHARGED, Signal.SOC)


class Boundary(StrEnum):
    """Where the counters measure. Results of both are never mixed."""

    BATTERY = "battery"  # DC side of the battery (most inverter counters)
    SYSTEM = "system"  # AC side of the whole storage (e.g. a plug meter)


@dataclass(frozen=True, slots=True)
class Hour:
    """One hour of the long-term statistics, cleaned.

    `charged`/`discharged` are the increments booked by the counter module
    for this hour (kWh); None when the counter had no usable reading. `soc`
    is the mean state of charge (%), `soc_min`/`soc_max` its range; None
    without statistics. `gap` marks the first hour after missing readings:
    its energy may belong to earlier hours.
    """

    start: datetime
    charged: float | None
    discharged: float | None
    soc: float | None
    soc_min: float | None = None
    soc_max: float | None = None
    gap: bool = False
    read: bool = False

    @property
    def complete(self) -> bool:
        return (
            self.charged is not None
            and self.discharged is not None
            and self.soc is not None
            and not self.gap
        )
