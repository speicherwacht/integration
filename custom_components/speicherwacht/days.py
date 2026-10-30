"""Local days and periods from the cleaned hours.

Pure Python, no Home Assistant imports. Days are `[midnight, next midnight)`
in the local time zone, so they have 23, 24 or 25 hours; everything else
stays in UTC.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import StrEnum

from .model import Hour

HOUR = timedelta(hours=1)


class Period(StrEnum):
    TODAY = "today"
    MONTH = "month"
    YEAR = "year"
    TOTAL = "total"


def local_midnight(day: date, tz: tzinfo) -> datetime:
    """Midnight of `day` in `tz`, as UTC."""
    return datetime.combine(day, time(0), tzinfo=tz).astimezone(UTC)


def period_start(period: Period, now: datetime, tz: tzinfo) -> date | None:
    """First local day of the period containing `now` (None for TOTAL)."""
    today = now.astimezone(tz).date()
    match period:
        case Period.TODAY:
            return today
        case Period.MONTH:
            return today.replace(day=1)
        case Period.YEAR:
            return today.replace(month=1, day=1)
    return None


def soc_at(boundary: datetime, by_start: dict[datetime, Hour]) -> float | None:
    """State of charge at an hour boundary.

    The statistics only hold hourly means, each taken half an hour from the
    boundary: the mean of the hour before and the hour after is the best
    estimate. At the edge of the data (first hour, latest hour) the trend of
    the two nearest hours is extended by half an hour.
    """

    def soc(start: datetime) -> float | None:
        hour = by_start.get(start)
        return hour.soc if hour is not None else None

    before, after = soc(boundary - HOUR), soc(boundary)
    if before is not None and after is not None:
        return (before + after) / 2
    if after is not None:
        further = soc(boundary + HOUR)
        edge = after if further is None else after - (further - after) / 2
    elif before is not None:
        further = soc(boundary - 2 * HOUR)
        edge = before if further is None else before + (before - further) / 2
    else:
        return None
    return min(100.0, max(0.0, edge))


@dataclass(frozen=True, slots=True)
class Day:
    """Energy of one local day and the state of charge at its boundaries."""

    day: date
    charged: float
    discharged: float
    soc_start: float | None
    soc_end: float | None
    # Hours with both counters, SoC and no gap before, of hours the day has.
    complete_hours: int
    length_hours: int
    # Hours with a value of both counters: a day without any has no energy
    # figures at all (statistics of the state of charge often reach further
    # back than those of the counters).
    energy_hours: int = 0

    @property
    def complete(self) -> bool:
        return (
            self.complete_hours == self.length_hours
            and self.soc_start is not None
            and self.soc_end is not None
        )


def days(hours: Iterable[Hour], tz: tzinfo) -> list[Day]:
    """Group hours by local day, oldest first; only days with any hour."""
    by_start = {hour.start: hour for hour in hours}
    grouped: dict[date, list[Hour]] = {}
    for hour in by_start.values():
        grouped.setdefault(hour.start.astimezone(tz).date(), []).append(hour)
    result = []
    for day in sorted(grouped):
        start = local_midnight(day, tz)
        end = local_midnight(day + timedelta(days=1), tz)
        members = grouped[day]
        result.append(
            Day(
                day=day,
                charged=sum(h.charged or 0.0 for h in members),
                discharged=sum(h.discharged or 0.0 for h in members),
                soc_start=soc_at(start, by_start),
                soc_end=soc_at(end, by_start),
                complete_hours=sum(1 for h in members if h.complete),
                length_hours=round((end - start) / HOUR),
                energy_hours=sum(
                    1
                    for h in members
                    if h.charged is not None and h.discharged is not None
                ),
            )
        )
    return result
