"""Figures of one storage from its cleaned hours.

Pure Python, no Home Assistant imports. Definitions, sources and own
assumptions: docs/ENTWICKLUNG.md, section 3.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, tzinfo
from statistics import median

from .days import Day, Period, days, period_start, soc_at
from .model import Hour

# A day on which charge and discharge each stay below this share of the
# capacity is a rest day (winter standby, emergency reserve, maintenance):
# its losses count as rest losses, not into the efficiency (own assumption).
REST_SHARE = 0.05
# Efficiency needs at least this much charged energy, in capacities: the
# state of charge correction is uncertain by a few percent of the capacity
# (own assumption).
MIN_CHARGE_CAPACITIES = {Period.TODAY: 0.5}
DEFAULT_MIN_CHARGE_CAPACITIES = 1.0
# Rest hours: charge plus discharge at most this share of the capacity per
# hour (trickle charging of the battery management counts as rest).
QUIET_SHARE = 0.005
# A run of rest hours shorter than this says nothing about losses.
MIN_REST_RUN_HOURS = 3
# Rest losses over this window, shown from this many rest hours on.
REST_WINDOW = timedelta(days=30)
MIN_REST_HOURS = 24
# A rest loss below 0 means the state of charge rose while resting: energy
# entered past the counters (PV straight into the battery) or the SoC drifts.
# Within one step of a state of charge in whole percent over all rest hours
# it is rounding and shows as 0 W (own assumption); beyond, it is unknown.
SOC_STEP_PERCENT = 1.0
# Capacity estimate: only discharges from full to empty count (as the field
# method of Figgener et al. 2024 between end of charge and end of discharge;
# the battery's own SoC is calculated by its management and would mostly
# repeat its own capacity model). Limits like the Marstek Capacity Monitor
# (≥ 95 → ≤ 15 %), a little wider for batteries that stop at 90 % (own
# assumption). The median of the latest ones within the window counts.
FULL_SOC = 90.0
EMPTY_SOC = 15.0
CAPACITY_SAMPLES = 10
CAPACITY_WINDOW = timedelta(days=90)
MIN_CAPACITY_SAMPLES = 3

# Why a figure is unknown.
NO_DATA = "no_data"
TOO_LITTLE_CHARGE = "too_little_charge"
NO_SOC = "no_soc"
TOO_FEW_REST_HOURS = "too_few_rest_hours"
SOC_ROSE_AT_REST = "soc_rose_at_rest"
TOO_FEW_DISCHARGES = "too_few_discharges"


def corrected_ratio(charged: float, discharged: float, stored: float) -> float:
    """Efficiency of a period whose stored energy changed by `stored` (kWh)."""
    return (discharged + stored) / charged


@dataclass(frozen=True, slots=True)
class Efficiency:
    """Efficiency of one period, rest days apart."""

    ratio: float | None
    charged: float  # operating days only
    discharged: float
    stored: float  # change of the stored energy over the operating days
    operating_days: int
    rest_days: int
    rest_loss: float  # kWh lost on rest days (charged − discharged − stored)
    days_without_soc: int = 0
    # Days the counters did not cover from midnight to midnight (first day
    # of the counters, missing readings): left out like days without SoC.
    incomplete_days: int = 0
    reason: str | None = None
    first_day: date | None = None


@dataclass(frozen=True, slots=True)
class RestLoss:
    """Mean power lost while the battery rests."""

    watts: float | None
    hours: float
    reason: str | None = None
    raw_watts: float | None = None  # as computed, also when below 0


@dataclass(frozen=True, slots=True)
class CapacityEstimate:
    """Energy discharged per 100 % state of charge, from large discharges."""

    kwh: float | None
    samples: list[float] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Analysis:
    efficiency: dict[Period, Efficiency]
    cycles_total: float
    cycles_year: float
    charged_total: float
    discharged_total: float
    rest: RestLoss
    capacity: CapacityEstimate
    first_day: date | None


def is_rest_day(day: Day, capacity: float) -> bool:
    limit = REST_SHARE * capacity
    return day.charged < limit and day.discharged < limit


def _stored(day: Day, capacity: float) -> float | None:
    if day.soc_start is None or day.soc_end is None:
        return None
    return (day.soc_end - day.soc_start) / 100 * capacity


def efficiency(
    selected: Sequence[Day], capacity: float, min_charge: float
) -> Efficiency:
    """Efficiency over the given days (with energy figures)."""
    charged = discharged = stored = rest_loss = 0.0
    operating = rest = without_soc = incomplete = 0
    for day in selected:
        if not (day.covered_start and day.covered_end):
            incomplete += 1
            continue
        day_stored = _stored(day, capacity)
        if day_stored is None:
            # No state of charge at a midnight: the day cannot be corrected
            # and is left out instead of spoiling the period.
            without_soc += 1
            continue
        if is_rest_day(day, capacity):
            rest += 1
            rest_loss += day.charged - day.discharged - day_stored
            continue
        operating += 1
        charged += day.charged
        discharged += day.discharged
        stored += day_stored
    first = selected[0].day if selected else None
    reason = None
    if not selected:
        reason = NO_DATA
    elif not operating and (without_soc or incomplete):
        reason = NO_SOC
    elif charged < min_charge * capacity:
        reason = TOO_LITTLE_CHARGE
    return Efficiency(
        ratio=None if reason else corrected_ratio(charged, discharged, stored),
        charged=charged,
        discharged=discharged,
        stored=stored,
        operating_days=operating,
        rest_days=rest,
        rest_loss=rest_loss,
        days_without_soc=without_soc,
        incomplete_days=incomplete,
        reason=reason,
        first_day=first,
    )


def _quiet(hour: Hour, capacity: float) -> bool:
    return (
        hour.complete
        and (hour.charged or 0.0) + (hour.discharged or 0.0) <= QUIET_SHARE * capacity
    )


def _runs(hours: Sequence[Hour], keep) -> list[list[Hour]]:
    """Maximal runs of consecutive hours for which `keep` holds."""
    runs: list[list[Hour]] = []
    current: list[Hour] = []
    for hour in hours:
        if keep(hour) and (
            not current or hour.start - current[-1].start == timedelta(hours=1)
        ):
            current.append(hour)
            continue
        if current:
            runs.append(current)
        current = [hour] if keep(hour) else []
    if current:
        runs.append(current)
    return runs


def rest_loss(hours: Sequence[Hour], capacity: float, now: datetime) -> RestLoss:
    """Mean loss while resting, from runs of quiet hours in the window.

    Between the means of the first and the last hour of a run lie
    len(run) - 1 hours; the energy of those hours (half of the first and
    the last) is booked against the drop of the state of charge.
    """
    since = now - REST_WINDOW
    recent = [h for h in hours if since <= h.start < now]
    lost = span = 0.0
    for run in _runs(recent, lambda h: _quiet(h, capacity)):
        if len(run) < MIN_REST_RUN_HOURS:
            continue
        net = sum((h.charged or 0.0) - (h.discharged or 0.0) for h in run)
        net -= ((run[0].charged or 0.0) - (run[0].discharged or 0.0)) / 2
        net -= ((run[-1].charged or 0.0) - (run[-1].discharged or 0.0)) / 2
        drop = ((run[0].soc or 0.0) - (run[-1].soc or 0.0)) / 100 * capacity
        lost += drop + net
        span += len(run) - 1
    if span < MIN_REST_HOURS:
        return RestLoss(None, span, TOO_FEW_REST_HOURS)
    watts = lost / span * 1000
    if watts >= 0:
        return RestLoss(watts, span, raw_watts=watts)
    if -watts <= SOC_STEP_PERCENT / 100 * capacity * 1000 / span:
        return RestLoss(0.0, span, raw_watts=watts)
    return RestLoss(None, span, SOC_ROSE_AT_REST, raw_watts=watts)


def _discharging(hour: Hour, capacity: float) -> bool:
    return (
        hour.complete
        and (hour.discharged or 0.0) > 0
        and (hour.charged or 0.0) <= QUIET_SHARE * capacity
    )


def capacity_estimate(
    hours: Sequence[Hour], capacity: float, now: datetime
) -> CapacityEstimate:
    """Median energy per 100 % SoC over the latest full-to-empty discharges."""
    since = now - CAPACITY_WINDOW
    recent = [h for h in hours if since <= h.start < now]
    samples = []
    for run in _runs(recent, lambda h: _discharging(h, capacity)):
        first, last = run[0], run[-1]
        high = first.soc_max if first.soc_max is not None else first.soc
        low = last.soc_min if last.soc_min is not None else last.soc
        if high is None or low is None or high < FULL_SOC or low > EMPTY_SOC:
            continue
        energy = sum(h.discharged or 0.0 for h in run)
        samples.append(energy / ((high - low) / 100))
    samples = samples[-CAPACITY_SAMPLES:]
    if len(samples) < MIN_CAPACITY_SAMPLES:
        return CapacityEstimate(None, samples, TOO_FEW_DISCHARGES)
    return CapacityEstimate(median(samples), samples)


def _close_today(day_list: list[Day], hours: Sequence[Hour], today: date) -> None:
    """The open day ends with the latest hour (and is covered up to it)."""
    if not day_list or day_list[-1].day != today or day_list[-1].soc_end is not None:
        return
    with_soc = [h for h in hours if h.soc is not None]
    if not with_soc:
        return
    end = with_soc[-1].start + timedelta(hours=1)
    last = soc_at(end, {h.start: h for h in with_soc[-2:]})
    latest = hours[-1] if hours else None
    day_list[-1] = replace(
        day_list[-1],
        soc_end=last,
        covered_end=latest is not None and latest.read,
    )


def analyse(
    hours: Sequence[Hour], capacity: float, tz: tzinfo, now: datetime
) -> Analysis:
    """All figures at `now` (UTC)."""
    day_list = [d for d in days(hours, tz) if d.energy_hours]
    today = now.astimezone(tz).date()
    _close_today(day_list, hours, today)
    result = {}
    for period in Period:
        first = period_start(period, now, tz)
        selected = [d for d in day_list if first is None or d.day >= first]
        minimum = MIN_CHARGE_CAPACITIES.get(period, DEFAULT_MIN_CHARGE_CAPACITIES)
        result[period] = efficiency(selected, capacity, minimum)
    year_start = period_start(Period.YEAR, now, tz)
    discharged_total = sum(d.discharged for d in day_list)
    discharged_year = sum(
        d.discharged for d in day_list if year_start and d.day >= year_start
    )
    return Analysis(
        efficiency=result,
        cycles_total=discharged_total / capacity,
        cycles_year=discharged_year / capacity,
        charged_total=sum(d.charged for d in day_list),
        discharged_total=discharged_total,
        rest=rest_loss(hours, capacity, now),
        capacity=capacity_estimate(hours, capacity, now),
        first_day=day_list[0].day if day_list else None,
    )
