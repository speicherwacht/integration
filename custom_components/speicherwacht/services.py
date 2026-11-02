"""Action "report": the figures of any period, by default the current
calendar year until now (as Wärmewacht's action of the same name)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .days import Period, local_midnight, period_start
from .report import report

if TYPE_CHECKING:
    from . import SpeicherwachtConfigEntry

SERVICE_REPORT = "report"
ATTR_CONFIG_ENTRY = "config_entry"
ATTR_START = "start"
ATTR_END = "end"

REPORT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_START): cv.datetime,
        vol.Optional(ATTR_END): cv.datetime,
    }
)


def _as_utc(moment: datetime) -> datetime:
    """Times without zone are local time of Home Assistant."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_utc(moment)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

    async def report_action(call: ServiceCall) -> ServiceResponse:
        entry: SpeicherwachtConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
        )
        runtime = entry.runtime_data
        now = dt_util.utcnow()
        if ATTR_START in call.data:
            start = _as_utc(call.data[ATTR_START])
        else:
            # As the yearly sensors: from local 1 January.
            first = period_start(Period.YEAR, now, runtime.tz)
            if TYPE_CHECKING:
                assert first is not None
            start = local_midnight(first, runtime.tz)
        end = _as_utc(call.data[ATTR_END]) if ATTR_END in call.data else now
        if start >= end:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="start_after_end"
            )
        if "recorder" not in hass.config.components:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_recorder"
            )
        series = runtime.series
        if series is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_analysed_yet"
            )
        figures = await hass.async_add_executor_job(
            report, series.hours, runtime.capacity, runtime.tz, start, end, now
        )
        return {
            "start": dt_util.as_local(start).isoformat(),
            "end": dt_util.as_local(end).isoformat(),
            "boundary": runtime.boundary.value,
            "capacity_kwh": runtime.capacity,
            **figures,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_REPORT,
        report_action,
        schema=REPORT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
