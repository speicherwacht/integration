"""The action "report" against the simulator: same figures as the sensors."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from custom_components.speicherwacht.analysis import (
    NO_DATA,
    TOO_FEW_DISCHARGES,
    TOO_FEW_REST_HOURS,
    analyse,
)
from custom_components.speicherwacht.days import Period, local_midnight
from custom_components.speicherwacht.report import period_days, report

from .sim import BERLIN, SUMMER_DAY, at, simulate

JUNE = date(2026, 6, 1)
HALF = timedelta(minutes=30)
# Shortly before midnight on the last simulated day: still in June.
END = at(date(2026, 6, 30), 23) + HALF
NEW_YEAR = local_midnight(date(2026, 1, 1), BERLIN)
SUNNY_DAY = {**SUMMER_DAY, **dict.fromkeys(range(9, 15), 2.0)}


def test_default_period_gives_the_yearly_sensor_figures() -> None:
    """1 January until now: the figures of the yearly sensors."""
    hours = simulate(JUNE, 30, rest_watts=20.0, profile=lambda _d: SUNNY_DAY)
    now = at(date(2026, 6, 30), 16)
    hours = [h for h in hours if h.start < now]
    analysis = analyse(hours, 10.0, BERLIN, now)
    result = report(hours, 10.0, BERLIN, NEW_YEAR, now, now)
    year = analysis.efficiency[Period.YEAR]
    assert result["efficiency"]["percent"] == round(year.ratio * 100, 1)
    assert result["efficiency"]["operating_days"] == year.operating_days == 30
    assert result["full_cycles"] == round(analysis.cycles_year, 1)
    # The simulator's quiet hour before the first midnight is a day too.
    assert result["first_day"] == analysis.first_day.isoformat() == "2026-05-31"
    # Today counts up to the latest hour, as for the sensors.
    assert result["last_day"] == "2026-06-30"
    assert result["rest_loss"]["watts"] == round(analysis.rest.watts)
    assert result["capacity_estimate"]["kwh"] == round(analysis.capacity.kwh, 2)
    assert result["data_until"] == "2026-06-30T16:00:00+02:00"


def test_whole_days_only() -> None:
    hours = simulate(JUNE, 30, rest_watts=0.0)
    start = at(date(2026, 6, 10), 8)
    end = at(date(2026, 6, 20), 12)
    result = report(hours, 10.0, BERLIN, start, end, END)
    assert result["first_day"] == "2026-06-11"
    assert result["last_day"] == "2026-06-19"
    assert result["days"] == 9
    days = period_days(hours, BERLIN, start, end, END)
    assert result["charged_kwh"] == round(sum(d.charged for d in days), 2)
    assert result["efficiency"]["percent"] == pytest.approx(90.0, abs=0.5)


def test_a_past_period_leaves_today_out() -> None:
    hours = simulate(JUNE, 30, rest_watts=0.0)
    now = at(date(2026, 6, 30), 16)
    hours = [h for h in hours if h.start < now]
    end = local_midnight(date(2026, 6, 30), BERLIN)
    result = report(hours, 10.0, BERLIN, NEW_YEAR, end, now)
    assert result["last_day"] == "2026-06-29"
    assert result["efficiency"]["operating_days"] == 29


def test_months_of_the_period() -> None:
    hours = simulate(date(2026, 5, 20), 42, rest_watts=0.0)
    result = report(hours, 10.0, BERLIN, NEW_YEAR, END, END)
    months = {m["month"]: m for m in result["months"]}
    assert list(months) == ["2026-05", "2026-06"]
    assert months["2026-06"]["efficiency_operating_days"] == 30
    assert months["2026-06"]["efficiency_percent"] == pytest.approx(90.0, abs=0.5)
    assert months["2026-05"]["discharged_kwh"] + months["2026-06"][
        "discharged_kwh"
    ] == pytest.approx(result["discharged_kwh"], abs=0.02)
    assert result["full_cycles"] == round(result["discharged_kwh"] / 10.0, 1)


def test_rest_loss_and_capacity_over_the_period() -> None:
    hours = simulate(JUNE, 30, rest_watts=20.0, profile=lambda _d: SUNNY_DAY)
    result = report(hours, 10.0, BERLIN, NEW_YEAR, END, END)
    assert result["rest_loss"]["watts"] == pytest.approx(20.0, rel=0.05)
    assert result["capacity_estimate"]["kwh"] == pytest.approx(10.0, rel=0.03)
    assert result["capacity_estimate"]["share_of_data_sheet_percent"] == (
        pytest.approx(100.0, abs=3)
    )
    # A single day has too few rest hours and full discharges.
    start = local_midnight(date(2026, 6, 10), BERLIN)
    short = report(hours, 10.0, BERLIN, start, start + timedelta(days=1), END)
    assert short["days"] == 1
    assert short["rest_loss"]["reason"] == TOO_FEW_REST_HOURS
    assert short["capacity_estimate"]["reason"] == TOO_FEW_DISCHARGES


def test_a_period_without_data() -> None:
    hours = simulate(JUNE, 30, rest_watts=0.0)
    start = local_midnight(date(2025, 1, 1), BERLIN)
    result = report(hours, 10.0, BERLIN, start, NEW_YEAR, END)
    assert result["days"] == 0
    assert result["first_day"] is None
    assert result["data_until"] is None
    assert result["efficiency"]["percent"] is None
    assert result["efficiency"]["reason"] == NO_DATA
    assert result["months"] == []
    assert result["full_cycles"] == 0.0
