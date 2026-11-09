"""The card: the websocket command hands it months and repair issues, and
the integration serves the card file itself."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.speicherwacht.const import DOMAIN

from ..sim import simulate
from .test_report import setup_entry


async def test_months_and_issues_for_the_card(
    hass: HomeAssistant, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    # Late June 2026: the simulated months are the latest two of twelve.
    freezer.move_to("2026-06-30 20:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Berlin")
    assert await async_setup_component(hass, "websocket_api", {})
    entry = await setup_entry(hass)
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    client = await hass_ws_client(hass)

    # Before the first analysis: no months yet, no issues.
    await client.send_json(
        {"id": 1, "type": "speicherwacht/card", "device_id": device.id}
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"] == {"months": None, "issues": []}

    # From the hours read anyway; computed once per analysis.
    runtime = entry.runtime_data
    runtime.series = SimpleNamespace(hours=simulate(date(2026, 5, 20), 42))
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry.entry_id}_counter_soc_mismatch",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="counter_soc_mismatch",
    )
    await client.send_json(
        {"id": 2, "type": "speicherwacht/card", "device_id": device.id}
    )
    reply = await client.receive_json()
    assert reply["success"]
    months = reply["result"]["months"]
    assert [m["month"] for m in months][-2:] == ["2026-05", "2026-06"]
    assert len(months) == 12
    assert months[-1]["days"] == 30
    assert {
        "month",
        "days",
        "charged_kwh",
        "discharged_kwh",
        "efficiency_percent",
    } <= set(months[-1])
    assert reply["result"]["issues"] == ["counter_soc_mismatch"]
    assert runtime._months is not None
    cached = runtime._months[1]
    assert await runtime.async_months() is cached

    # An ignored issue is left out.
    ir.async_ignore_issue(hass, DOMAIN, f"{entry.entry_id}_counter_soc_mismatch", True)
    await client.send_json(
        {"id": 3, "type": "speicherwacht/card", "device_id": device.id}
    )
    reply = await client.receive_json()
    assert reply["result"]["issues"] == []

    await client.send_json({"id": 4, "type": "speicherwacht/card", "device_id": "nope"})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "not_found"


async def test_card_file_is_served(hass: HomeAssistant, hass_client) -> None:
    """The integration serves its card file itself."""
    assert await async_setup_component(hass, "http", {})
    await setup_entry(hass)
    client = await hass_client()
    response = await client.get("/speicherwacht/speicherwacht-card.js")
    assert response.status == 200
    assert "speicherwacht-card-editor" in await response.text()
