"""Runtime of one storage: analysis from the long-term statistics only.

No store, no state listeners for the figures: shortly after the start the
whole statistics of the three source entities are read once, then every hour
the last few hours (decision of the owner 2026-10-30, docs/ENTWICKLUNG.md).
Live and look-back therefore compute the same way. Repair issues look at
the current states every few minutes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .analysis import Analysis, analyse
from .const import (
    CONF_BOUNDARY,
    CONF_CAPACITY,
    CONF_ENTITIES,
    CONF_TEMPLATE,
    CONF_WARRANTY_MWH,
    DOMAIN,
)
from .counter import UNIT_FACTORS, looks_like_day_counter
from .day_counters import WINDOW as DAY_COUNTER_WINDOW
from .health import Health, check
from .hours import Series, SocRow, build
from .model import Boundary, Signal
from .profiles import TEMPLATES

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

FIRST_DELAY = timedelta(minutes=1)
# Home Assistant compiles the hourly statistics a few minutes after the hour.
REFRESH_MINUTE = 12
# Each refresh reads again from a few hours before the last row (late rows).
OVERLAP = timedelta(hours=3)
# Everything since this date is read at the start.
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
ISSUE_INTERVAL = timedelta(minutes=5)
# Repair issues only after Home Assistant had time to load the sources.
ISSUE_GRACE = timedelta(minutes=10)
# A source unavailable longer than this gets a repair issue (own assumption,
# as Wärmewacht).
UNAVAILABLE_AFTER = timedelta(minutes=60)

# Why there is no analysis.
NO_RECORDER = "no_recorder"
NOT_ANALYSED = "not_analysed_yet"

ISSUE_MISSING = "missing_entity"
ISSUE_UNAVAILABLE = "source_unavailable"
ISSUE_UNIT = "source_unit"
ISSUE_RESETS = "counter_resets"
ISSUE_MISMATCH = "counter_soc_mismatch"


class StorageRuntime:
    """One storage: figures from the hourly statistics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.tz = dt_util.get_default_time_zone()
        configured: dict[str, str] = dict(entry.data[CONF_ENTITIES])
        self.entities: dict[Signal, str] = {
            Signal(key): entity_id for key, entity_id in configured.items()
        }
        self.capacity: float = entry.data[CONF_CAPACITY]
        self.boundary = Boundary(entry.data.get(CONF_BOUNDARY, Boundary.BATTERY))
        template = TEMPLATES.get(entry.data.get(CONF_TEMPLATE) or "")
        self.day_values = template.day_values if template else False
        # Warranted energy throughput in kWh (optional).
        self.warranty_kwh: float | None = (
            entry.data[CONF_WARRANTY_MWH] * 1000
            if entry.data.get(CONF_WARRANTY_MWH)
            else None
        )
        self.analysis: Analysis | None = None
        self.health: Health | None = None
        self.series: Series | None = None
        self.problem: str | None = NOT_ANALYSED
        self._charged: dict[datetime, float] = {}
        self._discharged: dict[datetime, float] = {}
        self._soc: dict[datetime, SocRow] = {}
        self._last_row: datetime | None = None
        self._refreshing = False
        self._started = dt_util.utcnow()
        self._unavailable_since: dict[str, datetime] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubscribe: list[CALLBACK_TYPE] = []

    # Lifecycle.

    async def async_start(self) -> None:
        @callback
        def _refresh(_now: datetime) -> None:
            # Bound to the entry: an unload cancels a running first read.
            self.entry.async_create_background_task(
                self.hass, self.async_refresh(), "speicherwacht_refresh"
            )

        self._unsubscribe = [
            async_call_later(
                self.hass,
                FIRST_DELAY,
                HassJob(_refresh, "speicherwacht_first", cancel_on_shutdown=True),
            ),
            async_track_time_change(
                self.hass, _refresh, minute=REFRESH_MINUTE, second=0
            ),
            async_track_time_interval(
                self.hass,
                self._async_check_issues,
                ISSUE_INTERVAL,
                cancel_on_shutdown=True,
            ),
        ]

    async def async_stop(self) -> None:
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self._unsubscribe = []

    @callback
    def add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # Analysis.

    async def async_refresh(self) -> None:
        """Read new statistics rows and analyse; never raises."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if "recorder" not in self.hass.config.components:
                self.problem = NO_RECORDER
                return
            now = dt_util.utcnow()
            start = EPOCH if self._last_row is None else self._last_row - OVERLAP
            await self._async_read(start, now)
            # Pure functions over all hours (tens of thousands after a few
            # years): off the event loop, on copies of the hourly readings.
            (
                self.series,
                self.analysis,
                self.health,
            ) = await self.hass.async_add_executor_job(
                self._compute,
                dict(self._charged),
                dict(self._discharged),
                dict(self._soc),
                now,
            )
            self.problem = None
            self._check_resets(now)
            self._check_mismatch(now)
        except Exception:  # keep running; the sensors stay as they were
            _LOGGER.exception("Analysing the storage statistics failed")
        finally:
            self._refreshing = False
            self._notify()

    def _compute(
        self,
        charged: dict[datetime, float],
        discharged: dict[datetime, float],
        soc: dict[datetime, SocRow],
        now: datetime,
    ) -> tuple[Series, Analysis, Health]:
        series = build(
            charged,
            discharged,
            soc,
            self.capacity,
            self.tz if self.day_values else None,
        )
        return (
            series,
            analyse(series.hours, self.capacity, self.tz, now),
            check(series.hours, self.capacity, self.tz, now),
        )

    @property
    def lifetime_discharged(self) -> float | None:
        """Energy discharged since commissioning (kWh): the first reading of a
        lifetime counter plus the increments the counter module booked, so a
        glitch of the latest reading never shows; for day counters the sum of
        the statistics."""
        if self.analysis is None or self.series is None:
            return None
        if self.day_values or self.series.first_discharged is None:
            return self.analysis.discharged_total
        return self.series.first_discharged + self.analysis.discharged_total

    async def _async_read(self, start: datetime, end: datetime) -> None:
        counters = {self.entities[Signal.CHARGED], self.entities[Signal.DISCHARGED]}
        soc_id = self.entities[Signal.SOC]
        instance = get_instance(self.hass)
        rows = await instance.async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            end,
            counters,
            "hour",
            {"energy": "kWh"},
            {"state"},
        )
        soc_rows = await instance.async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            end,
            {soc_id},
            "hour",
            None,
            {"mean", "min", "max"},
        )
        for signal, target in (
            (Signal.CHARGED, self._charged),
            (Signal.DISCHARGED, self._discharged),
        ):
            for row in rows.get(self.entities[signal], []):
                if (value := row.get("state")) is None:
                    continue
                hour = _hour(row["start"])
                target[hour] = value
                self._last_row = max(self._last_row or hour, hour)
        for row in soc_rows.get(soc_id, []):
            if (mean := row.get("mean")) is None:
                continue
            self._soc[_hour(row["start"])] = SocRow(
                mean, row.get("min"), row.get("max")
            )

    # Repair issues.

    async def _async_check_issues(self, now: datetime) -> None:
        if now - self._started < ISSUE_GRACE:
            return
        missing, unavailable, unit = [], [], []
        for signal, entity_id in self.entities.items():
            state = self.hass.states.get(entity_id)
            if state is None:
                missing.append(entity_id)
                continue
            if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                since = self._unavailable_since.setdefault(entity_id, now)
                if now - since >= UNAVAILABLE_AFTER:
                    unavailable.append(entity_id)
                continue
            self._unavailable_since.pop(entity_id, None)
            if not _unit_ok(signal, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
                unit.append(entity_id)
        self._issue(ISSUE_MISSING, missing)
        self._issue(
            ISSUE_UNAVAILABLE,
            unavailable,
            minutes=str(int(UNAVAILABLE_AFTER.total_seconds() // 60)),
        )
        self._issue(ISSUE_UNIT, unit)

    def _check_mismatch(self, now: datetime) -> None:
        """Repair issue when counters and state of charge disagree over the
        last day; only after the start-up grace, like the other issues."""
        if self.health is None or now - self._started < ISSUE_GRACE:
            return
        mismatch = self.health.mismatch
        entities = []
        if mismatch.problem:
            signal = (
                Signal.SOC
                if mismatch.details.get("kind") == "soc_still"
                else Signal.CHARGED
            )
            entities = [self.entities[signal]]
            if signal is Signal.CHARGED:
                entities.append(self.entities[Signal.DISCHARGED])
        self._issue(ISSUE_MISMATCH, entities)

    def _check_resets(self, now: datetime) -> None:
        """Repair issue for counters that restart like a day counter (one
        mapped as lifetime counter books nothing after its first day); the
        rule of the setup (counter.looks_like_day_counter) on the hourly
        states read anyway."""
        if self.day_values:
            return
        since = now - DAY_COUNTER_WINDOW
        found = [
            self.entities[signal]
            for signal, states in (
                (Signal.CHARGED, self._charged),
                (Signal.DISCHARGED, self._discharged),
            )
            if looks_like_day_counter(
                sorted((h, v) for h, v in states.items() if h >= since), self.tz
            )
        ]
        self._issue(ISSUE_RESETS, found)

    def _issue(self, key: str, entities: list[str], **placeholders: str) -> None:
        issue_id = f"{self.entry.entry_id}_{key}"
        if not entities:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders={
                "name": self.entry.title,
                "entities": ", ".join(sorted(entities)),
                **placeholders,
            },
        )


def _hour(start: float | datetime) -> datetime:
    if isinstance(start, datetime):
        return start.astimezone(UTC)
    return dt_util.utc_from_timestamp(start)


def _unit_ok(signal: Signal, unit: str | None) -> bool:
    if signal is Signal.SOC:
        return unit == PERCENTAGE
    return unit in UNIT_FACTORS
