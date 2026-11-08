"""Figures of the action "report" for any period. Pure Python, no HA imports.

The same functions as the sensors (analysis.py) on the cleaned hours of the
long-term statistics, only over another span:

- Efficiency, energy and full cycles over whole local days: a day counts if
  it begins at or after `start` and ends at or before `end`. The current day
  counts up to the latest hour when the period reaches `now`, as for the
  sensors; so the default period (1 January until now) gives the yearly
  sensors' figures.
- Rest loss and capacity estimate over the hours of [start, end), with the
  thresholds of the sensors (capacity: the latest discharges of the period).
- Hours of [start, end) with a rejected counter reading (`hours_implausible`):
  left out of all figures, their days out of the efficiency.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, tzinfo
from typing import Any

from .analysis import (
    DEFAULT_MIN_CHARGE_CAPACITIES,
    Efficiency,
    capacity_estimate,
    efficiency,
    energy_days,
    rest_loss,
)
from .days import Day, local_midnight
from .hours import rejected_summary
from .model import Hour

HOUR = timedelta(hours=1)


def _kwh(value: float) -> float:
    return round(value, 2)


def _percent(ratio: float | None) -> float | None:
    return None if ratio is None else round(ratio * 100, 1)


def period_days(
    hours: Sequence[Hour], tz: tzinfo, start: datetime, end: datetime, now: datetime
) -> list[Day]:
    """The whole local days of [start, end), today up to the latest hour."""
    today = now.astimezone(tz).date()
    return [
        day
        for day in energy_days(hours, tz, now)
        if local_midnight(day.day, tz) >= start
        and (
            local_midnight(day.day + timedelta(days=1), tz) <= end
            or (day.day == today and end >= now)
        )
    ]


def efficiency_figures(result: Efficiency) -> dict[str, Any]:
    """An efficiency as the report shows it (names as the sensor attributes)."""
    return {
        "percent": _percent(result.ratio),
        "charged_kwh": _kwh(result.charged),
        "discharged_kwh": _kwh(result.discharged),
        "stored_change_kwh": _kwh(result.stored),
        "operating_days": result.operating_days,
        "rest_days": result.rest_days,
        "rest_loss_kwh": _kwh(result.rest_loss),
        "days_without_soc": result.days_without_soc,
        "incomplete_days": result.incomplete_days,
        "implausible_days": result.implausible_days,
        "reason": result.reason,
    }


def report(
    hours: Sequence[Hour],
    capacity: float,
    tz: tzinfo,
    start: datetime,
    end: datetime,
    now: datetime,
) -> dict[str, Any]:
    """All figures of [start, end) at `now` (all UTC)."""
    chosen = period_days(hours, tz, start, end, now)
    minimum = DEFAULT_MIN_CHARGE_CAPACITIES
    charged = sum(d.charged for d in chosen)
    discharged = sum(d.discharged for d in chosen)
    months: dict[str, list[Day]] = {}
    for day in chosen:
        months.setdefault(day.day.strftime("%Y-%m"), []).append(day)
    until = min(end, now)
    rest = rest_loss(hours, capacity, until, since=start)
    estimate = capacity_estimate(hours, capacity, until, since=start)
    within = [h for h in hours if start <= h.start < until]
    latest = [h.start for h in within if h.read]
    return {
        "first_day": chosen[0].day.isoformat() if chosen else None,
        "last_day": chosen[-1].day.isoformat() if chosen else None,
        "days": len(chosen),
        "data_until": (max(latest) + HOUR).astimezone(tz).isoformat()
        if latest
        else None,
        "charged_kwh": _kwh(charged),
        "discharged_kwh": _kwh(discharged),
        "full_cycles": round(discharged / capacity, 1),
        "efficiency": efficiency_figures(efficiency(chosen, capacity, minimum)),
        "rest_loss": {
            "watts": None if rest.watts is None else round(rest.watts),
            "rest_hours": round(rest.hours),
            "raw_watts": None if rest.raw_watts is None else round(rest.raw_watts, 1),
            "reason": rest.reason,
        },
        "capacity_estimate": {
            "kwh": None if estimate.kwh is None else _kwh(estimate.kwh),
            "share_of_data_sheet_percent": None
            if estimate.kwh is None
            else round(estimate.kwh / capacity * 100, 1),
            "samples": len(estimate.samples),
            "reason": estimate.reason,
        },
        "hours_implausible": rejected_summary(within, tz),
        "months": [
            {
                "month": month,
                "charged_kwh": _kwh(sum(d.charged for d in month_days)),
                "discharged_kwh": _kwh(sum(d.discharged for d in month_days)),
                "full_cycles": round(
                    sum(d.discharged for d in month_days) / capacity, 1
                ),
                **{
                    f"efficiency_{key}": value
                    for key, value in efficiency_figures(
                        efficiency(month_days, capacity, minimum)
                    ).items()
                    if key in ("percent", "operating_days", "rest_days", "reason")
                },
            }
            for month, month_days in months.items()
        ],
    }
