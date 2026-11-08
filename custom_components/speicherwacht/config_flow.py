"""Config flow: pick a detected storage or map the entities by hand."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import selector

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
from .day_counters import async_day_counters
from .entity import own_entities
from .model import REQUIRED, Boundary, Signal
from .profiles import TEMPLATES, RegistryEntry
from .runtime import ISSUE_RESETS
from .sisters import TARIFWACHT, TARIFWACHT_URL, tarifwacht_battery
from .summary import MISSING, OWN, UNIT, Source, storage_summary

CONF_SOURCE = "source"
DEFAULT_NAME = "Speicher"
# Counters need long-term statistics with a sum, the state of charge a mean.
COUNTER_STATE_CLASSES = ("total", "total_increasing")
MEASUREMENT = "measurement"
# Hint of the entities step on the own mapping: counters taken from
# Tarifwacht, or a tip when it has none (own step ids, own texts).
HINT_TARIFWACHT = "tarifwacht"
HINT_TARIFWACHT_TIP = "tarifwacht_tip"
# Rarely changed fields of the entities form, in a section that starts
# collapsed (forms got too full, 08.11.2026). Stored flat as ever.
SECTION_MORE = "more"
MORE_FIELDS = (CONF_BOUNDARY, CONF_WARRANTY_MWH)


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


def entities_schema(
    values: dict[str, Any], expected_boundary: str = Boundary.BATTERY.value
) -> vol.Schema:
    """The entities form; `values` prefill it. The section "more" starts
    collapsed unless it holds a warranty or a boundary other than the
    expected one (the template's, else the battery). It is optional without
    a default: the frontend would take a default over its fields' values."""
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

    boundary = values.get(CONF_BOUNDARY) or expected_boundary

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
            vol.Optional(SECTION_MORE): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_BOUNDARY, default=boundary
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[b.value for b in Boundary],
                                translation_key=CONF_BOUNDARY,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                        vol.Optional(
                            CONF_WARRANTY_MWH,
                            description=suggested(CONF_WARRANTY_MWH),
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
                ),
                {
                    "collapsed": not values.get(CONF_WARRANTY_MWH)
                    and boundary == expected_boundary
                },
            ),
        }
    )


def flat_input(
    user_input: dict[str, Any], before: dict[str, Any], expected_boundary: str
) -> dict[str, Any]:
    """The form's input without the section. A section left out of the input
    keeps the values from before (stored or prefilled), never the default."""
    values = {k: v for k, v in user_input.items() if k != SECTION_MORE}
    more = user_input.get(SECTION_MORE)
    if more is None:
        more = {k: before[k] for k in MORE_FIELDS if before.get(k) is not None}
        more.setdefault(CONF_BOUNDARY, expected_boundary)
    values.update(more)
    return values


