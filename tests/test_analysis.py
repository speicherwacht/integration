"""Analysis against the simulator: efficiency, rest days, rest loss, capacity."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from custom_components.speicherwacht.analysis import (
    NO_DATA,
    SOC_ROSE_AT_REST,
    TOO_FEW_DISCHARGES,
    TOO_FEW_REST_HOURS,
    TOO_LITTLE_CHARGE,
    analyse,
    is_rest_day,
)
from custom_components.speicherwacht.days import Day, Period

from .sim import BERLIN, SUMMER_DAY, at, simulate

JUNE = date(2026, 6, 1)
# Shortly before midnight on the last simulated day: still in June.
HALF = timedelta(minutes=30)
END = at(date(2026, 6, 30), 23) + HALF


def test_month_efficiency_without_rest_loss_is_the_simulated_one() -> None:
    hours = simulate(JUNE, 30, rest_watts=0.0, soc=30.0)
    result = analyse(hours, 10.0, BERLIN, END)
    month = result.efficiency[Period.MONTH]
    assert month.ratio == pytest.approx(0.9, abs=0.005)
    assert month.operating_days == 30
    assert month.rest_days == 0


@pytest.mark.parametrize("start_soc", [10.0, 50.0, 90.0])
def test_correction_makes_the_start_level_irrelevant(start_soc: float) -> None:
    """Without the correction a week would swing with the state of charge."""
    hours = simulate(JUNE, 7, rest_watts=0.0, soc=start_soc)
    result = analyse(hours, 10.0, BERLIN, at(date(2026, 6, 7), 23) + HALF)
    assert result.efficiency[Period.MONTH].ratio == pytest.approx(0.9, abs=0.01)


def test_rest_loss_during_operation_lowers_the_efficiency() -> None:
    hours = simulate(JUNE, 30, rest_watts=20.0)
    result = analyse(hours, 10.0, BERLIN, END)
    month = result.efficiency[Period.MONTH]
    expected = 0.9 - 30 * 24 * 0.02 / month.charged
    assert month.ratio == pytest.approx(expected, abs=0.005)


def test_rest_loss_is_measured_in_quiet_hours() -> None:
    hours = simulate(JUNE, 30, rest_watts=20.0)
    result = analyse(hours, 10.0, BERLIN, END)
    assert result.rest.watts == pytest.approx(20.0, rel=0.05)
    assert result.rest.hours >= 24


def test_rest_days_stay_out_of_the_efficiency() -> None:
    def winter(day: date) -> dict[int, float]:
        return {} if date(2026, 6, 10) <= day < date(2026, 6, 20) else SUMMER_DAY

    hours = simulate(JUNE, 30, rest_watts=0.0, profile=winter)
    # A resting battery still loses some energy: only on the rest days.
    rest = {date(2026, 6, 10) + timedelta(days=i) for i in range(10)}
    hours = [
        replace(h, soc=h.soc - 0.2) if h.start.astimezone(BERLIN).date() in rest else h
        for h in hours
    ]
    result = analyse(hours, 10.0, BERLIN, END)
    month = result.efficiency[Period.MONTH]
    assert month.rest_days == 10
    assert month.operating_days == 20
    assert month.ratio == pytest.approx(0.9, abs=0.01)


def test_rest_day_rule() -> None:
    day = Day(JUNE, 0.4, 0.3, 50.0, 49.0, 24, 24, 24)
    assert is_rest_day(day, 10.0)
    assert not is_rest_day(replace(day, discharged=0.6), 10.0)


def test_little_charge_gives_no_efficiency() -> None:
    hours = simulate(JUNE, 1, rest_watts=0.0)
    hours = [replace(h, charged=(h.charged or 0) / 2) for h in hours]
    result = analyse(hours, 20.0, BERLIN, at(JUNE, 23) + HALF)
    assert result.efficiency[Period.MONTH].reason == TOO_LITTLE_CHARGE
    assert result.efficiency[Period.MONTH].ratio is None


def test_today_ends_at_the_latest_hour() -> None:
    hours = simulate(JUNE, 2, rest_watts=0.0)
    now = at(date(2026, 6, 2), 16)
    hours = [h for h in hours if h.start < now]
    today = analyse(hours, 10.0, BERLIN, now).efficiency[Period.TODAY]
    assert today.operating_days == 1
    assert today.ratio == pytest.approx(0.9, abs=0.05)


def test_days_without_counters_do_not_count() -> None:
    """The SoC statistics reach further back than the counters."""
    hours = simulate(JUNE, 10, rest_watts=0.0)
    early = at(date(2026, 6, 4), 0)
    hours = [
        replace(h, charged=None, discharged=None, read=False) if h.start < early else h
        for h in hours
    ]
    result = analyse(hours, 10.0, BERLIN, at(date(2026, 6, 10), 23) + HALF)
    assert result.first_day == date(2026, 6, 4)
    assert result.efficiency[Period.MONTH].rest_days == 0


def test_cycles_are_discharge_per_capacity() -> None:
    hours = simulate(JUNE, 10, rest_watts=0.0)
    result = analyse(hours, 10.0, BERLIN, at(date(2026, 6, 10), 23) + HALF)
    assert result.cycles_total == pytest.approx(result.discharged_total / 10.0)
    assert result.cycles_year == pytest.approx(result.cycles_total)


SUNNY_DAY = {**SUMMER_DAY, **dict.fromkeys(range(9, 15), 2.0)}


def test_capacity_estimate_from_full_to_empty() -> None:
    hours = simulate(JUNE, 30, rest_watts=0.0, profile=lambda _d: SUNNY_DAY)
    result = analyse(hours, 10.0, BERLIN, END)
    assert result.capacity.kwh == pytest.approx(10.0, rel=0.03)
    assert len(result.capacity.samples) == 10


def test_capacity_estimate_needs_full_discharges() -> None:
    """Charged to 86 % only: the battery's own SoC scale is not trusted."""
    hours = simulate(JUNE, 30, rest_watts=0.0)
    result = analyse(hours, 10.0, BERLIN, END)
    assert result.capacity.kwh is None
    assert result.capacity.reason == TOO_FEW_DISCHARGES


