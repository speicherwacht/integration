"""Config flow: own mapping, detected Fronius storage, errors, reconfigure."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.speicherwacht.const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    CONF_WARRANTY_MWH,
    DOMAIN,
)

from ..conftest import load_fixture
from .conftest import CHARGED, DISCHARGED, ENERGY, PERCENT, SOC, set_sources

MANUAL = {
    "charged": CHARGED,
    "discharged": DISCHARGED,
    "soc": SOC,
    CONF_CAPACITY: 10.0,
    CONF_BOUNDARY: "battery",
}


async def start_manual(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Akku", "source": "manual"}
    )


def suggested(result: dict[str, Any]) -> dict[str, Any]:
    """Prefilled values of a form."""
    values = {}
    for key in result["data_schema"].schema:
        description = key.description or {}
        if "suggested_value" in description:
            values[str(key)] = description["suggested_value"]
    return values


async def test_own_mapping(hass: HomeAssistant) -> None:
    set_sources(hass)
    result = await start_manual(hass)
    assert result["step_id"] == "entities"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, CONF_WARRANTY_MWH: 30.82}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Akku"
    assert result["data"][CONF_ENTITIES] == {
        "charged": CHARGED,
        "discharged": DISCHARGED,
        "soc": SOC,
    }
    assert result["data"][CONF_CAPACITY] == 10.0
    assert result["data"][CONF_TEMPLATE] == "manual"
    assert result["data"][CONF_WARRANTY_MWH] == 30.82


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"charged": {**ENERGY, "state_class": None}}, "counter_statistics"),
        ({"discharged": {**ENERGY, "unit_of_measurement": "W"}}, "energy_unit"),
        ({"soc": {**PERCENT, "state_class": None}}, "soc_statistics"),
        ({"soc": {**PERCENT, "unit_of_measurement": "kWh"}}, "soc_unit"),
    ],
)
async def test_unusable_sources(
    hass: HomeAssistant, changes: dict[str, Any], error: str
) -> None:
    set_sources(hass, **changes)
    result = await start_manual(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_same_entity_twice(hass: HomeAssistant) -> None:
    set_sources(hass)
    result = await start_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "discharged": CHARGED}
    )
    assert result["errors"] == {"base": "same_entity"}


async def test_detected_fronius_storage(hass: HomeAssistant) -> None:
    fixture = load_fixture("fronius_gen24_byd_hvs.json")
    fronius = MockConfigEntry(domain="fronius")
    fronius.add_to_hass(hass)
    registry = er.async_get(hass)
    for entity in fixture["entities"]:
        domain, object_id = entity["entity_id"].split(".", 1)
        registry.async_get_or_create(
            domain,
            "fronius",
            entity["unique_id"],
            suggested_object_id=object_id,
            config_entry=fronius,
        )
        hass.states.async_set(
            entity["entity_id"], entity["state"], entity["attributes"]
        )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    choice = f"fronius:{fronius.entry_id}"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "BYD", "source": choice}
    )
    assert result["step_id"] == "entities"
    prefill = suggested(result)
    assert prefill["charged"] == "sensor.fronius_gen24_gesamtenergie_batterieaufladung"
    assert prefill["soc"] == "sensor.byd_battery_box_premium_hv_ladezustand"
    assert prefill[CONF_CAPACITY] == pytest.approx(10.24)
    values = {key: prefill[key] for key in ("charged", "discharged", "soc")}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**values, CONF_CAPACITY: 10.24, CONF_BOUNDARY: "battery"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TEMPLATE] == "fronius"
    # The charge counter identifies the storage, whichever way it was chosen.
    assert result["result"].unique_id == values["charged"]

    # The same storage again, by template or by hand: refused.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "BYD", "source": choice}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**values, CONF_CAPACITY: 10.24, CONF_BOUNDARY: "battery"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "counter_in_use"}


async def test_reconfigure(hass: HomeAssistant) -> None:
    set_sources(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Akku",
        data={
            "name": "Akku",
            CONF_TEMPLATE: "manual",
            CONF_ENTITIES: {"charged": CHARGED, "discharged": DISCHARGED, "soc": SOC},
            CONF_CAPACITY: 10.0,
            CONF_BOUNDARY: "battery",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "entities"
    assert suggested(result)[CONF_CAPACITY] == 10.0
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, CONF_CAPACITY: 9.5, CONF_BOUNDARY: "system"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CAPACITY] == 9.5
    assert entry.data[CONF_BOUNDARY] == "system"


async def test_reconfigure_keeps_its_own_counters(hass: HomeAssistant) -> None:
    """Its own charge counter is no conflict; another entry's is."""
    set_sources(hass)
    hass.states.async_set("sensor.other_charged", "5.0", ENERGY)
    data = {
        "name": "Akku",
        CONF_TEMPLATE: "manual",
        CONF_ENTITIES: {"charged": CHARGED, "discharged": DISCHARGED, "soc": SOC},
        CONF_CAPACITY: 10.0,
        CONF_BOUNDARY: "battery",
    }
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Zweiter",
        data={
            **data,
            CONF_ENTITIES: {**data[CONF_ENTITIES], "charged": "sensor.other_charged"},
        },
    )
    other.add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Akku", data=data)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "charged": "sensor.other_charged"}
    )
    assert result["errors"] == {"base": "counter_in_use"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_moves_the_unique_id(hass: HomeAssistant) -> None:
    """Another charge counter identifies the entry from now on."""
    set_sources(hass)
    hass.states.async_set("sensor.new_charged", "5.0", ENERGY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Akku",
        unique_id=CHARGED,
        data={
            "name": "Akku",
            CONF_TEMPLATE: "manual",
            CONF_ENTITIES: {"charged": CHARGED, "discharged": DISCHARGED, "soc": SOC},
            CONF_CAPACITY: 10.0,
            CONF_BOUNDARY: "battery",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "charged": "sensor.new_charged"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "sensor.new_charged"
    assert entry.data[CONF_ENTITIES]["charged"] == "sensor.new_charged"
