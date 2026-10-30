"""Config flow: pick a detected storage or map the entities by hand."""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise
from typing import Any

import voluptuous as vol
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TEMPLATE,
    CONF_WARRANTY_MWH,
    DOMAIN,
    TEMPLATE_MANUAL,
)
from .counter import UNIT_FACTORS
from .model import REQUIRED, Boundary, Signal
from .profiles import TEMPLATES, RegistryEntry

CONF_SOURCE = "source"
# Day counter test: falls by half or more at least twice in this window
# (own assumption; a lifetime counter falls only when it is replaced).
DAY_COUNTER_WINDOW = timedelta(days=4)
DAY_COUNTER_MIN_KWH = 0.1
DEFAULT_NAME = "Speicher"
# Counters need long-term statistics with a sum, the state of charge a mean.
COUNTER_STATE_CLASSES = ("total", "total_increasing")
MEASUREMENT = "measurement"


def _entries(hass: HomeAssistant) -> list[RegistryEntry]:
    platforms = {t.platform for t in TEMPLATES.values()}
    result = []
    for entry in er.async_get(hass).entities.values():
        if entry.platform not in platforms:
            continue
        state = hass.states.get(entry.entity_id)
        result.append(
            RegistryEntry(
                entry.entity_id,
                entry.platform,
                entry.unique_id,
                entry.config_entry_id,
                usable=entry.disabled_by is None
                and state is not None
                and state.state != STATE_UNAVAILABLE,
            )
        )
    return result


def capacity_kwh(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Capacity of a source entity in kWh, None if unusable."""
    state = hass.states.get(entity_id) if entity_id else None
    if state is None:
        return None
    try:
        value = float(state.state)
        factor = UNIT_FACTORS[state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or ""]
    except KeyError, ValueError:
        return None
    return round(value * factor, 2) if value > 0 else None


async def async_energy_prefill(hass: HomeAssistant) -> dict[str, Any]:
    """Counters, state of charge and capacity of the first battery in the
    energy settings (state of charge since 2026.6, capacity since 2026.8);
    read only, empty without them."""
    if "energy" not in hass.config.components:
        return {}
    from homeassistant.components.energy.data import (
        async_get_manager,
    )

    manager = await async_get_manager(hass)
    sources = (manager.data or {}).get("energy_sources", [])
    battery: dict[str, Any] = next(
        (s for s in sources if s.get("type") == "battery"), {}
    )
    prefill: dict[str, Any] = {}
    for signal, key in (
        (Signal.CHARGED, "stat_energy_to"),
        (Signal.DISCHARGED, "stat_energy_from"),
        (Signal.SOC, "stat_soc"),
    ):
        # Statistics of external sources (with ":") have no entity.
        if (stat := battery.get(key)) and ":" not in stat:
            prefill[signal.value] = stat
    if isinstance(capacity := battery.get("capacity"), int | float) and capacity > 0:
        prefill[CONF_CAPACITY] = capacity
    return prefill


async def async_day_counters(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Counters that started anew at least twice in the last four days.

    A day counter (sensor "today", "daily") mapped as lifetime counter would
    book nothing after its first day; its statistics show it.
    """
    if "recorder" not in hass.config.components:
        return []
    end = dt_util.utcnow()
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        end - DAY_COUNTER_WINDOW,
        end,
        set(entity_ids),
        "hour",
        {"energy": "kWh"},
        {"state"},
    )
    found = []
    for entity_id in entity_ids:
        states = [
            r["state"] for r in rows.get(entity_id, []) if r.get("state") is not None
        ]
        drops = sum(
            1
            for before, after in pairwise(states)
            if before >= DAY_COUNTER_MIN_KWH and after < before * 0.5
        )
        if drops >= 2:
            found.append(entity_id)
    return found