def validate(hass: HomeAssistant, values: dict[str, Any]) -> str | None:
    """Error key for the form, None if the entities are usable."""
    entities = [values[s.value] for s in REQUIRED]
    if own_entities(hass, entities):
        return "own_entity"
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
        self._hint: str | None = None
        self._tarifwacht_title = ""
        # Counters that drew the day counter warning: sent again unchanged,
        # they are kept (a lifetime counter can restart at 0 now and then).
        self._day_counter_warned: tuple[Any, Any] | None = None

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
                self._suggest_from_tarifwacht()
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
        template = TEMPLATES.get(self._template)
        expected = (template.boundary if template else Boundary.BATTERY).value
        if user_input is not None:
            values = flat_input(user_input, self._prefill, expected)
            error = validate(self.hass, values)
            if error is None and self._counter_in_use(values):
                error = "counter_in_use"
            counters = (values[Signal.CHARGED], values[Signal.DISCHARGED])
            if (
                error is None
                and counters != self._day_counter_warned
                and await self._async_day_counters(values)
            ):
                self._day_counter_warned = counters
                error = "day_counter"
            if error is None:
                return await self._async_finish(values)
            errors["base"] = error
        placeholders: dict[str, str] = {}
        if self.source == SOURCE_RECONFIGURE:
            # The summary of the entry on top (built when the form opens).
            step_id = "reconfigure"
            placeholders["summary"] = await self._async_summary()
        # A source with a known limit: say so next to its entities.
        elif template and template.note:
            step_id = f"entities_note_{template.key}"
        elif self._hint is not None:
            step_id = f"entities_{self._hint}"
            if self._hint == HINT_TARIFWACHT:
                placeholders["tarifwacht"] = self._tarifwacht_title
            else:
                placeholders["tarifwacht_url"] = TARIFWACHT_URL
        else:
            step_id = "entities"
        return self.async_show_form(
            step_id=step_id,
            data_schema=entities_schema(values, expected),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_entities_tarifwacht(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The entities step, with the counters taken from Tarifwacht."""
        return await self.async_step_entities(user_input)

    async def async_step_entities_tarifwacht_tip(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The entities step, with the tip on Tarifwacht."""
        return await self.async_step_entities(user_input)

    def _suggest_from_tarifwacht(self) -> None:
        """Own mapping: the battery counters of Tarifwacht's "PV and battery"
        as suggestions, where the energy settings left both counters empty.

        Copied once, no dependency at runtime. A pair from one source only,
        so that charge and discharge counter never come from two places;
        counters that already belong to a storage entry are not suggested.
        """
        found = tarifwacht_battery(
            self.hass.config_entries.async_entries(TARIFWACHT, include_ignore=False)
        )
        if found is None:
            self._hint = HINT_TARIFWACHT_TIP
            return
        title, counters = found
        if any(self._prefill.get(signal) for signal in counters):
            return
        if self._counter_in_use(counters):
            return
        self._prefill.update(counters)
        self._hint = HINT_TARIFWACHT
        self._tarifwacht_title = title

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The entities form of the entry, with its summary on top."""
        if user_input is None:
            entry = self._get_reconfigure_entry()
            self._template = entry.data.get(CONF_TEMPLATE) or TEMPLATE_MANUAL
            self._prefill = {
                **entry.data[CONF_ENTITIES],
                CONF_CAPACITY: entry.data[CONF_CAPACITY],
                CONF_BOUNDARY: entry.data.get(CONF_BOUNDARY, Boundary.BATTERY.value),
                CONF_WARRANTY_MWH: entry.data.get(CONF_WARRANTY_MWH),
            }
        return await self.async_step_entities(user_input)

    async def _async_summary(self) -> str:
        """What the entry reads and evaluates, and what is missing: from the
        stored data, the current states, the energy settings, Tarifwacht and
        the last analysis (nothing is read from the statistics for it)."""
        entry = self._get_reconfigure_entry()
        entities: dict[str, str] = entry.data[CONF_ENTITIES]
        own = own_entities(self.hass, entities.values())
        sources = {
            signal: _source(self.hass, signal, entities[signal.value], own)
            for signal in REQUIRED
            if entities.get(signal.value)
        }
        template = TEMPLATES.get(entry.data.get(CONF_TEMPLATE) or "")
        counters = {
            s.value: entities.get(s.value) for s in (Signal.CHARGED, Signal.DISCHARGED)
        }
        energy = False
        tarifwacht = None
        if template is None:
            prefill = await async_energy_prefill(self.hass)
            energy = all(prefill.get(s) == e for s, e in counters.items())
            found = tarifwacht_battery(
                self.hass.config_entries.async_entries(TARIFWACHT, include_ignore=False)
            )
            if found is not None and found[1] == counters:
                tarifwacht = found[0]
        runtime = (
            getattr(entry, "runtime_data", None)
            if entry.state is ConfigEntryState.LOADED
            else None
        )
        issue = ir.async_get(self.hass).async_get_issue(
            DOMAIN, f"{entry.entry_id}_{ISSUE_RESETS}"
        )
        return storage_summary(
            entry.data,
            sources,
            template_label=_label(template.label, template.experimental)
            if template
            else None,
            day_values=bool(template and template.day_values),
            energy_dashboard=energy,
            tarifwacht=tarifwacht,
            analysis=getattr(runtime, "analysis", None),
            day_counter=issue is not None
            and issue.active
            and issue.dismissed_version is None,
            language=self.hass.config.language,
        )

    async def _async_day_counters(self, values: dict[str, Any]) -> list[str]:
        """Day counters among the counters; on a reconfigure only among the
        newly chosen ones. Templates with day values expect them."""
        before: dict[str, str] = {}
        key = self._template
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            key = entry.data.get(CONF_TEMPLATE) or key
            before = entry.data.get(CONF_ENTITIES, {})
        template = TEMPLATES.get(key or "")
        if template is not None and template.day_values:
            return []
        return await async_day_counters(
            self.hass,
            [
                values[s.value]
                for s in (Signal.CHARGED, Signal.DISCHARGED)
                if values[s.value] != before.get(s.value)
            ],
        )

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


def _source(
    hass: HomeAssistant, signal: Signal, entity_id: str, own: list[str]
) -> Source:
    """A source entity with its unit, current value and problem."""
    state = hass.states.get(entity_id)
    if signal is Signal.SOC and entity_id in own:
        return Source(entity_id, problem=OWN)
    if state is None:
        return Source(entity_id, problem=MISSING)
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    try:
        value: float | None = float(state.state)
    except ValueError:
        value = None
    usable = unit == PERCENTAGE if signal is Signal.SOC else unit in UNIT_FACTORS
    # An unavailable source may lack its unit for a while.
    known = state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    return Source(entity_id, unit, value, UNIT if known and not usable else None)


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
