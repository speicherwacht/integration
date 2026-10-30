"""Speicherwacht: efficiency, cycles, rest losses and capacity of a battery."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .rename import renamed_data, renamed_unique_id, sources
from .runtime import (
    ISSUE_MISMATCH,
    ISSUE_MISSING,
    ISSUE_RESETS,
    ISSUE_UNAVAILABLE,
    ISSUE_UNIT,
    StorageRuntime,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
ISSUES = (
    ISSUE_MISSING,
    ISSUE_UNAVAILABLE,
    ISSUE_UNIT,
    ISSUE_RESETS,
    ISSUE_MISMATCH,
)

type SpeicherwachtConfigEntry = ConfigEntry[StorageRuntime]

# Renames come in bursts ("recreate entity IDs" of a device): the entries
# reload once, this long after the last one (as Wärmewacht).
RENAME_RELOAD_DELAY = timedelta(seconds=3)
# Entries whose sources were renamed and which wait for that reload.
RENAMED: HassKey[set[str]] = HassKey(f"{DOMAIN}_renamed")
# A reload picks up the renamed sources; a disabled or unloaded entry reads
# them at its next setup.
RELOAD_STATES = (
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.SETUP_ERROR,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Follow renamed sources (once, for all entries)."""
    _async_follow_renames(hass)
    return True


@callback
def _async_follow_renames(hass: HomeAssistant) -> None:
    """Follow source entities renamed in the entity registry.

    Home Assistant's own helpers listen per entry (helper_integration.py).
    One listener for all entries also sees entries that are reloading or
    failed to set up, and an id renamed again before the reload. The entry
    data changes at once; the reload follows when the burst is over.
    Removed entities are left to the repair issue "missing_entity".
    """
    waiting = hass.data.setdefault(RENAMED, set())
    cancel: CALLBACK_TYPE | None = None

    @callback
    def _reload(_now: datetime) -> None:
        nonlocal cancel
        cancel = None
        for entry_id in sorted(waiting):
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.state in RELOAD_STATES:
                hass.config_entries.async_schedule_reload(entry_id)
        waiting.clear()

    @callback
    def _is_rename(data: er.EventEntityRegistryUpdatedData) -> bool:
        return data["action"] == "update" and "old_entity_id" in data

    @callback
    def _on_rename(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        nonlocal cancel
        old: str = event.data["old_entity_id"]  # type: ignore[typeddict-item]
        new = event.data["entity_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            used = sources(entry.data)
            if old not in used:
                continue
            if new in used:
                # Two sources would become one entity: leave it to the user.
                _LOGGER.warning(
                    "%s: %s was renamed to %s, which is already a source; "
                    "please reconfigure",
                    entry.title,
                    old,
                    new,
                )
                continue
            changes: dict[str, Any] = {"data": renamed_data(entry.data, old, new)}
            unique_id = renamed_unique_id(entry.unique_id, old, new)
            if unique_id and not hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            ):
                changes["unique_id"] = unique_id
            waiting.add(entry.entry_id)
            hass.config_entries.async_update_entry(entry, **changes)
            _LOGGER.info("%s: source %s renamed to %s", entry.title, old, new)
        if waiting:
            if cancel is not None:
                cancel()
            cancel = async_call_later(
                hass,
                RENAME_RELOAD_DELAY,
                HassJob(_reload, "speicherwacht_renamed", cancel_on_shutdown=True),
            )

    hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, _on_rename, event_filter=_is_rename
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> bool:
    """Set up one storage."""
    runtime = StorageRuntime(hass, entry)
    entry.runtime_data = runtime
    await runtime.async_start()
    # Also when setting up the platforms fails: no timers stay behind.
    entry.async_on_unload(runtime.async_stop)
    # Entities, capacity or boundary changed: reload.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> None:
    if entry.entry_id in hass.data.get(RENAMED, ()):
        return  # renamed sources: the reload follows the burst
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Disabled or reloaded entries keep no stale repair issues; a reload
        # raises them again if the cause remains.
        _delete_issues(hass, entry)
    return unloaded


async def async_remove_entry(
    hass: HomeAssistant, entry: SpeicherwachtConfigEntry
) -> None:
    """Nothing is stored; only the repair issues of the entry go."""
    _delete_issues(hass, entry)


def _delete_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    for key in ISSUES:
        ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_{key}")
