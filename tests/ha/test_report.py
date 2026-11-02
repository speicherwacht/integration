"""The action "report" without a recorder: registration and input checks.

The figures from recorded statistics are tested in test_init.py.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.speicherwacht.const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    DOMAIN,
)

from .conftest import CHARGED, DISCHARGED, SOC, set_sources


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
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
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def call(hass: HomeAssistant, entry_id: str, **data: str):
    return await hass.services.async_call(
        DOMAIN,
        "report",
        {"config_entry": entry_id, **data},
        blocking=True,
        return_response=True,
    )


async def test_report_is_registered_and_checks_its_input(
    hass: HomeAssistant,
) -> None:
    entry = await setup_entry(hass)
    assert hass.services.has_service(DOMAIN, "report")

    with pytest.raises(ServiceValidationError) as err:
        await call(
            hass, entry.entry_id, start="2026-01-15 08:00:00", end="2026-01-15 07:00:00"
        )
    assert err.value.translation_key == "start_after_end"
    # The test instance has no recorder: the report says so instead of 0.
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, entry.entry_id)
    assert err.value.translation_key == "no_recorder"
    # An entry of another integration or none at all.
    with pytest.raises(ServiceValidationError):
        await call(hass, "not_an_entry")


async def test_report_needs_a_loaded_entry(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await call(hass, entry.entry_id)
