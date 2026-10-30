"""Sensors of one storage, all from the hourly analysis.

Values are rounded to the shown precision and the long lists stay out of the
recorder, so a state is only written when the figure really changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.util import dt as dt_util

from .analysis import Analysis, Efficiency
from .days import Period, local_midnight
from .entity import StorageEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SpeicherwachtConfigEntry
    from .runtime import StorageRuntime


@dataclass(frozen=True, kw_only=True)
class StorageSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Analysis, StorageRuntime], float | None]
    attrs_fn: Callable[[Analysis, StorageRuntime], dict[str, Any]] = lambda _a, _r: {}
    # Starts anew each calendar year (last_reset at local 1 January).
    yearly: bool = False


def _kwh(value: float) -> float:
    return round(value, 2)


def _efficiency(period: Period) -> Callable[[Analysis, StorageRuntime], float | None]:
    def value(analysis: Analysis, _runtime: StorageRuntime) -> float | None:
        ratio = analysis.efficiency[period].ratio
        return None if ratio is None else round(ratio * 100, 1)

    return value


def _efficiency_attrs(
    period: Period,
) -> Callable[[Analysis, StorageRuntime], dict[str, Any]]:
    def attrs(analysis: Analysis, runtime: StorageRuntime) -> dict[str, Any]:
        result: Efficiency = analysis.efficiency[period]
        return {
            "charged_kwh": _kwh(result.charged),
            "discharged_kwh": _kwh(result.discharged),
            "stored_change_kwh": _kwh(result.stored),
            "operating_days": result.operating_days,
            "rest_days": result.rest_days,
            "rest_loss_kwh": _kwh(result.rest_loss),
            "days_without_soc": result.days_without_soc,
            "incomplete_days": result.incomplete_days,
            "since": result.first_day.isoformat() if result.first_day else None,
            "boundary": runtime.boundary.value,
            "reason": result.reason,
        }

    return attrs


def _since(analysis: Analysis) -> str | None:
    return analysis.first_day.isoformat() if analysis.first_day else None


def _rounded(kwh: float | None) -> float | None:
    return None if kwh is None else _kwh(kwh)


def _lifetime_cycles(_analysis: Analysis, runtime: StorageRuntime) -> float | None:
    """Equivalent full cycles since commissioning: discharged energy per
    capacity (warranties count the energy discharged, docs/ENTWICKLUNG.md)."""
    discharged = runtime.lifetime_discharged
    return None if discharged is None else round(discharged / runtime.capacity, 1)


def _warranty_used(_analysis: Analysis, runtime: StorageRuntime) -> float | None:
    discharged = runtime.lifetime_discharged
    if discharged is None or not runtime.warranty_kwh:
        return None
    return round(discharged / runtime.warranty_kwh * 100, 1)


WARRANTY = StorageSensorDescription(
    key="warranty_used",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    value_fn=_warranty_used,
    attrs_fn=lambda _a, r: {
        "discharged_lifetime_kwh": _rounded(r.lifetime_discharged),
        "warranty_mwh": (r.warranty_kwh or 0) / 1000,
    },
)


EFFICIENCY = [
    StorageSensorDescription(
        key=f"efficiency_{period.value}",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=period is not Period.TODAY,
        value_fn=_efficiency(period),
        attrs_fn=_efficiency_attrs(period),
    )
    for period in Period
]

DESCRIPTIONS = [
    *EFFICIENCY,
    StorageSensorDescription(
        key="full_cycles_total",
        # Not total_increasing: a new capacity lowers the value, which must
        # not count as a restart of the counter.
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=_lifetime_cycles,
        attrs_fn=lambda a, r: {
            "discharged_lifetime_kwh": _rounded(r.lifetime_discharged),
            "charged_in_statistics_kwh": _kwh(a.charged_total),
            "discharged_in_statistics_kwh": _kwh(a.discharged_total),
            "statistics_since": _since(a),
            "capacity_kwh": r.capacity,
        },
    ),
    StorageSensorDescription(
        key="full_cycles_year",
        state_class=SensorStateClass.TOTAL,
        yearly=True,
        suggested_display_precision=1,
        value_fn=lambda a, _r: round(a.cycles_year, 1),
        attrs_fn=lambda a, _r: {"statistics_since": _since(a)},
    ),
    StorageSensorDescription(
        key="rest_loss",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda a, _r: None if a.rest.watts is None else round(a.rest.watts),
        attrs_fn=lambda a, _r: {
            "rest_hours": round(a.rest.hours),
            "raw_watts": None
            if a.rest.raw_watts is None
            else round(a.rest.raw_watts, 1),
            "reason": a.rest.reason,
        },
    ),
    StorageSensorDescription(
        key="capacity_estimate",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda a, _r: None if a.capacity.kwh is None else _kwh(a.capacity.kwh),
        attrs_fn=lambda a, r: {
            "share_of_data_sheet_percent": (
                None
                if a.capacity.kwh is None
                else round(a.capacity.kwh / r.capacity * 100, 1)
            ),
            "data_sheet_kwh": r.capacity,
            "samples_kwh": [_kwh(s) for s in a.capacity.samples],
            "reason": a.capacity.reason,
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeicherwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    descriptions = list(DESCRIPTIONS)
    if entry.runtime_data.warranty_kwh:
        descriptions.append(WARRANTY)
    async_add_entities(StorageSensor(entry, d) for d in descriptions)


class StorageSensor(StorageEntity, SensorEntity):
    """A figure of the storage; unknown until the first analysis."""

    entity_description: StorageSensorDescription
    _unrecorded_attributes = frozenset({"samples_kwh"})

    def __init__(
        self, entry: SpeicherwachtConfigEntry, description: StorageSensorDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        analysis = self.runtime.analysis
        if analysis is None:
            return None
        return self.entity_description.value_fn(analysis, self.runtime)

    @property
    def last_reset(self) -> datetime | None:
        if not self.entity_description.yearly:
            return None
        today = dt_util.now(self.runtime.tz).date()
        return local_midnight(today.replace(month=1, day=1), self.runtime.tz)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        analysis = self.runtime.analysis
        if analysis is None:
            return {"reason": self.runtime.problem}
        return self.entity_description.attrs_fn(analysis, self.runtime)
