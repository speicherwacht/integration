"""Local days: 23/25-hour days, state of charge at midnight, periods."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.speicherwacht.days import (
    Period,
    days,
    local_midnight,
    period_start,
    soc_at,
)
from custom_components.speicherwacht.model import Hour

BERLIN = ZoneInfo("Europe/Berlin")
HOUR = timedelta(hours=1)


def hours_of(day: date, soc: float = 50.0, charged: float = 0.1) -> list[Hour]:
    start = local_midnight(day, BERLIN)
    end = local_midnight(day + timedelta(days=1), BERLIN)
    result = []
    while start < end:
        result.append(Hour(start, charged, 0.05, soc))
        start += HOUR
    return result


@pytest.mark.parametrize(
    ("day", "length"),
    [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 6, 1), 24)],
)
def test_day_length_follows_the_clock_change(day: date, length: int) -> None:
    (result,) = days(hours_of(day), BERLIN)
    assert result.length_hours == length
    assert result.complete_hours == length
    assert result.charged == pytest.approx(0.1 * length)


def test_soc_at_midnight_is_the_mean_of_the_neighbouring_hours() -> None:
    boundary = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)  # midnight in Berlin
    by_start = {
        boundary - HOUR: Hour(boundary - HOUR, 0, 0.4, 30.0),
        boundary: Hour(boundary, 0, 0.4, 26.0),
    }
    assert soc_at(boundary, by_start) == pytest.approx(28.0)
    del by_start[boundary]
    assert soc_at(boundary, by_start) == pytest.approx(30.0)
    assert soc_at(boundary, {}) is None


def test_days_carry_the_soc_of_both_midnights() -> None:
    first = hours_of(date(2026, 6, 1), soc=40.0)
    second = hours_of(date(2026, 6, 2), soc=60.0)
    one, two = days(first + second, BERLIN)
    assert one.soc_start == pytest.approx(40.0)  # no hour before: own first
    assert one.soc_end == pytest.approx(50.0)
    assert two.soc_start == pytest.approx(50.0)
    assert one.complete and two.complete


def test_a_missing_hour_makes_the_day_incomplete() -> None:
    hours = hours_of(date(2026, 6, 1))
    del hours[5]
    (result,) = days(hours, BERLIN)
    assert result.complete_hours == 23
    assert not result.complete


def test_period_start_is_local() -> None:
    # 23:30 UTC on 31 May is already 1 June in Berlin.
    now = datetime(2026, 5, 31, 23, 30, tzinfo=UTC)
    assert period_start(Period.TODAY, now, BERLIN) == date(2026, 6, 1)
    assert period_start(Period.MONTH, now, BERLIN) == date(2026, 6, 1)
    assert period_start(Period.YEAR, now, BERLIN) == date(2026, 1, 1)
    assert period_start(Period.TOTAL, now, BERLIN) is None


def test_soc_between_hour_middles_for_half_hour_offsets() -> None:
    """Midnight in Kolkata is 18:30 UTC, the middle of the 18:00 hour."""
    h18 = datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    by_start = {h18: Hour(h18, 0, 0, 40.0), h18 + HOUR: Hour(h18 + HOUR, 0, 0, 44.0)}
    # Middles at 18:30 and 19:30; in between linear.
    assert soc_at(datetime(2026, 6, 1, 18, 30, tzinfo=UTC), by_start) == pytest.approx(
        40.0
    )
    assert soc_at(datetime(2026, 6, 1, 19, 0, tzinfo=UTC), by_start) == pytest.approx(
        42.0
    )
    assert soc_at(datetime(2026, 6, 1, 19, 15, tzinfo=UTC), by_start) == pytest.approx(
        43.0
    )
