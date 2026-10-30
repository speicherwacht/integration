"""Renamed source entities: the entries follow without reconfiguring."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.speicherwacht.const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    DOMAIN,
)
from custom_components.speicherwacht.model import Signal

from .conftest import CHARGED, DISCHARGED, SOC, set_sources

SOURCES = {"charged": CHARGED, "discharged": DISCHARGED, "soc": SOC}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_mock: Recorder, enable_custom_integrations: None
) -> None:
    """The recorder must be set up before `hass` (listed first)."""


async def wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def setup(hass: HomeAssistant, unique_id: str | None) -> MockConfigEntry:
    registry = er.async_get(hass)
    for entity_id in SOURCES.values():
        if registry.async_get(entity_id) is None:
            domain, object_id = entity_id.split(".")
            registry.async_get_or_create(
                domain, "test", object_id, suggested_object_id=object_id
            )
    set_sources(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Akku",
        unique_id=unique_id,
        data={
            "name": "Akku",
            CONF_TEMPLATE: "manual",
            CONF_ENTITIES: dict(SOURCES),
            CONF_CAPACITY: 10.0,
            CONF_BOUNDARY: "battery",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def rename(hass: HomeAssistant, old: str, new: str) -> None:
    """As Home Assistant does it: the entity comes back under the new id."""
    state = hass.states.get(old)
    er.async_get(hass).async_update_entity(old, new_entity_id=new)
    hass.states.async_remove(old)
    if state is not None:
        hass.states.async_set(new, state.state, state.attributes)


async def test_source_renamed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    entry = await setup(hass, CHARGED)
    before = entry.runtime_data

    rename(hass, CHARGED, "sensor.fronius_charged")
    rename(hass, SOC, "sensor.byd_soc")
    await hass.async_block_till_done()
    # The data follows at once, the reload waits for the end of the burst.
    assert entry.data[CONF_ENTITIES] == {
        "charged": "sensor.fronius_charged",
        "discharged": DISCHARGED,
        "soc": "sensor.byd_soc",
    }
    assert entry.unique_id == "sensor.fronius_charged"
    assert entry.runtime_data is before

    await wait(hass, freezer, 5)
    assert entry.state is ConfigEntryState.LOADED
    runtime = entry.runtime_data
    assert runtime is not before
    assert runtime.entities[Signal.CHARGED] == "sensor.fronius_charged"
    assert runtime.entities[Signal.SOC] == "sensor.byd_soc"

    # No repair issue after the grace time.
    await wait(hass, freezer, 15 * 60)
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, f"{entry.entry_id}_missing_entity") is None


async def test_renamed_twice_and_shared(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Two entries with the same counter; renamed again before the reload.
    The unique id stays where another entry already carries the new one."""
    first = await setup(hass, CHARGED)
    second = await setup(hass, None)
    other = MockConfigEntry(
        domain=DOMAIN, title="Alt", unique_id="sensor.home_charged", data={}
    )
    other.add_to_hass(hass)

    rename(hass, CHARGED, "sensor.battery_in")
    await wait(hass, freezer, 1)
    rename(hass, "sensor.battery_in", "sensor.home_charged")
    await wait(hass, freezer, 5)

    for entry in (first, second):
        assert entry.state is ConfigEntryState.LOADED
        assert entry.data[CONF_ENTITIES]["charged"] == "sensor.home_charged"
        assert entry.runtime_data.entities[Signal.CHARGED] == "sensor.home_charged"
    assert first.unique_id == "sensor.battery_in"
    assert second.unique_id is None


async def test_rename_onto_another_source(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The new id is already a source of the entry: nothing changes."""
    entry = await setup(hass, CHARGED)
    er.async_get(hass).async_remove(DISCHARGED)
    hass.states.async_remove(DISCHARGED)

    rename(hass, CHARGED, DISCHARGED)
    await wait(hass, freezer, 5)
    assert entry.data[CONF_ENTITIES] == SOURCES
    assert entry.unique_id == CHARGED
    assert entry.state is ConfigEntryState.LOADED


async def test_other_changes_ignored(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A new name or a removed entity is not a rename."""
    entry = await setup(hass, CHARGED)
    before = entry.runtime_data
    er.async_get(hass).async_update_entity(CHARGED, name="Akku geladen")
    er.async_get(hass).async_remove(SOC)
    await wait(hass, freezer, 5)
    assert entry.data[CONF_ENTITIES] == SOURCES
    assert entry.runtime_data is before
