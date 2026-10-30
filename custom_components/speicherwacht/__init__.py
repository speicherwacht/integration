"""Speicherwacht: efficiency, cycles, rest losses and capacity of a battery."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .runtime import ISSUE_MISSING, ISSUE_UNAVAILABLE, ISSUE_UNIT, StorageRuntime

PLATFORMS: list[Platform] = [Platform.SENSOR]
ISSUES = (ISSUE_MISSING, ISSUE_UNAVAILABLE, ISSUE_UNIT)

type SpeicherwachtConfigEntry = ConfigEntry[StorageRuntime]


async def async_setup_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> bool:
    """Set up one storage."""
    runtime = StorageRuntime(hass, entry)
    entry.runtime_data = runtime
    await runtime.async_start()
    # Entities, capacity or boundary changed: reload.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> None:
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> None:
    """Nothing is stored; only the repair issues of the entry go."""
    for key in ISSUES:
        ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_{key}")
