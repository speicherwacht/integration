#!/usr/bin/env python3
"""Build the data of the demo (docs/demo/): made-up batteries, real logic.

Usage (from the repo root):
    uv run tools/make_demo.py

Everything here is invented: four batteries (no real product, no real
installation), their weather, household loads, losses and ageing. A small
simulator turns them into what Home Assistant's long-term statistics would
hold (hourly counter states, mean/min/max of the state of charge); the
integration's own code takes it from there, as in Home Assistant:
`hours.build` → `analysis.analyse` → `health.check`, and `report.report` for
the action "Bericht".

What lives in Home Assistant-dependent modules is rebuilt below with the same
rules: sensor values and attributes (sensor.py: rounding, lifetime discharge
from the first counter reading, warranty share), problem sensor attributes
(binary_sensor.py), the action's wrapper (services.py: start, end, boundary,
capacity) and entity IDs (slug of device and entity name).
"""

from __future__ import annotations

import json
import math
import random
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.speicherwacht.analysis import Analysis, analyse  # noqa: E402
from custom_components.speicherwacht.const import VERSION  # noqa: E402
from custom_components.speicherwacht.days import Period, local_midnight  # noqa: E402
from custom_components.speicherwacht.health import Check, check  # noqa: E402
from custom_components.speicherwacht.hours import Series, SocRow, build  # noqa: E402
from custom_components.speicherwacht.report import report  # noqa: E402

OUT = ROOT / "docs" / "demo" / "data"
TRANSLATIONS = ROOT / "custom_components" / "speicherwacht" / "translations"
BERLIN = ZoneInfo("Europe/Berlin")
HOUR = timedelta(hours=1)
# The demo moment: a sunny Wednesday in autumn, early evening; the statistics
# hold the hours up to 18:00 (Home Assistant compiles an hour a few minutes
# after its end).
NOW = datetime(2026, 10, 28, 18, 30, tzinfo=BERLIN)


# ---- The made-up batteries ----------------------------------------------------------


def _linear(start: date, end: date, before: float, after: float) -> Callable[[date], float]:  # fmt: skip
    """`before` until `start`, then linearly to `after` at `end`."""

    def value(day: date) -> float:
        if day <= start:
            return before
        if day >= end:
            return after
        share = (day - start).days / (end - start).days
        return before + (after - before) * share

    return value


def _const(value: float) -> Callable[[date], float]:
    return lambda _day: value


@dataclass(frozen=True)
class Battery:
    key: str
    name: str  # device name in Home Assistant
    area: dict[str, str]
    capacity: float  # usable capacity from the data sheet (configured), kWh
    boundary: str  # "battery" (DC) or "system" (AC)
    first: datetime  # first hour of the statistics (local)
    lifetime: tuple[float, float]  # counter readings then: charged, discharged (kWh)
    actual: Callable[[date], float]  # real usable capacity, kWh
    eta_in: Callable[[date], float]  # share of the charge that is stored
    eta_out: float  # share of the stored energy that leaves the counter
    rest_watts: Callable[[date], float]  # battery management, always on
    surplus: tuple[float, float]  # PV surplus kWh/day: mean, seasonal swing
    charge_kw: float
    load: Callable[[float], float]  # discharge demand kW by local hour
    floor: float  # % state of charge where discharging stops
    seed: int
    warranty_mwh: float | None = None


def _bump(hour: float, centre: float, width: float) -> float:
    return math.exp(-((hour - centre) ** 2) / width)


def house_load(hour: float) -> float:
    """A family home with a heat pump: base load, morning and evening peak."""
    return 0.42 + 0.3 * _bump(hour, 7.0, 1.5) + 0.85 * _bump(hour, 19.5, 3.5)


def balcony_load(_hour: float) -> float:
    """A balcony storage feeding a constant 200 W outside the sunny hours."""
    return 0.2


