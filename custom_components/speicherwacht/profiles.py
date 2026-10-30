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
    # Key of an entity holding the usable capacity (Wh or kWh), offered as
    # the default in the setup; never replaces the user's value.
    capacity: str | None = None
    boundary: Boundary = Boundary.BATTERY
    # Counters start anew each local day (cloud day values).
    day_values: bool = False
    # Built from the integration's source code, not yet confirmed on a real
    # installation: shown as "(beta)" in the setup.
    experimental: bool = False
    # The setup explains how to get the counters when a storage of this
    # template has a state of charge but no counters (text "hint_<key>").
    counter_hint: bool = False

    def group(self, entries: Iterable[RegistryEntry]) -> dict[str, dict[str, str]]:
        """{storage id: {key: entity_id}} of the usable entries."""
        groups: dict[str, dict[str, str]] = {}
        for entry in entries:
            if entry.platform != self.platform or not entry.usable:
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
            groups.setdefault(storage, {}).setdefault(key, entry.entity_id)
        return groups

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
        if self.capacity:
            keys.add(self.capacity)
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
                capacity = keys.get(self.capacity) if self.capacity else None
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
    capacity="capacity_designed",
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
    capacity="storage_rated_capacity",
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
    capacity="battery_capacity",
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
    capacity="rated_energy",
    experimental=True,
)

TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (FRONIUS, HUAWEI_SOLAR, SOLARMAN, ANKER_SOLIX, ANKER_SOLIX_OFFICIAL)
}
