"""Health checks against the simulator: one period now, one a year before."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from custom_components.speicherwacht.health import (
    NO_ESTIMATE,
    NO_PREVIOUS_YEAR,
    TOO_FEW_HOURS,
    capacity_low,
    counter_soc_mismatch,
    efficiency_drop,
    rest_loss_high,
)

from .sim import BERLIN, SUMMER_DAY, at, simulate

LAST_YEAR = date(2025, 6, 1)
THIS_YEAR = date(2026, 6, 1)
# 30 June 2026, 23:30: the last 30 full days are 31 May … 29 June.
NOW = at(date(2026, 6, 30), 23) + timedelta(minutes=30)
SUNNY_DAY = {**SUMMER_DAY, **dict.fromkeys(range(9, 15), 2.0)}


def two_years(**this_year) -> list:
    """June 2025 with the defaults, June 2026 with the given changes."""
    before = simulate(LAST_YEAR, 30, rest_watts=10.0, profile=lambda _d: SUNNY_DAY)
    now = simulate(
        THIS_YEAR - timedelta(days=1),
        31,
        profile=lambda _d: SUNNY_DAY,
        **{"rest_watts": 10.0, **this_year},
    )
    return before + now


def test_efficiency_unchanged_is_no_problem() -> None:
    result = efficiency_drop(two_years(), 10.0, BERLIN, NOW)
    assert result.problem is False
    assert result.details["drop_points"] == pytest.approx(0, abs=0.5)


def test_efficiency_dropped_by_five_points() -> None:
    result = efficiency_drop(two_years(efficiency=0.85), 10.0, BERLIN, NOW)
    assert result.problem is True
    assert result.details["drop_points"] == pytest.approx(5, abs=0.7)


def test_efficiency_without_previous_year_is_unknown() -> None:
    hours = simulate(THIS_YEAR, 30, profile=lambda _d: SUNNY_DAY)
    result = efficiency_drop(hours, 10.0, BERLIN, NOW)
    assert result.problem is None
    assert result.reason == NO_PREVIOUS_YEAR


def test_capacity_fine() -> None:
    result = capacity_low(two_years(), 10.0, NOW)
    assert result.problem is False
    assert result.details["share_percent"] == pytest.approx(100, abs=3)


def test_capacity_below_end_of_life() -> None:
    result = capacity_low(two_years(capacity=7.5), 10.0, NOW)
    assert result.problem is True
    assert result.details["share_percent"] == pytest.approx(75, abs=3)


def test_capacity_dropped_against_a_year_ago() -> None:
    """8.8 kWh is above end of life, but 12 points less than a year before."""
    result = capacity_low(two_years(capacity=8.8), 10.0, NOW)
    assert result.problem is True
    assert result.details["drop_points"] == pytest.approx(12, abs=3)


def test_capacity_without_full_discharges_is_unknown() -> None:
    hours = simulate(THIS_YEAR, 30)  # never charged to full
    assert capacity_low(hours, 10.0, NOW).reason == NO_ESTIMATE


def test_rest_loss_risen_against_last_year() -> None:
    hours = two_years(rest_watts=25.0)  # 10 W a year before
    result = rest_loss_high(hours, 10.0, NOW)
    assert result.problem is True
    assert result.details["previous_year_watts"] == pytest.approx(10, rel=0.1)


def test_rest_loss_rising_within_the_season_is_no_alarm() -> None:
    """From 10 to 25 W against the 30 days before, no year to compare."""
    before = simulate(THIS_YEAR - timedelta(days=30), 30, rest_watts=10.0)
    after = simulate(THIS_YEAR, 30, rest_watts=25.0)
    hours = before + [h for h in after if h.start >= at(THIS_YEAR, 0)]
    result = rest_loss_high(hours, 10.0, NOW)
    assert result.problem is False
    assert result.details["previous_year_watts"] is None


def test_rest_loss_above_the_highest_lab_value() -> None:
    hours = simulate(THIS_YEAR, 30, rest_watts=80.0)
    assert rest_loss_high(hours, 10.0, NOW).problem is True


def test_rest_loss_steady_is_no_problem() -> None:
    hours = simulate(THIS_YEAR - timedelta(days=30), 60, rest_watts=12.0)
    assert rest_loss_high(hours, 10.0, NOW).problem is False


def test_counters_and_soc_agree() -> None:
    hours = simulate(THIS_YEAR, 3)
    assert counter_soc_mismatch(hours, 10.0).problem is False


def test_counters_standing_still_while_soc_moves() -> None:
    hours = [replace(h, charged=0.0, discharged=0.0) for h in simulate(THIS_YEAR, 3)]
    result = counter_soc_mismatch(hours, 10.0)
    assert result.problem is True
    assert result.details["kind"] == "counters_still"


def test_soc_standing_still_while_counters_move() -> None:
    hours = [replace(h, soc=50.0) for h in simulate(THIS_YEAR, 3)]
    result = counter_soc_mismatch(hours, 10.0)
    assert result.problem is True
    assert result.details["kind"] == "soc_still"


def test_mismatch_needs_a_day_of_hours() -> None:
    assert counter_soc_mismatch(simulate(THIS_YEAR, 0), 10.0).reason == TOO_FEW_HOURS
