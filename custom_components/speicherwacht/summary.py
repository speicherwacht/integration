"""Short summary of a storage entry at the top of "Reconfigure" (Markdown).

Pure Python, no Home Assistant imports. What the entry reads, what it
evaluates and since when, then what is missing with its consequence, only
where it matters. The form shows it through a description placeholder,
which Home Assistant does not translate: the text comes in German or English
here (German for a German Home Assistant, English otherwise). The facts
about the source entities come from the caller, read when the form opens.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from .analysis import (
    CAPACITY_WINDOW,
    EMPTY_SOC,
    FULL_SOC,
    MIN_CAPACITY_SAMPLES,
    Analysis,
)
from .const import CONF_BOUNDARY, CONF_CAPACITY, CONF_WARRANTY_MWH
from .model import Boundary, Signal

# Problems of a source entity, found by the caller.
MISSING = "missing"  # no state (removed, or renamed outside the registry)
UNIT = "unit"  # counter not in Wh/kWh/MWh, state of charge not in %
OWN = "own"  # a sensor of Speicherwacht itself: a state of charge is not read


@dataclass(frozen=True, slots=True)
class Source:
    """A source entity as the summary shows it."""

    entity_id: str
    unit: str | None = None
    value: float | None = None  # current state, if numeric
    problem: str | None = None


TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "configured": "**Eingerichtet**",
        "missing": "**Was fehlt**",
        "source_template": "Quelle: Vorlage {label}",
        "source_own": "Quelle: eigene Zuordnung",
        "source_energy": "Quelle: eigene Zuordnung, Zähler wie im Energie-Dashboard",
        "source_tarifwacht": (
            "Quelle: eigene Zuordnung, Zähler wie in Tarifwacht „{title}“"
        ),
        "counters": "Zähler: {kind}{units}, messen {boundary}",
        "lifetime": "Gesamtzähler (Lebenszeit)",
        "day": "Tageszähler (Vorlage)",
        "unit": " in {unit}",
        "units_split": ", geladen in {charged}, entladen in {discharged}",
        "battery": "den Akku (DC)",
        "system": "den ganzen Speicher (AC)",
        "soc": "Ladezustand: jetzt {value} %",
        "soc_no_value": "Ladezustand: zurzeit ohne Wert",
        "soc_not_read": "Ladezustand: wird nicht gelesen",
        "capacity": "Kapazität: {kwh} kWh laut Datenblatt",
        "estimate": "geschätzt {kwh} kWh",
        "estimate_open": (
            "Schätzung offen (braucht {samples} Entladungen von ≥ {full} % bis "
            "≤ {empty} % in {days} Tagen)"
        ),
        "evaluated": "Ausgewertet: {names}",
        "efficiency": "Wirkungsgrad mit Korrektur über den Ladezustand",
        "cycles": "Vollzyklen",
        "rest_loss": "Ruheverlust",
        "capacity_estimate": "geschätzte Kapazität",
        "warranty": "Garantie-Durchsatz ({mwh} MWh)",
        "since": "Daten seit {date} (Langzeitstatistik, auch vor der Einrichtung)",
        "not_read": "Daten: noch nicht gelesen (kurz nach dem Start)",
        "charged": "Ladezähler",
        "discharged": "Entladezähler",
        "hint_counter_missing": (
            "{role} {entity} gibt es nicht: keine neuen Zahlen, bis er wieder "
            "da ist oder hier ein anderer gewählt ist."
        ),
        "hint_counter_unit": (
            "{role} in {unit}: Speicherwacht rechnet nur mit Wh, kWh oder MWh, "
            "die Zahlen stimmen nicht."
        ),
        "hint_soc_missing": (
            "Ladezustand {entity} gibt es nicht: für neue Tage kein "
            "Wirkungsgrad, kein Ruheverlust, keine geschätzte Kapazität."
        ),
        "hint_soc_unit": (
            "Ladezustand in {unit} statt %: Wirkungsgrad, Ruheverlust und "
            "geschätzte Kapazität stimmen nicht."
        ),
        "hint_soc_own": (
            "Als Ladezustand ist ein Sensor von Speicherwacht selbst gewählt, "
            "er wird nicht gelesen: kein Wirkungsgrad, kein Ruheverlust, keine "
            "geschätzte Kapazität."
        ),
        "hint_day_counter": (
            "Ein Zähler beginnt jeden Tag neu wie ein Tageszähler: Speicherwacht "
            "zählt zu wenig – hier einen Gesamtzähler (Lebenszeit) wählen."
        ),
        "hint_no_data": (
            "Noch keine Stunde in der Langzeitstatistik: noch keine Zahlen "
            "(Home Assistant schreibt sie stündlich)."
        ),
        "hint_warranty": (
            "Kein Garantie-Durchsatz (unter „Weitere Angaben“): kein Sensor "
            "„Garantie-Durchsatz genutzt“."
        ),
    },
    "en": {
        "configured": "**Set up**",
        "missing": "**Missing**",
        "source_template": "Source: template {label}",
        "source_own": "Source: own mapping",
        "source_energy": "Source: own mapping, counters as in the energy dashboard",
        "source_tarifwacht": (
            "Source: own mapping, counters as in Tarifwacht “{title}”"
        ),
        "counters": "Counters: {kind}{units}, measuring {boundary}",
        "lifetime": "lifetime counters",
        "day": "day counters (template)",
        "unit": " in {unit}",
        "units_split": ", charged in {charged}, discharged in {discharged}",
        "battery": "the battery (DC)",
        "system": "the whole storage (AC)",
        "soc": "State of charge: now {value} %",
        "soc_no_value": "State of charge: no value at the moment",
        "soc_not_read": "State of charge: not read",
        "capacity": "Capacity: {kwh} kWh from the data sheet",
        "estimate": "estimated {kwh} kWh",
        "estimate_open": (
            "estimate open (needs {samples} discharges from ≥ {full} % to "
            "≤ {empty} % within {days} days)"
        ),
        "evaluated": "Evaluated: {names}",
        "efficiency": "efficiency with the state of charge correction",
        "cycles": "full cycles",
        "rest_loss": "rest loss",
        "capacity_estimate": "estimated capacity",
        "warranty": "warranted throughput ({mwh} MWh)",
        "since": "Data since {date} (long-term statistics, also before the setup)",
        "not_read": "Data: not read yet (shortly after the start)",
        "charged": "Charge counter",
        "discharged": "Discharge counter",
        "hint_counter_missing": (
            "{role} {entity} does not exist: no new figures until it is back "
            "or another one is chosen here."
        ),
        "hint_counter_unit": (
            "{role} in {unit}: Speicherwacht calculates with Wh, kWh or MWh "
            "only, the figures are wrong."
        ),
        "hint_soc_missing": (
            "State of charge {entity} does not exist: for new days no "
            "efficiency, no rest loss, no estimated capacity."
        ),
        "hint_soc_unit": (
            "State of charge in {unit} instead of %: efficiency, rest loss and "
            "estimated capacity are wrong."
        ),
        "hint_soc_own": (
            "A sensor of Speicherwacht itself is chosen as state of charge and "
            "not read: no efficiency, no rest loss, no estimated capacity."
        ),
        "hint_day_counter": (
            "A counter starts anew every day like a day counter: Speicherwacht "
            "counts too little – choose a lifetime counter here."
        ),
        "hint_no_data": (
            "No hour in the long-term statistics yet: no figures yet (Home "
            "Assistant writes them every hour)."
        ),
        "hint_warranty": (
            "No warranted throughput (under “More”): no sensor “Warranted "
            "throughput used”."
        ),
    },
}


def language_of(language: str | None) -> str:
    """`de` for a German Home Assistant, `en` otherwise."""
    return "de" if (language or "").lower().startswith("de") else "en"


def format_number(value: float, language: str, digits: int = 2) -> str:
    """Up to `digits` decimals without trailing zeros, decimal comma in German."""
    text = f"{value:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",") if language == "de" else text


def format_date(day: date, language: str) -> str:
    """dd.mm.yyyy in German, ISO otherwise."""
    return day.strftime("%d.%m.%Y") if language == "de" else day.isoformat()


def storage_summary(
    data: Mapping[str, Any],
    sources: Mapping[Signal, Source],
    *,
    template_label: str | None,
    day_values: bool = False,
    energy_dashboard: bool = False,
    tarifwacht: str | None = None,
    analysis: Analysis | None = None,
    day_counter: bool = False,
    language: str | None,
) -> str:
    """The summary of a storage entry as Markdown.

    `data` is the entry data (capacity, boundary, warranty), `sources` the
    mapped entities by signal. `template_label` is None for an own mapping;
    then `energy_dashboard` / `tarifwacht` (entry title) say where the
    counters match. `analysis` is None while the statistics are not read
    yet; `day_counter` is set while the repair issue "counter starts anew
    every day" is open.
    """
    lang = language_of(language)
    t = TEXTS[lang]
    lines = [_source_line(t, template_label, energy_dashboard, tarifwacht)]

    charged = sources.get(Signal.CHARGED)
    discharged = sources.get(Signal.DISCHARGED)
    # Units as the sources report them now; an unknown one is left out.
    units = [s.unit if s else None for s in (charged, discharged)]
    known = {u for u in units if u}
    if len(known) == 2:
        unit_text = t["units_split"].format(charged=units[0], discharged=units[1])
    else:
        unit_text = t["unit"].format(unit=known.pop()) if known else ""
    boundary = (
        Boundary.SYSTEM
        if data.get(CONF_BOUNDARY) == Boundary.SYSTEM
        else Boundary.BATTERY
    )
    lines.append(
        t["counters"].format(
            kind=t["day" if day_values else "lifetime"],
            units=unit_text,
            boundary=t[boundary.value],
        )
    )

    soc = sources.get(Signal.SOC)
    soc_read = soc is not None and soc.problem != OWN
    if not soc_read:
        lines.append(t["soc_not_read"])
    elif soc.value is not None:
        lines.append(t["soc"].format(value=format_number(soc.value, lang, 1)))
    else:
        lines.append(t["soc_no_value"])

    capacity = t["capacity"].format(kwh=format_number(float(data[CONF_CAPACITY]), lang))
    if analysis is not None and soc_read:
        estimate = analysis.capacity.kwh
        capacity += ", " + (
            t["estimate"].format(kwh=format_number(estimate, lang))
            if estimate is not None
            else t["estimate_open"].format(
                samples=MIN_CAPACITY_SAMPLES,
                full=format_number(FULL_SOC, lang, 0),
                empty=format_number(EMPTY_SOC, lang, 0),
                days=CAPACITY_WINDOW.days,
            )
        )
    lines.append(capacity)

    names = (
        [t["efficiency"], t["cycles"], t["rest_loss"], t["capacity_estimate"]]
        if soc_read
        else [t["cycles"]]
    )
    warranty = data.get(CONF_WARRANTY_MWH)
    if warranty:
        names.append(t["warranty"].format(mwh=format_number(float(warranty), lang)))
    lines.append(t["evaluated"].format(names=", ".join(names)))

    if analysis is None:
        lines.append(t["not_read"])
    elif analysis.first_day is not None:
        lines.append(t["since"].format(date=format_date(analysis.first_day, lang)))

    hints = _hints(t, sources, analysis, day_counter, bool(warranty))
    return _markdown(t, lines, hints)


def _source_line(
    t: Mapping[str, str],
    template_label: str | None,
    energy_dashboard: bool,
    tarifwacht: str | None,
) -> str:
    if template_label:
        return t["source_template"].format(label=template_label)
    if energy_dashboard:
        return t["source_energy"]
    if tarifwacht:
        return t["source_tarifwacht"].format(title=tarifwacht)
    return t["source_own"]


def _hints(
    t: Mapping[str, str],
    sources: Mapping[Signal, Source],
    analysis: Analysis | None,
    day_counter: bool,
    warranty: bool,
) -> list[str]:
    """What is missing, each with what it costs; only what matters."""
    hints: list[str] = []
    for signal in (Signal.CHARGED, Signal.DISCHARGED):
        source = sources.get(signal)
        if source is None or source.problem not in (MISSING, UNIT):
            continue
        hints.append(
            t[f"hint_counter_{source.problem}"].format(
                role=t[signal.value], entity=source.entity_id, unit=source.unit
            )
        )
    soc = sources.get(Signal.SOC)
    if soc is not None and soc.problem is not None:
        hints.append(
            t[f"hint_soc_{soc.problem}"].format(
                entity=soc.entity_id, unit=soc.unit or "–"
            )
        )
    if day_counter:
        hints.append(t["hint_day_counter"])
    if analysis is not None and analysis.first_day is None:
        hints.append(t["hint_no_data"])
    if not warranty:
        hints.append(t["hint_warranty"])
    return hints


def _markdown(t: Mapping[str, str], lines: list[str], missing: list[str]) -> str:
    blocks = [
        "\n".join([t[heading], *(f"- {line}" for line in items)])
        for heading, items in (("configured", lines), ("missing", missing))
        if items
    ]
    return "\n\n".join(blocks)
