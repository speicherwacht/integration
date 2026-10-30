"""Follow a source entity renamed in the entity registry. Pure Python.

An entry keeps its three sources as entity ids, and the charge counter is
its unique id. Home Assistant moves the statistics along with a renamed
entity; only these references have to follow (__init__.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import CONF_ENTITIES


def sources(data: Mapping[str, Any]) -> set[str]:
    """Every entity id the entry refers to."""
    entities: Mapping[str, str] = data.get(CONF_ENTITIES) or {}
    return {e for e in entities.values() if e}


def renamed_data(data: Mapping[str, Any], old: str, new: str) -> dict[str, Any]:
    """The entry data with `old` replaced by `new`."""
    entities: Mapping[str, str] = data.get(CONF_ENTITIES) or {}
    return {
        **data,
        CONF_ENTITIES: {
            signal: new if e == old else e for signal, e in entities.items()
        },
    }


def renamed_unique_id(unique_id: str | None, old: str, new: str) -> str | None:
    """The unique id after the rename; None if it does not name `old`."""
    return new if unique_id == old else None
