"""A small battery simulator for the analysis tests.

Losses are booked on the charging side (the stored energy grows by
charge * efficiency, falls by the discharge), so energy taken out per 100 %
state of charge equals the capacity, and a rest loss drains the stored
energy. Hours are rows as the statistics deliver them: mean, min and max of
the state of charge, counters as increments.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.speicherwacht.days import local_midnight
from custom_components.speicherwacht.model import Hour

BERLIN = ZoneInfo("Europe/Berlin")
HOUR = timedelta(hours=1)

# kW per local hour of the day: + charge, - discharge.
SUMMER_DAY: dict[int, float] = {
    **dict.fromkeys(range(9, 15), 1.5),
    **dict.fromkeys([*range(18, 24), *range(0, 6)], -0.8),
}


def simulate(
    first: date,
    days: int,
    capacity: float = 10.0,
    efficiency: float = 0.9,
    rest_watts: float = 20.0,
    soc: float = 50.0,
    profile: Callable[[date], dict[int, float]] = lambda _day: SUMMER_DAY,
    low: float = 5.0,
    high: float = 95.0,
) -> list[Hour]:
    """Hours from local midnight of `first` for `days` days, plus one quiet
    hour before: the counters already ran, so the first day is covered."""
    hours = []
    midnight = local_midnight(first, BERLIN)
    start = midnight - HOUR
    end = local_midnight(first + timedelta(days=days), BERLIN)
    stored = soc / 100 * capacity
    while start < end:
        local = start.astimezone(BERLIN)
        power = profile(local.date()).get(local.hour, 0.0) if start >= midnight else 0.0
        before = stored
        charged = discharged = 0.0
        if power > 0:
            room = high / 100 * capacity - stored
            charged = max(0.0, min(power, room / efficiency))
            stored += charged * efficiency
        elif power < 0:
            available = stored - low / 100 * capacity
            discharged = max(0.0, min(-power, available))
            stored -= discharged
        stored -= rest_watts / 1000
        after = stored
        mean = (before + after) / 2 / capacity * 100
        hours.append(
            Hour(
                start=start,
                charged=charged,
                discharged=discharged,
                soc=mean,
                soc_min=min(before, after) / capacity * 100,
                soc_max=max(before, after) / capacity * 100,
                read=True,
            )
        )
        start += HOUR
    return hours


def at(day: date, hour: int) -> datetime:
    return local_midnight(day, BERLIN) + hour * HOUR
