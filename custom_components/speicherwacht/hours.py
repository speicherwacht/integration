"""Hourly rows of the long-term statistics → cleaned hours.

Pure Python, no Home Assistant imports. The counters are read by their
hourly state (meter reading at the end of the hour), not by Home Assistant's
`change`: with `total_increasing` a glitch to 0 and back counts the whole
meter reading again, with `total` and no `last_reset` (Huawei, Sungrow, Fox)
a step back becomes a negative change. The counter module handles both.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo

from .counter import Counter, CounterEvent
from .model import Hour

HOUR = timedelta(hours=1)
# A state row holds the reading at the end of its hour; dated just before
# the end, a day counter's last reading stays on its own day.
READING_OFFSET = HOUR - timedelta(seconds=1)
# Charge and discharge power above capacity × this (1/h) is a glitch. Home and
# balcony batteries charge at most at about 1 C; 2 C leaves margin (own
# assumption, see docs/ENTWICKLUNG.md).
MAX_C_RATE = 2.0


@dataclass(frozen=True, slots=True)
class SocRow:
    """Hourly statistics of the state of charge (%)."""

    mean: float
    low: float | None = None
    high: float | None = None


@dataclass
class CounterIssue:
    """A reading the counter module did not book (for diagnostics/repairs)."""

    hour: datetime
    signal: str
    event: CounterEvent


@dataclass
class Series:
    """Cleaned hours in time order plus what was rejected on the way."""

    hours: list[Hour] = field(default_factory=list)
    issues: list[CounterIssue] = field(default_factory=list)
    # First reading of the discharge counter (kWh): with the booked
    # increments it gives the lifetime discharge without the raw glitches.
    first_discharged: float | None = None


def _booked(
    states: Mapping[datetime, float],
    counter: Counter,
    signal: str,
    issues: list[CounterIssue],
) -> tuple[dict[datetime, float], set[datetime]]:
    """Increments per hour and the hours that follow missing rows."""
    booked: dict[datetime, float] = {}
    gaps: set[datetime] = set()
    previous: datetime | None = None
    # A day counter starting anew at midnight is no issue.
    unexpected = {CounterEvent.JUMP, CounterEvent.DIP}
    if counter.day_tz is None:
        unexpected.add(CounterEvent.RESET)
    for hour in sorted(states):
        update = counter.update(states[hour], hour + READING_OFFSET)
        if update.event in unexpected:
            issues.append(CounterIssue(hour, signal, update.event))
        if update.event is not CounterEvent.FIRST:
            booked[hour] = update.delta
        if previous is not None and hour - previous > HOUR:
            gaps.add(hour)
        previous = hour
    return booked, gaps


def build(
    charged: Mapping[datetime, float],
    discharged: Mapping[datetime, float],
    soc: Mapping[datetime, SocRow],
    capacity_kwh: float,
    day_tz: tzinfo | None = None,
) -> Series:
    """Combine the hourly counter states (kWh) and SoC rows (UTC hour starts).

    `day_tz` marks counters that start anew each day in that time zone.
    The first reading of a counter only sets its baseline; that hour has
    no energy for it.
    """
    series = Series()
    max_kw = capacity_kwh * MAX_C_RATE
    charge_counter = Counter(max_kw=max_kw, day_tz=day_tz)
    discharge_counter = Counter(max_kw=max_kw, day_tz=day_tz)
    into, into_gaps = _booked(charged, charge_counter, "charged", series.issues)
    out, out_gaps = _booked(discharged, discharge_counter, "discharged", series.issues)
    for hour in sorted(set(charged) | set(discharged) | set(soc)):
        row = soc.get(hour)
        series.hours.append(
            Hour(
                start=hour,
                charged=into.get(hour),
                discharged=out.get(hour),
                soc=row.mean if row else None,
                soc_min=row.low if row else None,
                soc_max=row.high if row else None,
                gap=hour in into_gaps or hour in out_gaps,
                read=hour in charged and hour in discharged,
            )
        )
    if discharged:
        series.first_discharged = discharged[min(discharged)]
    return series
