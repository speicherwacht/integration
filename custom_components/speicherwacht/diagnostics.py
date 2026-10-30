"""Diagnostics: configuration, figures and what the counter module rejected.

Contains energy sums of the storage; the README asks to check the file
before sharing it.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .const import VERSION

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import SpeicherwachtConfigEntry

# The latest rejected readings shown.
ISSUE_LIMIT = 50


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> dict[str, Any]:
    runtime = entry.runtime_data
    series = runtime.series
    hours = series.hours if series else []
    sources = {}
    for signal, entity_id in runtime.entities.items():
        state = hass.states.get(entity_id)
        sources[signal.value] = {
            "entity_id": entity_id,
            "state": state.state if state else None,
            "unit": state.attributes.get("unit_of_measurement") if state else None,
            "state_class": state.attributes.get("state_class") if state else None,
        }
    analysis = runtime.analysis
    return {
        "version": VERSION,
        "data": dict(entry.data),
        "sources": sources,
        "problem": runtime.problem,
        "hours": {
            "count": len(hours),
            "first": hours[0].start.isoformat() if hours else None,
            "last": hours[-1].start.isoformat() if hours else None,
            "gaps": sum(1 for h in hours if h.gap),
        },
        "rejected_readings": [
            {"hour": i.hour.isoformat(), "signal": i.signal, "event": i.event.value}
            for i in (series.issues[-ISSUE_LIMIT:] if series else [])
        ],
        "analysis": asdict(analysis) if analysis else None,
    }
