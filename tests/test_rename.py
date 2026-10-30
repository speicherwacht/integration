"""Following renamed source entities: entry data and unique id."""

from __future__ import annotations

from custom_components.speicherwacht.const import CONF_CAPACITY, CONF_ENTITIES
from custom_components.speicherwacht.rename import (
    renamed_data,
    renamed_unique_id,
    sources,
)

DATA = {
    CONF_ENTITIES: {
        "charged": "sensor.battery_charged",
        "discharged": "sensor.battery_discharged",
        "soc": "sensor.battery_soc",
    },
    CONF_CAPACITY: 10.0,
}


def test_sources() -> None:
    assert sources(DATA) == {
        "sensor.battery_charged",
        "sensor.battery_discharged",
        "sensor.battery_soc",
    }
    assert sources({}) == set()


def test_renamed_data() -> None:
    data = renamed_data(DATA, "sensor.battery_soc", "sensor.byd_soc")
    assert data == {
        CONF_ENTITIES: {
            "charged": "sensor.battery_charged",
            "discharged": "sensor.battery_discharged",
            "soc": "sensor.byd_soc",
        },
        CONF_CAPACITY: 10.0,
    }
    # The original stays as it was (entry data is read-only).
    assert DATA[CONF_ENTITIES]["soc"] == "sensor.battery_soc"


def test_unique_id_is_the_charge_counter() -> None:
    assert renamed_unique_id("sensor.a", "sensor.a", "sensor.b") == "sensor.b"
    assert renamed_unique_id("sensor.c", "sensor.a", "sensor.b") is None
    assert renamed_unique_id(None, "sensor.a", "sensor.b") is None