def entities_schema(values: dict[str, Any]) -> vol.Schema:
    counter = selector.EntitySelector(
        selector.EntitySelectorConfig(
            filter=selector.EntityFilterSelectorConfig(
                domain="sensor",
                device_class="energy",
                unit_of_measurement=list(UNIT_FACTORS),
            )
        )
    )
    soc = selector.EntitySelector(
        selector.EntitySelectorConfig(
            filter=selector.EntityFilterSelectorConfig(
                domain="sensor", unit_of_measurement=PERCENTAGE
            )
        )
    )

    def suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": values.get(key)}

    return vol.Schema(
        {
            vol.Required(Signal.CHARGED.value, description=suggested(Signal.CHARGED)): (
                counter
            ),
            vol.Required(
                Signal.DISCHARGED.value, description=suggested(Signal.DISCHARGED)
            ): counter,
            vol.Required(Signal.SOC.value, description=suggested(Signal.SOC)): soc,
            vol.Required(CONF_CAPACITY, description=suggested(CONF_CAPACITY)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=1000,
                        step=0.01,
                        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            ),
            vol.Required(
                CONF_BOUNDARY,
                default=values.get(CONF_BOUNDARY, Boundary.BATTERY.value),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[b.value for b in Boundary],
                    translation_key=CONF_BOUNDARY,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_WARRANTY_MWH, description=suggested(CONF_WARRANTY_MWH)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10000,
                    step=0.01,
                    unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def validate(hass: HomeAssistant, values: dict[str, Any]) -> str | None:
    """Error key for the form, None if the entities are usable."""
    entities = [values[s.value] for s in REQUIRED]
    if len(set(entities)) != len(entities):
        return "same_entity"
    for signal in REQUIRED:
        state = hass.states.get(values[signal.value])
        if state is None:
            return "entity_missing"
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        state_class = state.attributes.get("state_class")
        if signal is Signal.SOC:
            if unit != PERCENTAGE:
                return "soc_unit"
            if state_class != MEASUREMENT:
                return "soc_statistics"
        else:
            if unit not in UNIT_FACTORS:
                return "energy_unit"
            if state_class not in COUNTER_STATE_CLASSES:
                return "counter_statistics"
    return None


class SpeicherwachtConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per storage."""

    VERSION = 1

    def __init__(self) -> None:
        self._name = DEFAULT_NAME
        self._template = TEMPLATE_MANUAL
        self._storage: str | None = None
        self._prefill: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entries = _entries(self.hass)
        found: dict[str, tuple[str, str, dict[Signal, str], str | None]] = {}
        hints = []
        for template in TEMPLATES.values():
            for storage, (signals, capacity) in template.detect(entries).items():
                found[f"{template.key}:{storage}"] = (
                    template.key,
                    storage,
                    signals,
                    capacity,
                )
            if template.counter_hint and template.without_counters(entries):
                hints.append(template.key)
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            choice = user_input[CONF_SOURCE]
            if choice in found:
                key, storage, signals, capacity = found[choice]
                template = TEMPLATES[key]
                self._template, self._storage = key, storage
                self._prefill = {s.value: e for s, e in signals.items()}
                self._prefill[CONF_BOUNDARY] = template.boundary.value
                if (kwh := capacity_kwh(self.hass, capacity)) is not None:
                    self._prefill[CONF_CAPACITY] = kwh
            else:
                self._prefill = await async_energy_prefill(self.hass)
            return await self.async_step_entities()
        # The state of charge entity tells two storages of one template apart.
        options = [
            selector.SelectOptionDict(
                value=choice,
                label=_label(TEMPLATES[key].label, TEMPLATES[key].experimental)
                + f" – {signals[Signal.SOC]}",
            )
            for choice, (key, _storage, signals, _capacity) in found.items()
        ]
        options.append(
            selector.SelectOptionDict(value=TEMPLATE_MANUAL, label=TEMPLATE_MANUAL)
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self._name): str,
                vol.Required(
                    CONF_SOURCE, default=options[0]["value"]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        translation_key=CONF_SOURCE,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        # A source whose counters are switched off: say how to get them.
        step_id = f"user_hint_{hints[0]}" if hints else "user"
        return self.async_show_form(step_id=step_id, data_schema=schema)

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        values = self._prefill
        if user_input is not None:
            values = user_input
            error = validate(self.hass, values)
            if error is None and self._counter_in_use(values):
                error = "counter_in_use"
            if error is None and await async_day_counters(
                self.hass, [values[Signal.CHARGED], values[Signal.DISCHARGED]]
            ):
                error = "day_counter"
            if error is None:
                return await self._async_finish(values)
            errors["base"] = error
        # A source with a known limit: say so next to its entities.
        template = TEMPLATES.get(self._template)
        step_id = (
            f"entities_note_{template.key}"
            if template and template.note
            else "entities"
        )
        return self.async_show_form(
            step_id=step_id, data_schema=entities_schema(values), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        self._prefill = {
            **entry.data[CONF_ENTITIES],
            CONF_CAPACITY: entry.data[CONF_CAPACITY],
            CONF_BOUNDARY: entry.data.get(CONF_BOUNDARY, Boundary.BATTERY.value),
            CONF_WARRANTY_MWH: entry.data.get(CONF_WARRANTY_MWH),
        }
        return await self.async_step_entities()

    def _counter_in_use(self, values: dict[str, Any]) -> bool:
        """The charge counter already belongs to another storage entry."""
        own = (
            self._get_reconfigure_entry().entry_id
            if self.source == SOURCE_RECONFIGURE
            else None
        )
        return any(
            entry.data.get(CONF_ENTITIES, {}).get(Signal.CHARGED.value)
            == values[Signal.CHARGED]
            for entry in self._async_current_entries(include_ignore=False)
            if entry.entry_id != own
        )

    async def _async_finish(self, values: dict[str, Any]) -> ConfigFlowResult:
        data = {
            CONF_ENTITIES: {s.value: values[s.value] for s in REQUIRED},
            CONF_CAPACITY: float(values[CONF_CAPACITY]),
            CONF_BOUNDARY: values[CONF_BOUNDARY],
            CONF_WARRANTY_MWH: values.get(CONF_WARRANTY_MWH),
        }
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            # Another charge counter identifies the storage from now on,
            # unless an older entry still carries that id.
            unique_id = values[Signal.CHARGED.value]
            holder = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            # The update listener reloads the entry.
            return self.async_update_and_abort(
                entry,
                unique_id=unique_id if holder in (None, entry) else entry.unique_id,
                data={**entry.data, **data},
            )
        # The charge counter identifies the storage, whichever way it was
        # chosen (template or own mapping).
        await self.async_set_unique_id(values[Signal.CHARGED.value])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._name,
            data={CONF_NAME: self._name, CONF_TEMPLATE: self._template, **data},
        )


def _label(label: str, experimental: bool) -> str:
    return f"{label} (beta)" if experimental else label


async def _async_step_user_hint(
    self: SpeicherwachtConfigFlow, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """The first step again, shown with the counter hint of a template."""
    return await self.async_step_user(user_input)


async def _async_step_entities_note(
    self: SpeicherwachtConfigFlow, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """The entities step, shown with the note of a template."""
    return await self.async_step_entities(user_input)


# One step id per template with a counter hint or a note (own description).
for _template in TEMPLATES.values():
    if _template.counter_hint:
        setattr(
            SpeicherwachtConfigFlow,
            f"async_step_user_hint_{_template.key}",
            _async_step_user_hint,
        )
    if _template.note:
        setattr(
            SpeicherwachtConfigFlow,
            f"async_step_entities_note_{_template.key}",
            _async_step_entities_note,
        )