def test_capacity_estimate_follows_an_aged_battery() -> None:
    """A battery with 8 kWh left, configured with its data sheet's 10 kWh."""
    hours = simulate(JUNE, 30, rest_watts=0.0, capacity=8.0)
    result = analyse(hours, 10.0, BERLIN, END)
    assert result.capacity.kwh == pytest.approx(8.0, rel=0.03)


def test_without_data_everything_is_unknown() -> None:
    result = analyse([], 10.0, BERLIN, at(JUNE, 12))
    assert result.efficiency[Period.TOTAL].reason == NO_DATA
    assert result.rest.reason == TOO_FEW_REST_HOURS
    assert result.capacity.reason == TOO_FEW_DISCHARGES
    assert result.first_day is None


def test_counters_starting_mid_day_leave_that_day_out() -> None:
    """Fronius: the counters start with Modbus, the SoC reaches further back.

    The first day's change of charge would include energy the counters never
    saw (review 2026-10-30: 92 % instead of 90 % over a month).
    """
    hours = simulate(JUNE, 30, rest_watts=0.0)
    begin = at(JUNE, 15)
    hours = [
        replace(h, charged=None, discharged=None, read=False)
        if h.start < begin
        else (replace(h, charged=None) if h.start == begin else h)
        for h in hours
    ]
    result = analyse(hours, 10.0, BERLIN, END)
    month = result.efficiency[Period.MONTH]
    assert month.incomplete_days == 1
    assert month.operating_days == 29
    assert month.ratio == pytest.approx(0.9, abs=0.005)


def test_a_day_with_missing_readings_at_midnight_is_left_out() -> None:
    hours = simulate(JUNE, 10, rest_watts=0.0)
    gap = {at(date(2026, 6, 5), 23), at(date(2026, 6, 6), 0)}
    hours = [replace(h, read=False) if h.start in gap else h for h in hours]
    month = analyse(hours, 10.0, BERLIN, at(date(2026, 6, 10), 23) + HALF).efficiency[
        Period.MONTH
    ]
    assert month.incomplete_days == 2  # 5 June ends, 6 June starts without
    assert month.ratio == pytest.approx(0.9, abs=0.01)


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "Australia/Adelaide"])
def test_half_hour_time_zones_get_an_efficiency(zone: str) -> None:
    """Their midnight falls between two statistics hours (review M3)."""
    from zoneinfo import ZoneInfo

    hours = simulate(JUNE, 30, rest_watts=0.0)
    tz = ZoneInfo(zone)
    total = analyse(hours, 10.0, tz, END).efficiency[Period.TOTAL]
    assert total.ratio == pytest.approx(0.9, abs=0.01)


def test_soc_rising_at_rest_gives_no_negative_loss() -> None:
    """Charging past the counters (PV straight into the battery) or SoC
    drift: the rest loss is unknown, the computed value an attribute."""
    hours = simulate(JUNE, 30, rest_watts=-3.0)
    rest = analyse(hours, 10.0, BERLIN, END).rest
    assert rest.watts is None
    assert rest.reason == SOC_ROSE_AT_REST
    assert rest.raw_watts == pytest.approx(-3.0, rel=0.05)


def test_rest_loss_within_one_soc_step_is_zero() -> None:
    """A tiny rise over all rest hours can be rounding of the SoC: 0 W."""
    hours = simulate(JUNE, 30, rest_watts=-0.05)
    rest = analyse(hours, 10.0, BERLIN, END).rest
    assert rest.watts == 0.0
    assert rest.reason is None
    assert rest.raw_watts == pytest.approx(-0.05, rel=0.1)
