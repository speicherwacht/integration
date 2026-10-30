"""Source templates: which entity of an integration is which signal.

Pure Python, no Home Assistant imports: the caller passes registry entries as
`RegistryEntry` tuples. Templates are data; the core knows no vendor. Same
idea as Wärmewacht's templates. Sources of every key: docs/ENTWICKLUNG.md,
section 4, and the fixtures in tests/fixtures (origin in _index.json).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from typing import NamedTuple

from .model import REQUIRED, Boundary, Signal


class RegistryEntry(NamedTuple):
    """The parts of an entity registry entry a template matches on."""

    entity_id: str
    platform: str
    unique_id: str
    config_entry_id: str | None = None
    # Enabled and reporting a state.
    usable: bool = True


class GroupBy(StrEnum):
    """What makes one storage."""

    PREFIX = "prefix"  # the "prefix" group of the unique id (serial number)
    # The config entry: the signals sit on several devices of one source
    # (Fronius: counters at the inverter, state of charge at the battery).
    ENTRY = "entry"


@dataclass(frozen=True)
class Template:
    """How to find the signals of one storage in one integration."""

    key: str
    label: str  # shown in the setup
    platform: str
    # Candidate keys per signal, preferred first.
    signals: dict[Signal, tuple[str, ...]]
    # Regular expression for the whole unique id with the group "key" and,
    # for GroupBy.PREFIX, "prefix". "{key}" stands for the template's own
    # keys, tried longest first.
    id_format: str
    group_by: GroupBy = GroupBy.PREFIX
    # Keys of an entity holding the usable capacity (Wh or kWh), preferred
    # first, offered as the default in the setup; never replace the user's
    # value.
    capacity: tuple[str, ...] = ()
    # A storage with one of these keys is not of this template, even if the
    # entity is disabled (another model with the same counters).
    exclude_keys: tuple[str, ...] = ()
    boundary: Boundary = Boundary.BATTERY
    # Counters start anew each local day (cloud day values).
    day_values: bool = False
    # Built from the integration's source code, not yet confirmed on a real
    # installation: shown as "(beta)" in the setup.
    experimental: bool = False
    # The setup explains how to get the counters when a storage of this
    # template has a state of charge but no counters (text "hint_<key>").
    counter_hint: bool = False
    # The entities step explains a limit of this source (text "note_<key>").
    note: bool = False

    def group(self, entries: Iterable[RegistryEntry]) -> dict[str, dict[str, str]]:
        """{storage id: {key: entity_id}} of the usable entries."""
        groups: dict[str, dict[str, str]] = {}
        excluded: set[str] = set()
        for entry in entries:
            if entry.platform != self.platform:
                continue
            parts = self.split(entry.unique_id)
            if parts is None:
                continue
            prefix, key = parts
            storage = (
                entry.config_entry_id or ""
                if self.group_by is GroupBy.ENTRY
                else prefix
            )
            if key in self.exclude_keys:
                excluded.add(storage)
            elif entry.usable:
                groups.setdefault(storage, {}).setdefault(key, entry.entity_id)
        return {s: keys for s, keys in groups.items() if s not in excluded}

    def split(self, unique_id: str) -> tuple[str, str] | None:
        """(prefix, key) of a unique id, None if it is not of this format."""
        for pattern in self._id_patterns:
            if (match := pattern.fullmatch(unique_id)) is not None:
                return match.groupdict().get("prefix") or "", match["key"]
        return None

    @cached_property
    def _id_patterns(self) -> tuple[re.Pattern[str], ...]:
        if "{key}" not in self.id_format:
            return (re.compile(self.id_format),)
        keys = {key for keys in self.signals.values() for key in keys}
        keys.update(self.capacity, self.exclude_keys)
        return tuple(
            re.compile(self.id_format.replace("{key}", re.escape(key)))
            for key in sorted(keys, key=len, reverse=True)
        )

    def resolve(self, keys: dict[str, str]) -> dict[Signal, str]:
        """Entity per signal of one storage (first matching key wins)."""
        found: dict[Signal, str] = {}
        for signal, candidates in self.signals.items():
            for key in candidates:
                if key in keys:
                    found[signal] = keys[key]
                    break
        return found

    def detect(
        self, entries: Iterable[RegistryEntry]
    ) -> dict[str, tuple[dict[Signal, str], str | None]]:
        """Storages with all required signals: {id: (signals, capacity entity)}."""
        result = {}
        for storage, keys in self.group(entries).items():
            signals = self.resolve(keys)
            if all(signal in signals for signal in REQUIRED):
                capacity = next((keys[k] for k in self.capacity if k in keys), None)
                result[storage] = (signals, capacity)
        return result

    def without_counters(self, entries: Iterable[RegistryEntry]) -> list[str]:
        """Storages with a state of charge but without both counters."""
        missing = []
        for storage, keys in self.group(entries).items():
            signals = self.resolve(keys)
            if Signal.SOC in signals and not all(s in signals for s in REQUIRED):
                missing.append(storage)
        return missing


# Core integration fronius (Modbus TCP since Home Assistant 2026.9). The
# lifetime counters of the battery port sit on the inverter ("<inverter
# id>-modbus-<key>"), state of charge and capacity on the battery ("<serial
# padded with spaces>-<key>"); a GEN24 has one battery input, so one config
# entry is one storage. The "MPPT 3/4 energy" sensors repeat the counters and
# are not used. Checked at tag 2026.10.4 and on dev (2026-10-30).
FRONIUS = Template(
    key="fronius",
    label="Fronius (GEN24, Modbus TCP)",
    platform="fronius",
    signals={
        Signal.CHARGED: ("storage_energy_charged_total",),
        Signal.DISCHARGED: ("storage_energy_discharged_total",),
        Signal.SOC: ("state_of_charge",),
    },
    id_format=r"(?P<prefix>.+?)(?:-modbus)?-(?P<key>{key})",
    group_by=GroupBy.ENTRY,
    capacity=("capacity_designed",),
)

# HACS integration huawei_solar (wlcrs/huawei_solar 2.1.5, 9738e50): unique id
# "<inverter serial>_<register key>". The sums over all battery stacks of an
# inverter are "total" without last_reset (steps back reach the statistics as
# negative changes; the counter module handles them). The per-stack counters
# are disabled by default and not used. Rated capacity in Wh, disabled by
# default. Positive power is charging.
HUAWEI_SOLAR = Template(
    key="huawei_solar",
    label="Huawei SUN2000 mit LUNA2000 (huawei_solar)",
    platform="huawei_solar",
    signals={
        Signal.CHARGED: ("storage_total_charge",),
        Signal.DISCHARGED: ("storage_total_discharge",),
        Signal.SOC: ("storage_state_of_capacity",),
    },
    id_format=r"(?P<prefix>[^_]+)_(?P<key>{key})",
    capacity=("storage_rated_capacity",),
    experimental=True,
)

# HACS integration solarman (davidrapan/ha-solarman, ac1d88b; same ids in
# v25.08.16): unique id "<config entry id, lower case>_<slugified English
# profile name>_<platform>", independent of the language. Names as in the Deye
# hybrid profiles (one and three phases); counters 0.1 kWh. The "Battery
# Capacity" sensor is an estimate and the three-phase "Battery SOH" a linear
# write-off over the throughput: neither is offered. The archived
# StephanJoubert/home_assistant_solarman (same domain) has other ids.
SOLARMAN = Template(
    key="solarman",
    label="Deye und andere über Solarman-Logger (solarman)",
    platform="solarman",
    signals={
        Signal.CHARGED: ("total_battery_charge_sensor",),
        Signal.DISCHARGED: ("total_battery_discharge_sensor",),
        Signal.SOC: ("battery_sensor",),
    },
    id_format=r"(?P<prefix>[0-9a-z]{26})_(?P<key>{key})",
    experimental=True,
)

# HACS integration anker_solix (thomluther/ha-anker-solix 3.9.1, d510255),
# Solarbank 1-4 over the cloud: unique id "<serial, lower case>_<key>". The
# lifetime counters come only by MQTT (owner account) and new entries exclude
# the energy category: then they do not exist at all (counter_hint). Whether
# they count DC or AC is not documented. Total state of charge including
# expansion batteries; capacity as number entity in Wh (rated × SoH).
ANKER_SOLIX = Template(
    key="anker_solix",
    label="Anker SOLIX Solarbank (anker_solix)",
    platform="anker_solix",
    signals={
        Signal.CHARGED: ("charged_energy",),
        Signal.DISCHARGED: ("discharged_energy",),
        Signal.SOC: ("state_of_charge",),
    },
    id_format=r"(?P<prefix>[0-9a-z]+)_(?P<key>{key})",
    capacity=("battery_capacity",),
    experimental=True,
    counter_hint=True,
)

# Integration anker_solix_official (anker-charging/ha-anker-solix-official
# v1.5.0, 3ecc42b), local Modbus TCP for Solarbank 4 E5000 Pro, Max and XE:
# unique id "<config entry id>_<key>". Counters in 0.1 kWh; the rated energy
# (kWh) is wrongly total_increasing and alternates by 0.1 kWh (#151).
ANKER_SOLIX_OFFICIAL = Template(
    key="anker_solix_official",
    label="Anker SOLIX Solarbank 4, Max, XE (anker_solix_official)",
    platform="anker_solix_official",
    signals={
        Signal.CHARGED: ("cumulative_charge_energy",),
        Signal.DISCHARGED: ("cumulative_discharge_energy",),
        Signal.SOC: ("battery_soc",),
    },
    id_format=r"(?P<prefix>[0-9A-Z]{26})_(?P<key>{key})",
    capacity=("rated_energy",),
    experimental=True,
)

# Core integration goodwe (marcelblijleven/goodwe 0.4.10, 66dfcdd; same ids in
# the HACS variant): unique id "goodwe-<sensor id>-<serial>". Only the ET
# family (ET/EH/BT/BH and platforms 205/745/753) has lifetime counters, DC at
# the inverter's battery port (0.1 kWh); ES/EM/BP show the SoC only
# (counter_hint). The day counters are total_increasing too and not used.
# No capacity entity. Positive battery power is discharging.
GOODWE = Template(
    key="goodwe",
    label="GoodWe ET/EH/BT/BH (goodwe)",
    platform="goodwe",
    signals={
        Signal.CHARGED: ("e_bat_charge_total",),
        Signal.DISCHARGED: ("e_bat_discharge_total",),
        Signal.SOC: ("battery_soc",),
    },
    id_format=r"goodwe-(?P<key>{key})-(?P<prefix>.+)",
    experimental=True,
    counter_hint=True,
)

# Core integration victron_gx (since 2026.5, victron-mqtt 2026.9.5, 37fbc4d):
# unique id "<VRM portal id>_battery_<device instance>_<key>". Lifetime
# counters (History/ChargedEnergy, DischargedEnergy; DC at the shunt) come
# from battery monitors such as SmartShunt and BMV; batteries with a CAN BMS
# show the SoC only (counter_hint). The system device's charge/discharge
# energy is a Riemann sum that starts anew with every restart: not used.
# Capacity only in Ah, so none is offered.
VICTRON_GX = Template(
    key="victron_gx",
    label="Victron GX: Batteriemonitor (victron_gx)",
    platform="victron_gx",
    signals={
        Signal.CHARGED: ("battery_charged_energy",),
        Signal.DISCHARGED: ("battery_discharged_energy",),
        Signal.SOC: ("battery_soc",),
    },
    id_format=r"(?P<prefix>[0-9A-Za-z]+_battery_\d+)_(?P<key>{key})",
    experimental=True,
    counter_hint=True,
)

# HACS integration solaredge_modbus_multi (WillCodeForCats 4.0.10, 70aa159):
# unique id "<inverter model>_<serial>_B<1-3>_<key>", one storage per
# battery. Battery entities exist only with the option "Auto-Detect
# Batteries". Lifetime counters in Wh (1 Wh); LG/BYD batteries reset them
# and the SolarEdge Home Battery runs backwards – without the option
# "Allow Battery Energy to Reset" the counter freezes instead (#1156), which
# the repair issue counter_soc_mismatch reveals. Capacity: maximum energy.
SOLAREDGE_MODBUS_MULTI = Template(
    key="solaredge_modbus_multi",
    label="SolarEdge StorEdge (solaredge_modbus_multi)",
    platform="solaredge_modbus_multi",
    signals={
        Signal.CHARGED: ("energy_import",),
        Signal.DISCHARGED: ("energy_export",),
        Signal.SOC: ("battery_soe",),
    },
    id_format=r"(?P<prefix>.+_B[1-3])_(?P<key>{key})",
    capacity=("max_energy",),
    experimental=True,
)

# HACS integration solax_modbus (wills106 2026.10.02, b6880b6): unique id
# "<hub name>_<key>", one inverter per config entry. Lifetime counters are
# "total" without last_reset, 0.1 kWh, disabled by default and then not even
# read (counter_hint). "battery_capacity" is the SoC in % for SolaX
# ("battery_capacity_total" for Sofar); other brands in the same repository
# use other keys (AlphaESS: capacity in kWh) and are left out. The optional
# "Energy Dashboard" device holds day values and Riemann sums: excluded.
SOLAX_MODBUS = Template(
    key="solax_modbus",
    label="SolaX, Sofar (solax_modbus)",
    platform="solax_modbus",
    signals={
        Signal.CHARGED: ("battery_input_energy_total",),
        Signal.DISCHARGED: ("battery_output_energy_total",),
        Signal.SOC: ("battery_capacity", "battery_capacity_total"),
    },
    id_format=r"(?!.* Energy Dashboard_)(?P<prefix>.+)_(?P<key>{key})",
    group_by=GroupBy.ENTRY,
    capacity=("battery_system_installed_capacity",),
    experimental=True,
    counter_hint=True,
)

# Core integration modbus with the YAML package of mkaiser/Sungrow-SHx-
# Inverter-Modbus-Home-Assistant (310635c, 2026-06-19): the unique ids are the
# package's own, "_inv_<n>" appended with several inverters; one storage per
# inverter. Lifetime counters "total" without last_reset, 0.1 kWh, read every
# 600 s. "Battery level" runs from 0 to 100 % between min and max SoC, not
# absolute (note). The successor integration sungrow_modbus (alpha) keeps the
# entity ids but changes platform and unique ids. Negative power is charging.
SUNGROW_MODBUS_YAML = Template(
    key="sungrow_modbus_yaml",
    label="Sungrow SH (Modbus-YAML von mkaiser)",
    platform="modbus",
    signals={
        Signal.CHARGED: ("sg_total_battery_charge",),
        Signal.DISCHARGED: ("sg_total_battery_discharge",),
        Signal.SOC: ("sg_battery_level",),
    },
    id_format=r"(?P<key>{key})(?P<prefix>_inv_\d+)?",
    capacity=("uid_battery_capacity_high_precision",),
    experimental=True,
    note=True,
)

# HACS integration sigen (TypQxQ/Sigenergy-Local-Modbus 1.2.7.5, b66e304; the
# same in 1.3.0): unique id "<config entry id>_<device name>_<key>". Only the
# plant's counters (protocol v2.7 and later, 0.01 kWh, "total" without
# last_reset, shown in MWh): one storage per plant. The inverters have their
# own counters of the same battery and are not offered, so it does not show
# twice; older firmware has the plant SoC only (counter_hint). Rated capacity
# in kWh. Positive power is charging.
SIGEN = Template(
    key="sigen",
    label="Sigenergy SigenStor (sigen)",
    platform="sigen",
    signals={
        Signal.CHARGED: ("plant_accumulated_battery_charge_energy",),
        Signal.DISCHARGED: ("plant_accumulated_battery_discharge_energy",),
        Signal.SOC: ("plant_ess_soc",),
    },
    id_format=r"(?P<prefix>[0-9A-Za-z]{26}_[0-9a-z_]+?)_(?P<key>{key})",
    capacity=("plant_ess_rated_energy_capacity",),
    experimental=True,
    counter_hint=True,
)

# HACS integration zendure_ha (Zendure/Zendure-HA 1.4.4, 8d59bac): unique id
# "<device name from the app, snake case>_<key>"; renaming the device in the
# app moves unique id and entity id. The lifetime counters are summed up in
# Home Assistant from the pack powers, not read from the device (note).
# Capacity = rated sum of the packs. Expansion packs and the manager have no
# counters.
ZENDURE_HA = Template(
    key="zendure_ha",
    label="Zendure SolarFlow, Hyper, Hub (zendure_ha)",
    platform="zendure_ha",
    signals={
        Signal.CHARGED: ("aggr_charge",),
        Signal.DISCHARGED: ("aggr_discharge",),
        Signal.SOC: ("electric_level",),
    },
    id_format=r"(?P<prefix>[a-z0-9_]+?)_(?P<key>{key})",
    capacity=("total_kwh",),
    experimental=True,
    note=True,
)

# HACS integrations marstek_venus_modbus (ViperRNMC 2026.10.1, cb5a241) and
# marstek-modbus-suite (sphings79 3.1.3, 60c023d): same domain, unique id
# "<config entry id>_<key>". The lifetime counters (registers 33000/33002,
# 0.01 kWh) count at the AC connection: on the Venus E (no PV input) that is
# the whole storage; on a Venus A/D PV passes through them, so those are
# excluded (only their register maps have mppt1_power, disabled by default).
# The suite renamed the capacity key in 3.1.0-beta.3.
MARSTEK_MODBUS = Template(
    key="marstek_modbus",
    label="Marstek Venus E (marstek_modbus)",
    platform="marstek_modbus",
    signals={
        Signal.CHARGED: ("total_charging_energy",),
        Signal.DISCHARGED: ("total_discharging_energy",),
        Signal.SOC: ("battery_soc",),
    },
    id_format=r"(?P<prefix>[0-9A-Z]{26})_(?P<key>{key})",
    capacity=("battery_rated_capacity", "battery_total_energy"),
    exclude_keys=("mppt1_power",),
    boundary=Boundary.SYSTEM,
    experimental=True,
)

TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (
        FRONIUS,
        HUAWEI_SOLAR,
        SOLARMAN,
        ANKER_SOLIX,
        ANKER_SOLIX_OFFICIAL,
        GOODWE,
        VICTRON_GX,
        SOLAREDGE_MODBUS_MULTI,
        SOLAX_MODBUS,
        SUNGROW_MODBUS_YAML,
        SIGEN,
        ZENDURE_HA,
        MARSTEK_MODBUS,
    )
}