BATTERIES = [
    Battery(
        key="healthy",
        name="Heimspeicher",
        area={"de": "Keller", "en": "Basement"},
        capacity=10.0,
        boundary="battery",
        first=datetime(2025, 4, 14, 10, tzinfo=BERLIN),
        lifetime=(1584.211, 1497.836),
        actual=_linear(date(2025, 4, 14), date(2026, 10, 28), 9.9, 9.68),
        eta_in=_const(0.991),
        eta_out=0.992,
        rest_watts=_const(9.0),
        surplus=(9.5, 8.0),
        charge_kw=5.0,
        load=house_load,
        floor=5.0,
        seed=5021,  # RAL 5021, the brand colour
        warranty_mwh=30.0,
    ),
    Battery(
        key="ageing",
        name="Hausspeicher",
        area={"de": "Hauswirtschaftsraum", "en": "Utility room"},
        capacity=8.0,
        boundary="battery",
        first=datetime(2024, 10, 15, 0, tzinfo=BERLIN),
        lifetime=(10612.402, 9847.119),
        actual=_linear(date(2024, 10, 15), date(2026, 10, 28), 7.02, 6.18),
        eta_in=_linear(date(2025, 10, 31), date(2026, 10, 28), 0.975, 0.94),
        eta_out=0.986,
        rest_watts=_linear(date(2025, 10, 31), date(2026, 10, 28), 14.0, 18.0),
        surplus=(8.0, 6.5),
        charge_kw=4.0,
        load=house_load,
        floor=7.0,
        seed=7043,
        warranty_mwh=20.0,
    ),
    Battery(
        key="balcony",
        name="Balkonspeicher",
        area={"de": "Balkon", "en": "Balcony"},
        capacity=2.0,
        boundary="system",
        first=datetime(2026, 4, 18, 15, tzinfo=BERLIN),
        lifetime=(0.412, 0.233),
        actual=_const(2.04),
        eta_in=_const(0.972),
        eta_out=0.966,
        rest_watts=_const(6.5),
        surplus=(1.9, 1.3),
        charge_kw=0.8,
        load=balcony_load,
        floor=10.0,
        seed=6033,
    ),
    Battery(
        key="new",
        name="Neuer Speicher",
        area={"de": "Garage", "en": "Garage"},
        capacity=12.0,
        boundary="battery",
        first=datetime(2026, 10, 7, 14, tzinfo=BERLIN),
        lifetime=(1.106, 0.587),
        actual=_const(12.3),
        eta_in=_const(0.986),
        eta_out=0.985,
        rest_watts=_const(11.0),
        surplus=(11.0, 9.0),
        charge_kw=6.0,
        load=lambda hour: 1.15 * house_load(hour),
        floor=5.0,
        seed=2026,
    ),
]


# ---- Simulator: what the long-term statistics would hold ---------------------------------


def _summer(day: date) -> float:
    """1 at midsummer, -1 at midwinter."""
    return math.cos(2 * math.pi * (day.timetuple().tm_yday - 172) / 365)


def day_plan(battery: Battery, day: date, weather: float, rng: random.Random) -> dict[int, float]:  # fmt: skip
    """kW per local hour: + charge (PV surplus), - discharge demand."""
    summer = _summer(day)
    offset = datetime(day.year, day.month, day.day, 12, tzinfo=BERLIN).utcoffset()
    noon = 11.3 + (offset or timedelta()).total_seconds() / 3600
    length = 12.2 + 4.4 * summer
    first, last = noon - length / 2 + 2.0, noon + length / 2 - 2.0
    surplus = max(0.0, battery.surplus[0] + battery.surplus[1] * summer) * weather
    weights = {
        h: math.sin(math.pi * (h + 0.5 - first) / (last - first))
        for h in range(24)
        if first < h + 0.5 < last
    }
    total = sum(weights.values()) or 1.0
    usage = rng.uniform(0.75, 1.3) * (1 + 0.25 * max(0.0, -summer))
    plan = {}
    for hour in range(24):
        if hour in weights:
            plan[hour] = min(battery.charge_kw, surplus * weights[hour] / total)
        else:
            plan[hour] = -battery.load(hour + 0.5) * usage * rng.uniform(0.85, 1.15)
    return plan


@dataclass
class Statistics:
    charged: dict[datetime, float]
    discharged: dict[datetime, float]
    soc: dict[datetime, SocRow]
    soc_now: float


