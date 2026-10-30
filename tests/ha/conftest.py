"""Fixtures for Home Assistant tests.

pytest-homeassistant-custom-component needs Linux (fcntl). Without it (local
Windows development) these tests are not collected; CI runs them.
All values are made up.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

CHARGED = "sensor.battery_charged"
DISCHARGED = "sensor.battery_discharged"
SOC = "sensor.battery_soc"

ENERGY = {
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "state_class": "total_increasing",
}
PERCENT = {
    "unit_of_measurement": "%",
    "device_class": "battery",
    "state_class": "measurement",
}


def set_sources(hass: Any, **changes: dict[str, Any]) -> None:
    """Source entities with usable units and state classes."""
    hass.states.async_set(CHARGED, "1000.0", changes.get("charged", ENERGY))
    hass.states.async_set(DISCHARGED, "900.0", changes.get("discharged", ENERGY))
    hass.states.async_set(SOC, "50.0", changes.get("soc", PERCENT))


if importlib.util.find_spec("pytest_homeassistant_custom_component") is None:
    collect_ignore_glob = ["test_*.py"]
else:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
        """Allow loading custom_components/speicherwacht in every test."""
