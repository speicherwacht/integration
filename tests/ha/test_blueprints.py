"""The blueprint as a real automation: bell, phone, more actions, texts.

All values are made up.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

BLUEPRINT = (
    Path(__file__).parent.parent.parent
    / "blueprints"
    / "automation"
    / "speicherwacht"
    / "befund_melden.yaml"
)
EFFICIENCY = "binary_sensor.heimspeicher_wirkungsgrad_unter_vorjahr"
CAPACITY = "binary_sensor.heimspeicher_kapazitat_gesunken"
DROP = {
    "friendly_name": "Heimspeicher Wirkungsgrad unter Vorjahr",
    "device_class": "problem",
    "current_percent": 88.4,
    "previous_year_percent": 92.0,
    "current_days": 27,
    "previous_year_days": 28,
    "threshold_points": 3.0,
    "drop_points": 3.6,
    "reason": None,
}
LOW = {
    "friendly_name": "Heimspeicher Kapazität gesunken",
    "device_class": "problem",
    "estimate_kwh": 7.6,
    "year_ago_kwh": None,
    "data_sheet_kwh": 10.0,
    "end_of_life_percent": 80.0,
    "drop_threshold_points": 10.0,
    "share_percent": 76.0,
    "reason": None,
}
DAY = 24 * 3600


async def setup(
    hass: HomeAssistant, off_since: float, **inputs: Any
) -> tuple[list[ServiceCall], list[ServiceCall]]:
    """Efficiency off since `off_since` seconds ago, capacity unknown."""
    hass.states.async_set(EFFICIENCY, "off", DROP, timestamp=time.time() - off_since)
    hass.states.async_set(CAPACITY, STATE_UNKNOWN, LOW)
    blueprint = Blueprint(
        load_yaml(BLUEPRINT),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    config = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": BLUEPRINT.name,
                "input": {"checks": [EFFICIENCY, CAPACITY], **inputs},
            }
        },
    ).async_substitute()
    config.pop("use_blueprint", None)
    created = async_mock_service(hass, "persistent_notification", "create")
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    return created, phone


async def change(hass: HomeAssistant, entity: str, state: str, attrs: dict) -> None:
    hass.states.async_set(entity, state, attrs)
    await hass.async_block_till_done()


async def test_bell_and_phone_in_german(hass: HomeAssistant) -> None:
    created, phone = await setup(hass, 2 * DAY, notify_action="notify.mobile_app_phone")
    await change(hass, EFFICIENCY, "on", DROP)
    assert len(created) == 1
    assert created[0].data["notification_id"] == f"speicherwacht_{EFFICIENCY}"
    assert created[0].data["title"] == "Speicherwacht: auffällig"
    message = (
        "Heimspeicher Wirkungsgrad unter Vorjahr: letzte 30 Tage 88,4 % statt "
        "92,0 % im Vorjahr (3,6 Punkte weniger)"
    )
    assert created[0].data["message"] == message
    assert [(c.data["title"], c.data["message"]) for c in phone] == [
        ("Speicherwacht: auffällig", message)
    ]

    # Unknown after a restart -> conspicuous: the bell again, not the phone.
    await change(hass, CAPACITY, "on", LOW)
    assert created[-1].data["message"] == (
        "Heimspeicher Kapazität gesunken: geschätzt 7,6 kWh, 76 % des "
        "Datenblatts (Grenze 80 %)"
    )
    assert len(phone) == 1

    # Fine again: only in the bell.
    await change(hass, EFFICIENCY, "off", DROP)
    assert created[-1].data["notification_id"] == f"speicherwacht_{EFFICIENCY}"
    assert created[-1].data["title"] == "Speicherwacht: wieder in Ordnung"
    assert created[-1].data["message"] == (
        "Heimspeicher Wirkungsgrad unter Vorjahr: wieder in Ordnung"
    )
    assert len(phone) == 1

    # Back on within the day (a value at the limit): the bell, not the phone.
    await change(hass, EFFICIENCY, "on", DROP)
    assert created[-1].data["title"] == "Speicherwacht: auffällig"
    assert len(phone) == 1


async def test_phone_needs_a_day_in_order(hass: HomeAssistant) -> None:
    created, phone = await setup(hass, 3600, notify_action="notify.mobile_app_phone")
    await change(hass, EFFICIENCY, "on", DROP)
    assert len(created) == 1
    assert phone == []


async def test_bell_only_in_english(hass: HomeAssistant) -> None:
    created, phone = await setup(hass, 2 * DAY, language="en")
    await change(hass, EFFICIENCY, "on", DROP)
    assert created[0].data["title"] == "Speicherwacht: conspicuous"
    assert created[0].data["message"] == (
        "Heimspeicher Wirkungsgrad unter Vorjahr: last 30 days 88.4 % instead of "
        "92.0 % last year (3.6 points less)"
    )
    await change(hass, EFFICIENCY, "off", DROP)
    assert created[-1].data["title"] == "Speicherwacht: fine again"
    assert created[-1].data["message"] == (
        "Heimspeicher Wirkungsgrad unter Vorjahr: fine again"
    )
    assert phone == []


def add_device(hass: HomeAssistant, domain: str, name: str, entity: str = "") -> str:
    """A device of `domain` named `name`, optionally with `entity` on it."""
    entry = MockConfigEntry(domain=domain, title=name)
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(domain, name)}, name=name
    )
    if entity:
        domain_, object_id = entity.split(".")
        registered = er.async_get(hass).async_get_or_create(
            domain_,
            domain,
            object_id,
            suggested_object_id=object_id,
            config_entry=entry,
            device_id=device.id,
        )
        assert registered.entity_id == entity
        # integration_entities() reads the loaded entities.
        entity_sources(hass)[entity] = {
            "domain": domain,
            "config_entry": entry.entry_id,
        }
    return device.id


def second_storage(hass: HomeAssistant) -> None:
    """Another battery with checks, so the title names the device."""
    add_device(
        hass,
        "speicherwacht",
        "Balkonspeicher",
        "binary_sensor.balkonspeicher_ruheverlust_hoch",
    )


async def test_one_storage_no_name_in_the_title(hass: HomeAssistant) -> None:
    add_device(hass, "speicherwacht", "Heimspeicher", EFFICIENCY)
    created, _ = await setup(hass, 2 * DAY)
    await change(hass, EFFICIENCY, "on", DROP)
    assert created[0].data["title"] == "Speicherwacht: auffällig"


async def test_device_name_in_the_title(hass: HomeAssistant) -> None:
    add_device(hass, "speicherwacht", "Heimspeicher", EFFICIENCY)
    second_storage(hass)
    created, _ = await setup(hass, 2 * DAY)
    await change(hass, EFFICIENCY, "on", DROP)
    assert created[0].data["title"] == "Speicherwacht · Heimspeicher: auffällig"
    await change(hass, EFFICIENCY, "off", DROP)
    assert created[-1].data["title"] == (
        "Speicherwacht · Heimspeicher: wieder in Ordnung"
    )


async def test_phone_device_and_more_actions(hass: HomeAssistant) -> None:
    add_device(hass, "speicherwacht", "Heimspeicher", EFFICIENCY)
    second_storage(hass)
    phone_id = add_device(hass, "mobile_app", "Pixel von Max")
    app = async_mock_service(hass, "notify", "mobile_app_pixel_von_max")
    extra = async_mock_service(hass, "test", "extra")
    created, phone = await setup(
        hass,
        2 * DAY,
        language="en",
        notify_device=phone_id,
        extra_actions=[
            {"action": "test.extra", "data": {"text": "{{ title }}: {{ message }}"}}
        ],
    )
    await change(hass, EFFICIENCY, "on", DROP)
    title = "Speicherwacht · Heimspeicher: conspicuous"
    message = (
        "Heimspeicher Wirkungsgrad unter Vorjahr: last 30 days 88.4 % instead of "
        "92.0 % last year (3.6 points less)"
    )
    assert [(c.data["title"], c.data["message"]) for c in app] == [(title, message)]
    assert [c.data["text"] for c in extra] == [f"{title}: {message}"]
    assert phone == []

    # Unknown after a restart -> conspicuous: same rule as the phone.
    await change(hass, CAPACITY, "on", LOW)
    assert len(app) == 1
    assert len(extra) == 1

    # Fine again: only in the bell.
    await change(hass, EFFICIENCY, "off", DROP)
    assert created[-1].data["title"] == "Speicherwacht · Heimspeicher: fine again"
    assert len(app) == 1
    assert len(extra) == 1


async def test_more_actions_need_a_day_in_order(hass: HomeAssistant) -> None:
    extra = async_mock_service(hass, "test", "extra")
    created, _ = await setup(hass, 3600, extra_actions=[{"action": "test.extra"}])
    await change(hass, EFFICIENCY, "on", DROP)
    assert len(created) == 1
    assert extra == []
