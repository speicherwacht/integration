"""Implausible hourly counter readings from the long-term statistics.

Pattern of a real meter (a source briefly reported Wh as kWh): hourly states
107 -> 109851.5 -> 110.131, Home Assistant's `change` then shows +109,744 kWh
and books the fall back as a new meter cycle (+110 kWh); on another channel
+661,683 kWh. Speicherwacht reads the states: the counter module rejects the
jump and takes the fall back for a restart. Their energy is unknown, so the
hours are left out of all figures and their day out of the efficiency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.speicherwacht.analysis import analyse
from custom_components.speicherwacht.counter import CounterEvent
from custom_components.speicherwacht.days import Period
from custom_components.speicherwacht.hours import SocRow, build, rejected_summary
from custom_components.speicherwacht.model import Hour
from custom_components.speicherwacht.report import report

from .sim import BERLIN, at, simulate

T0 = datetime(2026, 3, 10, 6, 0, tzinfo=UTC)
CAPACITY = 10.0
JUNE = date(2026, 6, 1)
END = at(date(2026, 6, 30), 23) + timedelta(minutes=30)


def h(n: int) -> datetime:
    return T0 + timedelta(hours=n)


@pytest.mark.parametrize("signal", ["charged", "discharged"])
def test_wh_reported_as_kwh_is_rejected(signal: str) -> None:
    glitchy = {h(0): 105.0, h(1): 107.0, h(2): 109851.5, h(3): 110.131, h(4): 111.0}
    steady = {h(n): 50.0 + n for n in range(5)}
    charged, discharged = (
        (glitchy, steady) if signal == "charged" else (steady, glitchy)
    )
    series = build(charged, discharged, {}, CAPACITY)
    values = [getattr(hour, signal) for hour in series.hours]
    assert values == [None, pytest.approx(2.0), None, None, pytest.approx(0.869)]
    assert [hour.rejected for hour in series.hours] == [
        False,
        False,
        True,
        True,
        False,
    ]
    assert [(i.hour, i.signal, i.event) for i in series.issues] == [
        (h(2), signal, CounterEvent.JUMP),
        (h(3), signal, CounterEvent.RESET),
    ]
    # The other counter of the rejected hours keeps its energy.
    other = "discharged" if signal == "charged" else "charged"
    assert getattr(series.hours[2], other) == pytest.approx(1.0)
    assert not series.hours[2].complete


def test_a_huge_jump_on_another_channel_is_rejected() -> None:
    discharged = {h(0): 80.0, h(1): 81.0, h(2): 81.0 + 661683.0, h(3): 82.5}
    series = build(dict.fromkeys(discharged, 10.0), discharged, {}, CAPACITY)
    assert [hour.discharged for hour in series.hours] == [
        None,
        pytest.approx(1.0),
        None,
        None,
    ]
    assert sum(hour.discharged or 0.0 for hour in series.hours) < 2


def test_a_large_but_plausible_hour_stays() -> None:
    """1.5 C for an hour is below the bound (2 C x 1.5 + 1 kWh)."""
    charged = {h(0): 100.0, h(1): 115.0, h(2): 116.0}
    series = build(charged, dict.fromkeys(charged, 50.0), {}, CAPACITY)
    assert [hour.charged for hour in series.hours] == [
        None,
        pytest.approx(15.0),
        pytest.approx(1.0),
    ]
    assert series.issues == []
    assert not any(hour.rejected for hour in series.hours)


def _states(hours: list[Hour], signal: str, start: float) -> dict[datetime, float]:
    states, value = {}, start
    for hour in hours:
        value += getattr(hour, signal) or 0.0
        states[hour.start] = value
    return states


def _series(glitch_signal: str | None) -> tuple[list[Hour], datetime]:
    """A simulated month as hourly counter states; one reading in Wh."""
    simulated = simulate(JUNE, 30, rest_watts=0.0)
    charged = _states(simulated, "charged", 107.0)
    discharged = _states(simulated, "discharged", 90.0)
    soc = {x.start: SocRow(x.soc, x.soc_min, x.soc_max) for x in simulated}
    local_hour = 10 if glitch_signal == "charged" else 20
    glitch = at(date(2026, 6, 15), local_hour)
    if glitch_signal == "charged":
        charged[glitch] *= 1000
    elif glitch_signal == "discharged":
        discharged[glitch] *= 1000
    return build(charged, discharged, soc, CAPACITY).hours, glitch


@pytest.mark.parametrize("signal", ["charged", "discharged"])
def test_efficiency_leaves_the_day_out(signal: str) -> None:
    clean = analyse(_series(None)[0], CAPACITY, BERLIN, END)
    hours, glitch = _series(signal)
    result = analyse(hours, CAPACITY, BERLIN, END)
    month, before = result.efficiency[Period.MONTH], clean.efficiency[Period.MONTH]
    assert month.implausible_days == 1
    assert month.operating_days == before.operating_days - 1
    assert before.implausible_days == 0
    # Without leaving the day out, the lost energy of two hours shifted the
    # month by about a percentage point.
    assert month.ratio == pytest.approx(before.ratio, abs=0.001)
    # Never the glitch itself in the energy or the full cycles.
    assert result.discharged_total <= clean.discharged_total
    assert result.cycles_total == pytest.approx(clean.cycles_total, abs=0.2)
    summary = rejected_summary(hours, BERLIN)
    assert summary == {
        "count": 2,
        "hours": [
            glitch.astimezone(BERLIN).isoformat(),
            (glitch + timedelta(hours=1)).astimezone(BERLIN).isoformat(),
        ],
    }


def test_report_names_the_hours() -> None:
    hours, glitch = _series("charged")
    start = at(JUNE, 0)
    figures = report(hours, CAPACITY, BERLIN, start, END, END)
    assert figures["hours_implausible"]["count"] == 2
    assert (
        figures["hours_implausible"]["hours"][0]
        == glitch.astimezone(BERLIN).isoformat()
    )
    assert figures["efficiency"]["implausible_days"] == 1
    clean = report(_series(None)[0], CAPACITY, BERLIN, start, END, END)
    assert clean["hours_implausible"] == {"count": 0, "hours": []}


def test_summary_lists_the_first_five() -> None:
    hours = [
        Hour(start=h(n), charged=None, discharged=None, soc=None, rejected=True)
        for n in range(7)
    ]
    summary = rejected_summary(hours, UTC)
    assert summary["count"] == 7
    assert summary["hours"] == [h(n).isoformat() for n in range(5)]