def simulate(battery: Battery) -> Statistics:
    """Hourly rows from the first hour until the hour before NOW's hour.

    Losses as in tests/sim.py, split: the charge counter sees the energy
    before `eta_in`, the discharge counter after `eta_out`; the battery
    management drains `rest_watts` all the time. Below the floor the inverter
    tops the battery up from the grid now and then (as most do in winter).
    """
    rng = random.Random(battery.seed)
    drift = random.Random(-battery.seed)
    bms = 1.0
    charged_states: dict[datetime, float] = {}
    discharged_states: dict[datetime, float] = {}
    soc_rows: dict[datetime, SocRow] = {}
    total_in, total_out = battery.lifetime
    hour = battery.first.astimezone(UTC)
    last = NOW.astimezone(UTC).replace(minute=0) - HOUR
    capacity = battery.actual(battery.first.date())
    stored = 0.4 * capacity
    weather = 0.0
    plan: dict[int, float] = {}
    day = None
    soc_now = 0.0
    while hour <= last + HOUR:
        local = hour.astimezone(BERLIN)
        if local.date() != day:
            day = local.date()
            weather = 0.55 * weather + rng.gauss(0, 0.32)
            if day == NOW.date():  # the demo day is sunny
                weather = max(weather, 0.3)
            plan = day_plan(battery, day, min(1.0, max(0.05, 0.62 + weather)), rng)
            capacity = battery.actual(day)
            stored = min(stored, capacity)
            # The battery management estimates the state of charge; its
            # scale drifts by a few percent (spreads the capacity samples).
            bms = 1 + 0.6 * (bms - 1) + drift.gauss(0, 0.02)
        eta_in = battery.eta_in(day)
        before = stored
        power = plan[local.hour]
        charged = discharged = 0.0
        if power > 0:
            charged = max(0.0, min(power, (capacity - stored) / eta_in))
            stored += charged * eta_in
        elif power < 0:
            available = stored - battery.floor / 100 * capacity
            discharged = max(0.0, min(-power, available * battery.eta_out))
            stored -= discharged / battery.eta_out
        stored -= battery.rest_watts(day) / 1000
        if stored < (battery.floor - 2) / 100 * capacity:
            top_up = battery.floor / 100 * capacity - stored
            charged += top_up / eta_in
            stored += top_up
        total_in += charged
        total_out += discharged
        low, high = sorted(
            min(100.0, energy / capacity * 100 * bms) for energy in (before, stored)
        )
        mean = (low + high) / 2
        if hour > last:  # the running hour: only the state of charge "now"
            soc_now = round(mean, 1)
            break
        charged_states[hour] = round(total_in, 3)
        discharged_states[hour] = round(total_out, 3)
        soc_rows[hour] = SocRow(round(mean, 2), round(low, 1), round(high, 1))
        hour += HOUR
    return Statistics(charged_states, discharged_states, soc_rows, soc_now)


# ---- What Home Assistant shows (rebuilt from the HA-dependent modules) ---------------------


def _kwh(value: float) -> float:
    return round(value, 2)


def _rounded(kwh: float | None) -> float | None:
    return None if kwh is None else _kwh(kwh)


def slug(text: str) -> str:
    """Like Home Assistant's slugify for entity IDs (ä → a)."""
    plain = unicodedata.normalize("NFKD", text.replace("ß", "ss"))
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    words = "".join(c if c.isalnum() else " " for c in plain).split()
    return "_".join(words)


def sensors(battery: Battery, series: Series, analysis: Analysis) -> dict[str, Any]:
    """State and attributes of each sensor as sensor.py writes them."""
    lifetime = (
        None
        if series.first_discharged is None
        else series.first_discharged + analysis.discharged_total
    )
    since = analysis.first_day.isoformat() if analysis.first_day else None
    result: dict[str, Any] = {}
    for period in Period:
        eff = analysis.efficiency[period]
        result[f"efficiency_{period.value}"] = {
            "state": None if eff.ratio is None else round(eff.ratio * 100, 1),
            "disabled": period is Period.TODAY,
            "attributes": {
                "charged_kwh": _kwh(eff.charged),
                "discharged_kwh": _kwh(eff.discharged),
                "stored_change_kwh": _kwh(eff.stored),
                "operating_days": eff.operating_days,
                "rest_days": eff.rest_days,
                "rest_loss_kwh": _kwh(eff.rest_loss),
                "days_without_soc": eff.days_without_soc,
                "incomplete_days": eff.incomplete_days,
                "since": eff.first_day.isoformat() if eff.first_day else None,
                "boundary": battery.boundary,
                "reason": eff.reason,
            },
        }
    result["full_cycles_total"] = {
        "state": None if lifetime is None else round(lifetime / battery.capacity, 1),
        "attributes": {
            "discharged_lifetime_kwh": _rounded(lifetime),
            "charged_in_statistics_kwh": _kwh(analysis.charged_total),
            "discharged_in_statistics_kwh": _kwh(analysis.discharged_total),
            "statistics_since": since,
            "capacity_kwh": battery.capacity,
        },
    }
    result["full_cycles_year"] = {
        "state": round(analysis.cycles_year, 1),
        "attributes": {"statistics_since": since},
    }
    rest = analysis.rest
    result["rest_loss"] = {
        "state": None if rest.watts is None else round(rest.watts),
        "attributes": {
            "rest_hours": round(rest.hours),
            "raw_watts": None if rest.raw_watts is None else round(rest.raw_watts, 1),
            "reason": rest.reason,
        },
    }
    estimate = analysis.capacity
    result["capacity_estimate"] = {
        "state": _rounded(estimate.kwh),
        "attributes": {
            "share_of_data_sheet_percent": None
            if estimate.kwh is None
            else round(estimate.kwh / battery.capacity * 100, 1),
            "data_sheet_kwh": battery.capacity,
            "samples_kwh": [_kwh(s) for s in estimate.samples],
            "reason": estimate.reason,
        },
    }
    if battery.warranty_mwh:
        warranty_kwh = battery.warranty_mwh * 1000
        result["warranty_used"] = {
            "state": None
            if lifetime is None
            else round(lifetime / warranty_kwh * 100, 1),
            "attributes": {
                "discharged_lifetime_kwh": _rounded(lifetime),
                "warranty_mwh": battery.warranty_mwh,
            },
        }
    return result


