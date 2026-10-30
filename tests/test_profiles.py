"""Templates against the fixtures: which entity is which signal."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.speicherwacht.model import Signal
from custom_components.speicherwacht.profiles import (
    ANKER_SOLIX,
    ANKER_SOLIX_OFFICIAL,
    FRONIUS,
    GOODWE,
    HUAWEI_SOLAR,
    MARSTEK_MODBUS,
    SIGEN,
    SOLAREDGE_MODBUS_MULTI,
    SOLARMAN,
    SOLAX_MODBUS,
    SUNGROW_MODBUS_YAML,
    TEMPLATES,
    VICTRON_GX,
    ZENDURE_HA,
    RegistryEntry,
)

from .conftest import load_fixture


def entries(fixture: dict[str, Any], **changes: Any) -> list[RegistryEntry]:
    return [
        RegistryEntry(
            entity_id=e["entity_id"],
            platform=fixture["platform"],
            unique_id=e["unique_id"],
            config_entry_id=fixture.get("config_entry_id"),
            usable=not e.get("disabled_by_default", False),
        )._replace(**changes)
        for e in fixture["entities"]
    ]


def test_fronius_finds_the_battery_counters_not_the_mppt_copies() -> None:
    fixture = load_fixture("fronius_gen24_byd_hvs.json")
    found = FRONIUS.detect(entries(fixture))
    assert list(found) == [fixture["config_entry_id"]]
    signals, capacity = found[fixture["config_entry_id"]]
    assert signals == {
        Signal.CHARGED: "sensor.fronius_gen24_gesamtenergie_batterieaufladung",
        Signal.DISCHARGED: "sensor.fronius_gen24_gesamtenergie_batterieentladung",
        Signal.SOC: "sensor.byd_battery_box_premium_hv_ladezustand",
    }
    assert capacity == "sensor.byd_battery_box_premium_hv_ausgelegte_kapazitat"


def test_fronius_without_modbus_has_no_counters() -> None:
    """Before Home Assistant 2026.9 (or Modbus off) only the SoC exists."""
    fixture = load_fixture("fronius_gen24_byd_hvs.json")
    without = [e for e in entries(fixture) if "-modbus-" not in e.unique_id]
    assert FRONIUS.detect(without) == {}


def test_huawei_uses_the_sums_not_the_stacks() -> None:
    fixture = load_fixture("huawei_solar_luna2000.json")
    # Disabled entities count here: the user may have enabled them.
    found = HUAWEI_SOLAR.detect(entries(fixture, usable=True))
    signals, capacity = found["HV2299990001"]
    assert signals == {
        Signal.CHARGED: "sensor.batteries_total_charge",
        Signal.DISCHARGED: "sensor.batteries_total_discharge",
        Signal.SOC: "sensor.batteries_state_of_capacity",
    }
    assert capacity == "sensor.batteries_rated_capacity"


def test_huawei_capacity_disabled_by_default() -> None:
    fixture = load_fixture("huawei_solar_luna2000.json")
    (signals, capacity), *_ = HUAWEI_SOLAR.detect(entries(fixture)).values()
    assert capacity is None
    assert Signal.CHARGED in signals


@pytest.mark.parametrize(
    "fixture_name", ["solarman_deye_hybrid.json", "solarman_deye_p3.json"]
)
def test_solarman_takes_the_lifetime_counters_and_the_soc(fixture_name: str) -> None:
    fixture = load_fixture(fixture_name)
    found = SOLARMAN.detect(entries(fixture))
    (storage,) = found
    assert storage == fixture["config_entry_id"].lower()
    signals, capacity = found[storage]
    assert signals == {
        Signal.CHARGED: "sensor.inverter_total_battery_charge",
        Signal.DISCHARGED: "sensor.inverter_total_battery_discharge",
        Signal.SOC: "sensor.inverter_battery",
    }
    assert capacity is None  # the sensor is an estimate of solarman


def test_anker_solix_with_mqtt_counters() -> None:
    fixture = load_fixture("anker_solix_solarbank.json")
    found = ANKER_SOLIX.detect(entries(fixture))
    signals, capacity = found["azv1k7q3p9m2x4t8c"]
    assert signals == {
        Signal.CHARGED: "sensor.solarbank_3_e2700_pro_energie_geladen",
        Signal.DISCHARGED: "sensor.solarbank_3_e2700_pro_energie_entladen",
        Signal.SOC: "sensor.solarbank_3_e2700_pro_ladestand",
    }
    assert capacity == "number.solarbank_3_e2700_pro_akku_kapazitat"
    # The system ("site") has its own state of charge but no counters.
    assert set(found) == {"azv1k7q3p9m2x4t8c"}


def test_anker_solix_default_options_need_the_hint() -> None:
    fixture = load_fixture("anker_solix_solarbank2_default.json")
    assert ANKER_SOLIX.detect(entries(fixture)) == {}
    assert ANKER_SOLIX.without_counters(entries(fixture)) == ["apc8r2d5f7h9j1k3l"]


def test_anker_solix_official() -> None:
    fixture = load_fixture("anker_solix_official_sb4.json")
    (signals, capacity), *_ = ANKER_SOLIX_OFFICIAL.detect(entries(fixture)).values()
    assert signals[Signal.SOC].endswith("_soc")
    assert signals[Signal.CHARGED].endswith("_batterie_ladeenergie")
    assert capacity == "sensor.anker_solix_solarbank_4_e5000_pro_akkukapazitat"


@pytest.mark.parametrize("template", TEMPLATES.values())
def test_other_platforms_are_ignored(template) -> None:
    fixture = load_fixture("fronius_gen24_byd_hvs.json")
    assert template.detect(entries(fixture, platform="other")) == {}


def test_goodwe_et_uses_lifetime_not_day_counters() -> None:
    fixture = load_fixture("goodwe_et.json")
    (storage, (signals, capacity)), *_ = GOODWE.detect(entries(fixture)).items()
    assert storage == "9010KETU229W9999"
    assert signals == {
        Signal.CHARGED: "sensor.goodwe_total_battery_charge",
        Signal.DISCHARGED: "sensor.goodwe_total_battery_discharge",
        Signal.SOC: "sensor.goodwe_battery_state_of_charge",
    }
    assert capacity is None


def test_goodwe_es_without_counters_gets_the_hint() -> None:
    fixture = load_fixture("goodwe_et.json")
    soc_only = [e for e in entries(fixture) if "e_bat_" not in e.unique_id]
    assert GOODWE.detect(soc_only) == {}
    assert GOODWE.without_counters(soc_only) == ["9010KETU229W9999"]


def test_victron_battery_monitor_but_not_can_bms_or_system() -> None:
    fixture = load_fixture("victron_gx_smartshunt.json")
    found = VICTRON_GX.detect(entries(fixture))
    assert list(found) == ["c0619ab9f0e1_battery_279"]
    signals, capacity = found["c0619ab9f0e1_battery_279"]
    assert signals[Signal.CHARGED].endswith("_charged_energy")
    assert capacity is None  # Ah only
    assert VICTRON_GX.without_counters(entries(fixture)) == ["c0619ab9f0e1_battery_512"]


def test_solaredge_one_storage_per_battery() -> None:
    fixture = load_fixture("solaredge_modbus_multi_storedge.json")
    found = SOLAREDGE_MODBUS_MULTI.detect(entries(fixture, usable=True))
    assert sorted(found) == [
        "SE10K-RWB48BEN4_7E1A2B3C_B1",
        "SE10K-RWB48BEN4_7E1A2B3C_B2",
    ]
    signals, capacity = found["SE10K-RWB48BEN4_7E1A2B3C_B2"]
    assert signals[Signal.SOC] == "sensor.solaredge_i1_b2_state_of_energy"
    assert capacity == "sensor.solaredge_i1_b2_maximum_energy"


def test_solax_counters_disabled_by_default_get_the_hint() -> None:
    fixture = load_fixture("solax_modbus_x3_hybrid_g4.json")
    assert SOLAX_MODBUS.detect(entries(fixture)) == {}
    assert SOLAX_MODBUS.without_counters(entries(fixture)) == [
        fixture["config_entry_id"]
    ]
    (signals, capacity), *_ = SOLAX_MODBUS.detect(
        entries(fixture, usable=True)
    ).values()
    assert signals == {
        Signal.CHARGED: "sensor.solax_battery_input_energy_total",
        Signal.DISCHARGED: "sensor.solax_battery_output_energy_total",
        Signal.SOC: "sensor.solax_battery_capacity",
    }
    assert capacity == "sensor.solax_battery_system_installed_capacity"


def test_sungrow_yaml_one_inverter() -> None:
    fixture = load_fixture("sungrow_modbus_yaml.json")
    found = SUNGROW_MODBUS_YAML.detect(entries(fixture))
    assert list(found) == [""]
    signals, capacity = found[""]
    assert signals == {
        Signal.CHARGED: "sensor.total_battery_charge",
        Signal.DISCHARGED: "sensor.total_battery_discharge",
        Signal.SOC: "sensor.battery_level",
    }
    assert capacity == "sensor.battery_capacity_high_precision"


def test_sungrow_yaml_two_inverters() -> None:
    fixture = load_fixture("sungrow_modbus_yaml_two_inverters.json")
    found = SUNGROW_MODBUS_YAML.detect(entries(fixture))
    assert sorted(found) == ["_inv_1", "_inv_2"]
    signals, capacity = found["_inv_2"]
    assert signals[Signal.SOC] == "sensor.battery_level_inv_2"
    assert capacity == "sensor.battery_capacity_high_precision_inv_2"


def test_sigen_plant_only_not_the_inverter() -> None:
    fixture = load_fixture("sigen_plant.json")
    found = SIGEN.detect(entries(fixture))
    (storage,) = found
    assert storage.endswith("_sigen_plant")
    signals, capacity = found[storage]
    assert signals[Signal.CHARGED] == (
        "sensor.sigen_plant_total_charged_energy_of_the_ess"
    )
    assert signals[Signal.SOC] == "sensor.sigen_plant_battery_state_of_charge"
    assert capacity == "sensor.sigen_plant_rated_energy_capacity"


def test_sigen_old_firmware_gets_the_hint() -> None:
    fixture = load_fixture("sigen_plant.json")
    old = [e for e in entries(fixture) if "plant_accumulated" not in e.unique_id]
    assert SIGEN.detect(old) == {}
    assert len(SIGEN.without_counters(old)) == 1


def test_zendure_devices_not_packs_or_manager() -> None:
    fixture = load_fixture("zendure_ha_solarflow.json")
    found = ZENDURE_HA.detect(entries(fixture))
    assert sorted(found) == ["hyper_2000", "solarflow_800_pro"]
    signals, _capacity = found["hyper_2000"]
    assert signals[Signal.CHARGED] == "sensor.hyper_2000_aggr_charge"
    assert ZENDURE_HA.without_counters(entries(fixture)) == []


@pytest.mark.parametrize(
    ("fixture_name", "capacity"),
    [
        (
            "marstek_modbus_suite_venus_e_v3.json",
            "sensor.marstek_venus_e_3_0_batterie_nennkapazitat",
        ),
        (
            "marstek_venus_modbus_venus_e_v3.json",
            "sensor.marstek_venus_modbus_batterie_gesamtenergie",
        ),
    ],
)
def test_marstek_venus_e_both_forks(fixture_name: str, capacity: str) -> None:
    fixture = load_fixture(fixture_name)
    found = MARSTEK_MODBUS.detect(entries(fixture))
    assert list(found) == [fixture["config_entry_id"]]
    signals, found_capacity = found[fixture["config_entry_id"]]
    assert signals[Signal.CHARGED].endswith("_gesamte_ladeenergie")
    assert found_capacity == capacity


def test_marstek_venus_d_excluded_by_a_disabled_entity() -> None:
    """PV passes through the counters of a Venus A/D."""
    fixture = load_fixture("marstek_venus_modbus_venus_d.json")
    assert any(not e.usable for e in entries(fixture))
    assert MARSTEK_MODBUS.detect(entries(fixture)) == {}
    assert MARSTEK_MODBUS.without_counters(entries(fixture)) == []
