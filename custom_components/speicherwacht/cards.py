"""The Lovelace card (frontend/speicherwacht-card.js).

The integration serves the file itself and registers it with the frontend
as a dashboard resource (frontend_resource.py), so nobody has to add one; a
new version busts the cache by its query string. The card reads
Speicherwacht's own entities through the entity registry (device and
translation key). Only the entry knows the figures per month and its repair
issues: the websocket command "speicherwacht/card" hands them out, from the
hours read anyway (no extra recorder query, runtime.async_months).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, VERSION

if TYPE_CHECKING:
    from .runtime import StorageRuntime

CARD_FILE = "speicherwacht-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"
# The URL the frontend loads: a new version is a new URL (no stale cache).
CARD_RESOURCE_URL = f"{CARD_URL}?v={VERSION}"


async def async_setup_cards(hass: HomeAssistant) -> None:
    """Serve the card and register the websocket command; without http
    (tests) only the command. The frontend learns of the card per entry
    (frontend_resource.async_register_card)."""
    websocket_api.async_register_command(hass, ws_card)
    if getattr(hass, "http", None) is None:
        return
    from homeassistant.components.http import StaticPathConfig

    path = Path(__file__).parent / "frontend" / CARD_FILE
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(path), True)]
    )


def device_runtime(hass: HomeAssistant, device_id: str) -> StorageRuntime | None:
    """The runtime of a Speicherwacht device; None if the device is no
    loaded entry of Speicherwacht."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    # Since HA 2026.11 a device belongs to one entry (`config_entry_id`);
    # `config_entries` warns and goes in 2027.10. Older versions only have it.
    if hasattr(device, "config_entry_id"):
        entry_ids = [device.config_entry_id] if device.config_entry_id else []
    else:
        entry_ids = list(device.config_entries)
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is not None
            and entry.domain == DOMAIN
            and entry.state is ConfigEntryState.LOADED
        ):
            return entry.runtime_data
    return None


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/card", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def ws_card(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Months and repair issues of a Speicherwacht device for the card;
    `months` is null until the first analysis (about a minute after the
    start)."""
    runtime = device_runtime(hass, msg["device_id"])
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No Speicherwacht device")
        return
    connection.send_result(
        msg["id"],
        {
            "months": await runtime.async_months(),
            "issues": runtime.active_issues(),
        },
    )
