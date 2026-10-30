"""Problem sensors of the health check (docs/GESUNDHEITSCHECK.md).

On when the storage behaves conspicuously; unknown with a `reason` while the
data do not allow a judgement. The figures behind the decision are
attributes, rounded to keep the recorder quiet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import StorageEntity
from .health import Check, Health

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SpeicherwachtConfigEntry

CHECKS: dict[str, Callable[[Health], Check]] = {
    "efficiency_drop": lambda h: h.efficiency_drop,
    "capacity_low": lambda h: h.capacity_low,
    "rest_loss_high": lambda h: h.rest_loss_high,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeicherwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(ProblemSensor(entry, key) for key in CHECKS)


def _rounded(value: Any) -> Any:
    return round(value, 1) if isinstance(value, float) else value


class ProblemSensor(StorageEntity, BinarySensorEntity):
    """One check of the storage's health."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: SpeicherwachtConfigEntry, key: str) -> None:
        super().__init__(entry, key)
        self._check = CHECKS[key]

    def _result(self) -> Check | None:
        health = self.runtime.health
        return None if health is None else self._check(health)

    @property
    def is_on(self) -> bool | None:
        result = self._result()
        return None if result is None else result.problem

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._result()
        if result is None:
            return {"reason": self.runtime.problem}
        return {
            **{key: _rounded(value) for key, value in result.details.items()},
            "reason": result.reason,
        }
