"""Hourly statistics → cleaned hours: glitches, resets, gaps, day counters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.speicherwacht.counter import CounterEvent
from custom_components.speicherwacht.hours import SocRow, build

T0 = datetime(2026, 3, 10, 6, 0, tzinfo=UTC)
CAPACITY = 10.0


def h(n: int) -> datetime:
    return T0 + timedelta(hours=n)


def soc(*values: float) -> dict[datetime, SocRow]:
    return {h(i): SocRow(v, v - 1, v + 1) for i, v in enumerate(values)}


def test_first_reading_is_only_the_baseline() -> None:
    series = build(
        {h(0): 100.0, h(1): 102.0},
        {h(0): 90.0, h(1): 90.0},
        soc(20, 40),
        CAPACITY,
    )
    first, second = series.hours
    assert first.charged is None and first.discharged is None
    assert first.soc == 20 and first.soc_min == 19 and first.soc_max == 21
    assert second.charged == pytest.approx(2.0)
    assert second.discharged == 0
    assert second.complete
    assert not first.complete


def test_glitch_to_zero_and_back_books_nothing() -> None:
    """total_increasing: Home Assistant would count the meter reading again."""
    charged = {h(0): 2800.0, h(1): 2801.0, h(2): 0.0, h(3): 2802.0, h(4): 2803.5}
    series = build(charged, dict.fromkeys(charged, 50.0), {}, CAPACITY)
    booked = [hour.charged for hour in series.hours]
    assert booked == [None, pytest.approx(1.0), 0, 0, pytest.approx(1.5)]
    events = [(i.hour, i.event) for i in series.issues if i.signal == "charged"]
    assert events == [(h(2), CounterEvent.RESET), (h(3), CounterEvent.JUMP)]


def test_step_back_without_reset_is_held() -> None:
    """total without last_reset: a small step back must not be booked twice."""
    discharged = {h(0): 500.0, h(1): 499.9, h(2): 500.5}
    series = build(dict.fromkeys(discharged, 1.0), discharged, {}, CAPACITY)
    assert [hour.discharged for hour in series.hours] == [
        None,
        0,
        pytest.approx(0.5),
    ]
    assert series.issues[0].event is CounterEvent.DIP


def test_missing_rows_mark_a_gap() -> None:
    charged = {h(0): 10.0, h(1): 11.0, h(5): 15.0}
    series = build(charged, dict(charged), {}, CAPACITY)
    by_hour = {hour.start: hour for hour in series.hours}
    assert by_hour[h(5)].gap
    assert by_hour[h(5)].charged == pytest.approx(4.0)
    assert not by_hour[h(1)].gap


def test_soc_without_counters_keeps_the_hour() -> None:
    series = build({}, {}, soc(55), CAPACITY)
    assert len(series.hours) == 1
    assert series.hours[0].charged is None
    assert series.hours[0].soc == 55


def test_day_counter_starts_anew_at_local_midnight() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    # Rows of the hours 22, 23 and 0 o'clock local (UTC+1): the reading at
    # the end of 23–24 o'clock still belongs to the old day.
    late = datetime(2026, 3, 10, 21, 0, tzinfo=UTC)
    charged = {
        late - timedelta(hours=1): 7.0,
        late: 8.0,
        late + timedelta(hours=1): 9.0,
        late + timedelta(hours=2): 0.5,
    }
    series = build(charged, dict.fromkeys(charged, 0.0), {}, CAPACITY, berlin)
    assert [hour.charged for hour in series.hours] == [
        None,
        pytest.approx(1.0),
        pytest.approx(1.0),
        pytest.approx(0.5),
    ]
    assert series.issues == []
