"""Health check of one storage: rules on the cleaned hours.

Pure Python, no Home Assistant imports. Rules, sources and own assumptions:
docs/GESUNDHEITSCHECK.md. Every check answers `problem` True/False, or None
with a `reason` when the data do not allow a judgement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
from itertools import pairwise
from typing import Any

from .analysis import capacity_estimate, efficiency, rest_loss
from .days import Day, days
from .model import Hour

# Efficiency dropped: the last 30 full days against the same days a year
# before, from a drop of 3 percentage points (own assumption: corrected
# monthly values of a real installation stay within about one point).
EFFICIENCY_WINDOW_DAYS = 30
EFFICIENCY_DROP_POINTS = 3.0
# Each side needs this many operating days and charged capacities.
EFFICIENCY_MIN_DAYS = 15
EFFICIENCY_MIN_CAPACITIES = 2.0

# Capacity low: below 80 % of the data sheet (end of life in the field
# study of Figgener et al. 2024), or 10 points less than a year before (field
# ageing 2–3 points a year; own assumption).
CAPACITY_END_OF_LIFE = 0.80
CAPACITY_DROP_POINTS = 10.0

# Rest loss high: above the highest standby of the HTW storage inspection
# 2026 (64 W), or at least +50 % and +10 W against the same 30 days a year
# before (own assumption, as Wärmewacht's standby check). Not against the 30
# days before: the rest loss follows the season (rest at low or high state
# of charge); at a real installation it rose from 18 to 30 W in May without
# any fault.
REST_LOSS_MAX_WATTS = 64.0
REST_LOSS_RISE = 1.5
REST_LOSS_RISE_WATTS = 10.0

# Counters and state of charge disagree within the last 24 complete hours
# (own assumptions): the SoC moves by 30 points while the counters move less
# than 5 % of the capacity, or the counters move half a capacity while the
# SoC stays within 2 points.
MISMATCH_HOURS = 24
MISMATCH_SOC_POINTS = 30.0
MISMATCH_QUIET_SHARE = 0.05
MISMATCH_BUSY_SHARE = 0.5
MISMATCH_STILL_POINTS = 2.0

YEAR = timedelta(days=365)

NO_PREVIOUS_YEAR = "no_previous_year"
TOO_FEW_DAYS = "too_few_days"
NO_ESTIMATE = "no_estimate"
NO_REST_LOSS = "no_rest_loss"
TOO_FEW_HOURS = "too_few_hours"


@dataclass(frozen=True, slots=True)
class Check:
    problem: bool | None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _window_days(
    hours: Sequence[Hour], tz: tzinfo, first: date, last: date
) -> list[Day]:
    return [d for d in days(hours, tz) if d.energy_hours and first <= d.day <= last]


def efficiency_drop(
    hours: Sequence[Hour], capacity: float, tz: tzinfo, now: datetime
) -> Check:
    """Efficiency of the last 30 full days against the same days a year ago."""
    yesterday = now.astimezone(tz).date() - timedelta(days=1)
    first = yesterday - timedelta(days=EFFICIENCY_WINDOW_DAYS - 1)
    try:
        prev_first = first.replace(year=first.year - 1)
        prev_last = yesterday.replace(year=yesterday.year - 1)
    except ValueError:  # 29 February
        prev_first = first - timedelta(days=365)
        prev_last = yesterday - timedelta(days=365)
    current = efficiency(
        _window_days(hours, tz, first, yesterday), capacity, EFFICIENCY_MIN_CAPACITIES
    )
    previous = efficiency(
        _window_days(hours, tz, prev_first, prev_last),
        capacity,
        EFFICIENCY_MIN_CAPACITIES,
    )
    details = {
        "current_percent": None if current.ratio is None else current.ratio * 100,
        "previous_year_percent": None
        if previous.ratio is None
        else previous.ratio * 100,
        "current_days": current.operating_days,
        "previous_year_days": previous.operating_days,
        "threshold_points": EFFICIENCY_DROP_POINTS,
    }
    if previous.ratio is None or previous.operating_days < EFFICIENCY_MIN_DAYS:
        return Check(None, NO_PREVIOUS_YEAR, details)
    if current.ratio is None or current.operating_days < EFFICIENCY_MIN_DAYS:
        return Check(None, TOO_FEW_DAYS, details)
    drop = (previous.ratio - current.ratio) * 100
    details["drop_points"] = drop
    return Check(drop >= EFFICIENCY_DROP_POINTS, None, details)


def capacity_low(hours: Sequence[Hour], capacity: float, now: datetime) -> Check:
    """Estimated capacity at end of life, or clearly below a year ago."""
    current = capacity_estimate(hours, capacity, now)
    year_ago = capacity_estimate(hours, capacity, now - YEAR)
    details: dict[str, Any] = {
        "estimate_kwh": current.kwh,
        "year_ago_kwh": year_ago.kwh,
        "data_sheet_kwh": capacity,
        "end_of_life_percent": CAPACITY_END_OF_LIFE * 100,
        "drop_threshold_points": CAPACITY_DROP_POINTS,
    }
    if current.kwh is None:
        return Check(None, NO_ESTIMATE, details)
    share = current.kwh / capacity * 100
    details["share_percent"] = share
    low = share < CAPACITY_END_OF_LIFE * 100
    if year_ago.kwh is not None:
        drop = (year_ago.kwh - current.kwh) / capacity * 100
        details["drop_points"] = drop
        low = low or drop >= CAPACITY_DROP_POINTS
    return Check(low, None, details)


def rest_loss_high(hours: Sequence[Hour], capacity: float, now: datetime) -> Check:
    """Rest loss of the last 30 days: very high, or clearly above the same
    days a year ago."""
    current = rest_loss(hours, capacity, now)
    before = rest_loss(hours, capacity, now - YEAR)
    details = {
        "watts": current.watts,
        "previous_year_watts": before.watts,
        "max_watts": REST_LOSS_MAX_WATTS,
    }
    if current.watts is None:
        return Check(None, NO_REST_LOSS, details)
    high = current.watts > REST_LOSS_MAX_WATTS
    if before.watts is not None and before.watts > 0:
        high = high or (
            current.watts >= before.watts * REST_LOSS_RISE
            and current.watts - before.watts >= REST_LOSS_RISE_WATTS
        )
    return Check(high, None, details)


def counter_soc_mismatch(hours: Sequence[Hour], capacity: float) -> Check:
    """Over the last 24 complete hours: SoC and counters tell different
    stories (a counter stuck, a SoC stuck, or a wrong mapping)."""
    complete = [h for h in hours if h.complete][-MISMATCH_HOURS:]
    if len(complete) < MISMATCH_HOURS:
        return Check(None, TOO_FEW_HOURS)
    socs = [h.soc for h in complete if h.soc is not None]
    soc_moved = sum(abs(b - a) for a, b in pairwise(socs))
    soc_range = max(socs) - min(socs)
    energy = sum((h.charged or 0.0) + (h.discharged or 0.0) for h in complete)
    details = {
        "soc_moved_points": soc_moved,
        "soc_range_points": soc_range,
        "throughput_kwh": energy,
    }
    counters_still = (
        soc_moved >= MISMATCH_SOC_POINTS and energy < MISMATCH_QUIET_SHARE * capacity
    )
    soc_still = (
        energy >= MISMATCH_BUSY_SHARE * capacity and soc_range < MISMATCH_STILL_POINTS
    )
    details["kind"] = (
        "counters_still" if counters_still else "soc_still" if soc_still else None
    )
    return Check(counters_still or soc_still, None, details)


@dataclass(frozen=True, slots=True)
class Health:
    efficiency_drop: Check
    capacity_low: Check
    rest_loss_high: Check
    mismatch: Check


def check(hours: Sequence[Hour], capacity: float, tz: tzinfo, now: datetime) -> Health:
    return Health(
        efficiency_drop=efficiency_drop(hours, capacity, tz, now),
        capacity_low=capacity_low(hours, capacity, now),
        rest_loss_high=rest_loss_high(hours, capacity, now),
        mismatch=counter_soc_mismatch(hours, capacity),
    )
