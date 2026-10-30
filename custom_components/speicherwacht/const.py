"""Constants of Speicherwacht."""

from __future__ import annotations

DOMAIN = "speicherwacht"
# Kept equal to manifest.json and pyproject.toml (tests/test_manifest.py).
VERSION = "0.1.0b3"

CONF_NAME = "name"
CONF_TEMPLATE = "template"
CONF_PREFIX = "prefix"
CONF_ENTITIES = "entities"
# Usable capacity from the data sheet in kWh.
CONF_CAPACITY = "capacity"
# What the counters measure: the battery itself (DC) or the whole system (AC).
CONF_BOUNDARY = "boundary"
# Optional: energy throughput the warranty covers, in MWh discharged.
CONF_WARRANTY_MWH = "warranty_mwh"

TEMPLATE_MANUAL = "manual"
