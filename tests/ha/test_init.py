"""Setup, figures from recorded statistics, repair issues, unload."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.speicherwacht.const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    CONF_WARRANTY_MWH,
    DOMAIN,
)

from ..sim import SUMMER_DAY, simulate
from .conftest import CHARGED, DISCHARGED, SOC, set_sources

JUNE = date(2026, 6, 1)
# 30 June, 23:30 in Berlin: the simulated month is still the current one.
NOW = datetime(2026, 6, 30, 21, 30, tzinfo=UTC)
SUNNY_DAY = {**SUMMER_DAY, **dict.fromkeys(range(9, 15), 2.0)}
# Lifetime readings before the simulated month (commissioned earlier).
CHARGED_BEFORE = 2000.0
DISCHARGED_BEFORE = 1800.0


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_mock: Recorder, enable_custom_integrations: None
) -> None:
    """The recorder must be set up before `hass` (listed first)."""


def import_statistics(hass: HomeAssistant) -> float:
    """A month of a 10 kWh battery with 90 % efficiency; returns the last
    discharge reading."""
    hours = simulate(JUNE, 30, rest_watts=0.0, profile=lambda _d: SUNNY_DAY)
    charged, discharged, soc = [], [], []
    into, out = CHARGED_BEFORE, DISCHARGED_BEFORE
    for hour in hours:
        into += hour.charged or 0.0
        out += hour.discharged or 0.0
        charged.append(StatisticData(start=hour.start, state=into, sum=into))
        discharged.append(StatisticData(start=hour.start, state=out, sum=out))
        soc.append(
            StatisticData(
                start=hour.start, mean=hour.soc, min=hour.soc_min, max=hour.soc_max
            )
        )
    for statistic_id, rows in ((CHARGED, charged), (DISCHARGED, discharged)):
        async_import_statistics(
            hass,
            StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=None,
                source="recorder",
                statistic_id=statistic_id,
                unit_class="energy",
                unit_of_measurement="kWh",
            ),
            rows,
        )
    async_import_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=None,
            source="recorder",
            statistic_id=SOC,
            unit_class=None,
            unit_of_measurement="%",
        ),
        soc,
    )
    return out


async def setup_entry(hass: HomeAssistant, **data) -> MockConfigEntry:
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
            **data,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def state(hass: HomeAssistant, entry: MockConfigEntry, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id, key
    return hass.states.get(entity_id)


@pytest.mark.freeze_time(NOW)
async def test_figures_from_statistics(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    last_discharge = import_statistics(hass)
    await async_wait_recording_done(hass)
    entry = await setup_entry(hass, **{CONF_WARRANTY_MWH: 30.0})
    first = state(hass, entry, "efficiency_month")
    assert first.state == "unknown"
    assert first.attributes["reason"] == "not_analysed_yet"

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    month = state(hass, entry, "efficiency_month")
    assert float(month.state) == pytest.approx(90.0, abs=0.5)
    assert month.attributes["operating_days"] == 30
    assert month.attributes["boundary"] == "battery"
    assert month.attributes["reason"] is None
    assert float(state(hass, entry, "efficiency_total").state) == pytest.approx(
        90.0, abs=0.5
    )
    # Lifetime: the reading of the discharge counter, not only June.
    cycles = state(hass, entry, "full_cycles_total")
    assert float(cycles.state) == pytest.approx(last_discharge / 10.0, abs=0.1)
    warranty = state(hass, entry, "warranty_used")
    assert float(warranty.state) == pytest.approx(last_discharge / 30000 * 100, abs=0.1)
    capacity = state(hass, entry, "capacity_estimate")
    assert float(capacity.state) == pytest.approx(10.0, rel=0.03)
    assert capacity.attributes["share_of_data_sheet_percent"] == pytest.approx(
        100, abs=3
    )
    # The day sensor exists but is disabled by default.
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_efficiency_today"
    )
    assert er.async_get(hass).async_get(entity_id).disabled


async def test_without_warranty_no_warranty_sensor(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_warranty_used"
        )
        is None
    )


async def test_missing_source_gives_a_repair_issue(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    hass.states.async_remove(SOC)
    now = datetime.now(UTC)
    for minutes in (11, 16):
        await hass.async_block_till_done()
        async_fire_time_changed(hass, now + timedelta(minutes=minutes))
        await hass.async_block_till_done()
    issue_id = f"{entry.entry_id}_missing_entity"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(SOC, "40.0", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, now + timedelta(minutes=21))
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_unload_and_remove(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(entry.entry_id)
