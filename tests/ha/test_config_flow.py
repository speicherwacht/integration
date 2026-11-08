"""Config flow: own mapping, detected Fronius storage, errors, reconfigure,
suggestions from Tarifwacht."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section
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
    "more": {CONF_BOUNDARY: "battery"},
}
STORED = {
    "name": "Akku",
    CONF_TEMPLATE: "manual",
    CONF_ENTITIES: {"charged": CHARGED, "discharged": DISCHARGED, "soc": SOC},
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
    """Prefilled values of a form (fields of sections flat)."""
    values = {}

    def walk(schema: dict[Any, Any]) -> None:
        for key, value in schema.items():
            if isinstance(value, section):
                walk(value.schema.schema)
                continue
            description = key.description or {}
            if "suggested_value" in description:
                values[str(key)] = description["suggested_value"]

    walk(result["data_schema"].schema)
    return values


def unchanged_input(result: dict[str, Any]) -> dict[str, Any]:
    """What the frontend sends for a form submitted unchanged, without
    opening a section (computeInitialHaFormData): each field's suggested
    value, else its default; sections nested, collapsed or not."""

    def values(schema: dict[Any, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key, value in schema.items():
            if isinstance(value, section):
                data[str(key)] = values(value.schema.schema)
                continue
            suggested_value = (key.description or {}).get("suggested_value")
            if suggested_value is not None:
                data[str(key)] = suggested_value
            elif key.default is not type(key)("x").default:
                data[str(key)] = key.default()
        return data

    return values(result["data_schema"].schema)


def more_collapsed(result: dict[str, Any]) -> bool:
    schema = result["data_schema"].schema
    return next(v for k, v in schema.items() if k == "more").options["collapsed"]


async def test_own_mapping(hass: HomeAssistant) -> None:
    set_sources(hass)
    result = await start_manual(hass)
    # Without Tarifwacht: the tip, nothing suggested.
    assert result["step_id"] == "entities_tarifwacht_tip"
    assert result["description_placeholders"] == {
        "tarifwacht_url": "https://github.com/tarifwacht/integration"
    }
    assert not suggested(result).get("charged")
    # Boundary and warranty in the collapsed section "more".
    assert more_collapsed(result)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MANUAL, "more": {CONF_BOUNDARY: "battery", CONF_WARRANTY_MWH: 30.82}},
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
    assert result["data"][CONF_BOUNDARY] == "battery"


async def test_own_mapping_without_the_section(hass: HomeAssistant) -> None:
    """A section left out of the input: boundary battery, no warranty."""
    set_sources(hass)
    result = await start_manual(hass)
    plain = {k: v for k, v in MANUAL.items() if k != "more"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], plain)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BOUNDARY] == "battery"
    assert result["data"][CONF_WARRANTY_MWH] is None


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


async def test_own_sensor_as_source_is_refused(hass: HomeAssistant) -> None:
    """An own efficiency sensor (in %, measurement) passes every other check
    as state of charge; the entry would read its own results (seen in
    Wärmewacht, 2026-11)."""
    set_sources(hass)
    own = er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "01JZ_efficiency_month", suggested_object_id="akku_month"
    )
    hass.states.async_set(own.entity_id, "93.0", PERCENT)
    result = await start_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "soc": own.entity_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "own_entity"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_refuses_own_sensor(hass: HomeAssistant) -> None:
    set_sources(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Akku", unique_id=CHARGED, data=STORED)
    entry.add_to_hass(hass)
    own = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_warranty_used",
        suggested_object_id="akku_warranty_used",
        config_entry=entry,
    )
    hass.states.async_set(own.entity_id, "12.0", PERCENT)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "soc": own.entity_id}
    )
    assert result["errors"] == {"base": "own_entity"}


def add_tarifwacht(hass: HomeAssistant, *subentries: dict[str, Any]) -> None:
    """A Tarifwacht entry (not set up; only its data is read)."""
    MockConfigEntry(
        domain="tarifwacht",
        title="Haus",
        data={"name": "Haus", "meter_entity": "sensor.grid_import"},
        version=2,
        subentries_data=[
            {
                "data": data,
                "subentry_id": f"sub{i}",
                "subentry_type": data.pop("type"),
                "title": "PV",
                "unique_id": None,
            }
            for i, data in enumerate(subentries)
        ],
    ).add_to_hass(hass)


TARIFF = {"type": "tariff", "kind": "fixed", "price": 30.0, "current": True}
SOLAR = {
    "type": "solar",
    "feed_in_entity": "sensor.feed_in",
    "pv_entity": "sensor.pv",
    "charged_entity": CHARGED,
    "discharged_entity": DISCHARGED,
    "same_inverter": True,
}


async def test_tarifwacht_without_pv_subentry(hass: HomeAssistant) -> None:
    set_sources(hass)
    add_tarifwacht(hass, dict(TARIFF))
    result = await start_manual(hass)
    assert result["step_id"] == "entities_tarifwacht_tip"
    assert not suggested(result).get("charged")


async def test_counters_suggested_from_tarifwacht(hass: HomeAssistant) -> None:
    set_sources(hass)
    add_tarifwacht(hass, dict(TARIFF), dict(SOLAR))
    result = await start_manual(hass)
    assert result["step_id"] == "entities_tarifwacht"
    assert result["description_placeholders"] == {"tarifwacht": "Haus"}
    prefill = suggested(result)
    assert prefill["charged"] == CHARGED
    assert prefill["discharged"] == DISCHARGED
    assert not prefill.get("soc")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENTITIES]["charged"] == CHARGED

    # A second storage: Tarifwacht's counters belong to the first one now,
    # so they are not suggested again (and no tip either).
    result = await start_manual(hass)
    assert result["step_id"] == "entities"
    assert not suggested(result).get("charged")


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
    assert more_collapsed(result)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], unchanged_input(result)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TEMPLATE] == "fronius"
    assert result["data"][CONF_BOUNDARY] == "battery"
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
        {**values, CONF_CAPACITY: 10.24, "more": {CONF_BOUNDARY: "battery"}},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "counter_in_use"}


async def test_reconfigure(hass: HomeAssistant) -> None:
    set_sources(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Akku", data=STORED)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert suggested(result)[CONF_CAPACITY] == 10.0
    assert more_collapsed(result)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MANUAL, CONF_CAPACITY: 9.5, "more": {CONF_BOUNDARY: "system"}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CAPACITY] == 9.5
    assert entry.data[CONF_BOUNDARY] == "system"


async def test_reconfigure_unchanged_keeps_every_value(hass: HomeAssistant) -> None:
    """Saved without opening the section (or without the section at all):
    boundary and warranty stay as stored, never the defaults."""
    set_sources(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Akku",
        data={**STORED, CONF_BOUNDARY: "system", CONF_WARRANTY_MWH: 30.82},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    # A boundary other than expected or a warranty: the section is open.
    assert not more_collapsed(result)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], unchanged_input(result)
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BOUNDARY] == "system"
    assert entry.data[CONF_WARRANTY_MWH] == 30.82
    assert entry.data[CONF_CAPACITY] == 10.0

    result = await entry.start_reconfigure_flow(hass)
    plain = {k: v for k, v in unchanged_input(result).items() if k != "more"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], plain)
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BOUNDARY] == "system"
    assert entry.data[CONF_WARRANTY_MWH] == 30.82


async def test_reconfigure_summary(hass: HomeAssistant) -> None:
    """The summary on top: own mapping matching Tarifwacht, the language of
    Home Assistant, the entry not loaded (statistics not read)."""
    set_sources(hass)
    add_tarifwacht(hass, dict(TARIFF), dict(SOLAR))
    entry = MockConfigEntry(domain=DOMAIN, title="Akku", data=STORED)
    entry.add_to_hass(hass)
    hass.config.language = "de"
    result = await entry.start_reconfigure_flow(hass)
    summary = result["description_placeholders"]["summary"]
    assert summary.startswith(
        "**Eingerichtet**\n"
        "- Quelle: eigene Zuordnung, Zähler wie in Tarifwacht „Haus“\n"
        "- Zähler: Gesamtzähler (Lebenszeit) in kWh, messen den Akku (DC)\n"
        "- Ladezustand: jetzt 50 %\n"
        "- Kapazität: 10 kWh laut Datenblatt\n"
    )
    assert "- Daten: noch nicht gelesen (kurz nach dem Start)" in summary
    assert "Kein Garantie-Durchsatz" in summary


async def test_reconfigure_summary_template_and_missing_soc(
    hass: HomeAssistant,
) -> None:
    set_sources(hass)
    hass.states.async_remove(SOC)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Akku",
        data={**STORED, CONF_TEMPLATE: "fronius", CONF_WARRANTY_MWH: 20.0},
    )
    entry.add_to_hass(hass)
    hass.config.language = "en"
    result = await entry.start_reconfigure_flow(hass)
    summary = result["description_placeholders"]["summary"]
    assert summary.startswith(
        "**Set up**\n- Source: template Fronius (GEN24, Modbus TCP)\n"
    )
    assert summary.endswith(
        "**Missing**\n"
        f"- State of charge {SOC} does not exist: for new days no efficiency, "
        "no rest loss, no estimated capacity."
    )


async def test_reconfigure_keeps_its_own_counters(hass: HomeAssistant) -> None:
    """Its own charge counter is no conflict; another entry's is."""
    set_sources(hass)
    hass.states.async_set("sensor.other_charged", "5.0", ENERGY)
    data = STORED
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
    entry = MockConfigEntry(domain=DOMAIN, title="Akku", unique_id=CHARGED, data=STORED)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MANUAL, "charged": "sensor.new_charged"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "sensor.new_charged"
    assert entry.data[CONF_ENTITIES]["charged"] == "sensor.new_charged"
