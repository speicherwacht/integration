"""Button: show a short report for a bug report (issue_report.py)."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    CONF_WARRANTY_MWH,
    DOMAIN,
    TEMPLATE_MANUAL,
    VERSION,
)
from .days import Period
from .entity import StorageEntity
from .issue_report import build, show
from .profiles import TEMPLATES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SpeicherwachtConfigEntry
    from .runtime import StorageRuntime

NAME = "Speicherwacht"
# Settings shown in the report: numbers and choices only. The entry's name
# (free text) and the entity ids stay out.
SETTINGS = (CONF_BOUNDARY, CONF_CAPACITY, CONF_WARRANTY_MWH)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeicherwachtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([IssueReport(entry)])


class IssueReport(StorageEntity, ButtonEntity):
    """A short report to copy into a bug report, as a notification: what an
    issue needs without the diagnostics download (issue_report.py)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: SpeicherwachtConfigEntry) -> None:
        super().__init__(entry, "issue_report")
        self._entry = entry

    async def async_press(self) -> None:
        entry = self._entry
        # As configured, also an own sensor the runtime does not read.
        mapping = dict(entry.data.get(CONF_ENTITIES) or {})
        report = build(
            self.hass,
            DOMAIN,
            NAME,
            VERSION,
            entry,
            mapping=mapping,
            extra=_lines(entry, self.runtime),
            options={key: entry.data.get(key) for key in SETTINGS},
        )
        show(self.hass, DOMAIN, NAME, entry, report)


def _lines(
    entry: SpeicherwachtConfigEntry, runtime: StorageRuntime
) -> list[tuple[str, str]]:
    key = entry.data.get(CONF_TEMPLATE) or TEMPLATE_MANUAL
    template = TEMPLATES.get(key)
    lines = [
        ("template", "own mapping" if template is None else key),
    ]
    if template is not None:
        lines.append(("beta template", str(template.experimental)))
    lines += [
        ("day values", str(runtime.day_values)),
        ("problem", str(runtime.problem or "none")),
        ("own entities as source", str(len(runtime.own))),
    ]
    if (series := runtime.series) is not None:
        hours = series.hours
        lines.append(
            (
                "hours",
                f"{len(hours)}, {sum(1 for h in hours if h.gap)} gaps"
                + (
                    f", {hours[0].start.date().isoformat()} - "
                    f"{hours[-1].start.date().isoformat()}"
                    if hours
                    else ""
                ),
            )
        )
        rejected = Counter(f"{i.signal} {i.event.value}" for i in series.issues)
        lines.append(
            (
                "rejected readings",
                ", ".join(f"{k} {v}" for k, v in sorted(rejected.items())) or "none",
            )
        )
    if (analysis := runtime.analysis) is not None:
        total = analysis.efficiency[Period.TOTAL]
        lines.append(
            (
                "days (total)",
                f"{total.operating_days} operating, {total.rest_days} rest, "
                f"{total.days_without_soc} without SoC, "
                f"{total.incomplete_days} incomplete",
            )
        )
    return lines
