"""Suggestions from sister integrations, so that a meter is entered once.

Read from their config entries when a form is shown and copied once as a
suggested value; no dependency at runtime. Pure Python, no Home Assistant
imports: the entries are duck-typed (title, subentries with subentry_type
and data).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .model import Signal

TARIFWACHT = "tarifwacht"
# Link of the tip (hassfest refuses URLs in translations).
TARIFWACHT_URL = "https://github.com/tarifwacht/integration"
# Tarifwacht's subentry "PV and battery" and its optional battery meters
# (tarifwacht/const.py: SUBENTRY_SOLAR, CONF_CHARGED_ENTITY,
# CONF_DISCHARGED_ENTITY).
TARIFWACHT_SOLAR = "solar"
TARIFWACHT_COUNTERS = {
    Signal.CHARGED.value: "charged_entity",
    Signal.DISCHARGED.value: "discharged_entity",
}


def tarifwacht_battery(entries: Iterable[Any]) -> tuple[str, dict[str, str]] | None:
    """(entry title, {signal: entity}) of the first Tarifwacht entry whose
    "PV and battery" has both battery meters; None without one."""
    for entry in entries:
        for subentry in entry.subentries.values():
            if subentry.subentry_type != TARIFWACHT_SOLAR:
                continue
            counters = {
                signal: subentry.data.get(key)
                for signal, key in TARIFWACHT_COUNTERS.items()
            }
            if all(isinstance(v, str) and v for v in counters.values()):
                return entry.title, counters
    return None
