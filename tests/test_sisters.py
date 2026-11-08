"""Suggestions from sister integrations (duck-typed config entries)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from custom_components.speicherwacht.sisters import tarifwacht_battery


def entry(title: str, *subentries: tuple[str, dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        subentries={
            str(i): SimpleNamespace(subentry_type=kind, data=data)
            for i, (kind, data) in enumerate(subentries)
        },
    )


SOLAR = {
    "feed_in_entity": "sensor.feed_in",
    "pv_entity": "sensor.pv",
    "charged_entity": "sensor.battery_in",
    "discharged_entity": "sensor.battery_out",
}


def test_no_tarifwacht() -> None:
    assert tarifwacht_battery([]) is None


def test_tarifwacht_without_pv_subentry() -> None:
    assert tarifwacht_battery([entry("Haus", ("tariff", {"kind": "fixed"}))]) is None


def test_pv_without_battery() -> None:
    solar = {k: v for k, v in SOLAR.items() if "charged" not in k}
    assert tarifwacht_battery([entry("Haus", ("solar", solar))]) is None


def test_found() -> None:
    entries = [
        entry("Wohnung", ("tariff", {"kind": "fixed"})),
        entry("Haus", ("tariff", {"kind": "fixed"}), ("solar", SOLAR)),
    ]
    assert tarifwacht_battery(entries) == (
        "Haus",
        {"charged": "sensor.battery_in", "discharged": "sensor.battery_out"},
    )