def problem(result: Check) -> dict[str, Any]:
    """State and attributes of a problem sensor (binary_sensor.py)."""
    return {
        "state": None if result.problem is None else "on" if result.problem else "off",
        "attributes": {
            **{
                key: round(value, 1) if isinstance(value, float) else value
                for key, value in result.details.items()
            },
            "reason": result.reason,
        },
    }


def action_response(battery: Battery, hours: list, start: datetime, now: datetime) -> dict[str, Any]:  # fmt: skip
    """The response of speicherwacht.report (services.py around report.py)."""
    figures = report(hours, battery.capacity, BERLIN, start, now, now)
    return {
        "start": start.astimezone(BERLIN).isoformat(),
        "end": now.astimezone(BERLIN).isoformat(),
        "boundary": battery.boundary,
        "capacity_kwh": battery.capacity,
        **figures,
    }


def entity_names() -> dict[str, Any]:
    """Entity and action names from the integration's translations."""
    names = {}
    for lang in ("de", "en"):
        data = json.loads((TRANSLATIONS / f"{lang}.json").read_text(encoding="utf-8"))
        names[lang] = {
            platform: {key: value["name"] for key, value in entities.items()}
            for platform, entities in data["entity"].items()
        }
        names[lang]["report"] = data["services"]["report"]["name"]
    return names


def build_battery(battery: Battery, names: dict[str, Any]) -> dict[str, Any]:
    stats = simulate(battery)
    now = NOW.astimezone(UTC)
    series = build(stats.charged, stats.discharged, stats.soc, battery.capacity)
    analysis = analyse(series.hours, battery.capacity, BERLIN, now)
    health = check(series.hours, battery.capacity, BERLIN, now)
    year_start = local_midnight(date(NOW.year, 1, 1), BERLIN)
    first_day = local_midnight(battery.first.date(), BERLIN)
    history = report(series.hours, battery.capacity, BERLIN, first_day, now, now)
    device = slug(battery.name)
    entity_ids = {
        f"{platform}.{key}": f"{platform}.{device}_{slug(name)}"
        for platform, entities in names["de"].items()
        if platform in ("sensor", "binary_sensor")
        for key, name in entities.items()
    }
    return {
        "key": battery.key,
        "name": battery.name,
        "area": battery.area,
        "version": VERSION,
        "now": NOW.isoformat(),
        "capacity_kwh": battery.capacity,
        "boundary": battery.boundary,
        "warranty_mwh": battery.warranty_mwh,
        "statistics_since": battery.first.isoformat(),
        "soc": stats.soc_now,
        "rejected_readings": len(series.issues),
        "entity_ids": entity_ids,
        "sensors": sensors(battery, series, analysis),
        "binary_sensors": {
            "efficiency_drop": problem(health.efficiency_drop),
            "capacity_low": problem(health.capacity_low),
            "rest_loss_high": problem(health.rest_loss_high),
        },
        "mismatch": problem(health.mismatch),
        "months": [
            {k: m[k] for k in ("month", "charged_kwh", "discharged_kwh")}
            for m in history["months"]
        ],
        "report": action_response(battery, series.hours, year_start, now),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = entity_names()
    with (OUT / "names.json").open("w", encoding="utf-8", newline="\n") as file:
        json.dump(names, file, ensure_ascii=False, separators=(",", ":"))
    for battery in BATTERIES:
        data = build_battery(battery, names)
        path = OUT / f"{battery.key}.json"
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, separators=(",", ":"))
        s = data["sensors"]
        b = data["binary_sensors"]
        months = ", ".join(
            f"{m['month'][2:]} {m['efficiency_percent']}"
            for m in data["report"]["months"]
        )
        print(
            f"{battery.key} ({battery.name}, {battery.capacity} kWh): "
            f"Monat {s['efficiency_month']['state']} %, Jahr {s['efficiency_year']['state']} %, "
            f"gesamt {s['efficiency_total']['state']} %, Ruheverlust {s['rest_loss']['state']} W, "
            f"Kapazität {s['capacity_estimate']['state']} kWh "
            f"({s['capacity_estimate']['attributes']['share_of_data_sheet_percent']} %), "
            f"Zyklen {s['full_cycles_total']['state']} / {s['full_cycles_year']['state']}, "
            f"SoC {data['soc']} %, {path.stat().st_size // 1024} KB"
        )
        for key, value in b.items():
            print(f"  {key}: {value['state']} {value['attributes']}")
        print(
            f"  mismatch: {data['mismatch']['state']}, verworfen: {data['rejected_readings']}"
        )
        print(f"  Monate 2026: {months}")


if __name__ == "__main__":
    main()
