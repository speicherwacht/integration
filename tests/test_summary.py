"""Summary on top of "Reconfigure": what is set up, what is missing."""

from __future__ import annotations

from datetime import date

from custom_components.speicherwacht.analysis import (
    TOO_FEW_DISCHARGES,
    Analysis,
    CapacityEstimate,
    RestLoss,
)
from custom_components.speicherwacht.model import Signal
from custom_components.speicherwacht.summary import (
    MISSING,
    OWN,
    UNIT,
    Source,
    storage_summary,
)

DATA = {"capacity": 10.0, "boundary": "battery", "warranty_mwh": 25.0}
SOURCES = {
    Signal.CHARGED: Source("sensor.charged", "Wh", 1234.0),
    Signal.DISCHARGED: Source("sensor.discharged", "Wh", 1100.0),
    Signal.SOC: Source("sensor.soc", "%", 56.5),
}


def analysis(estimate: float | None, first: date | None) -> Analysis:
    return Analysis(
        efficiency={},
        cycles_total=0.0,
        cycles_year=0.0,
        charged_total=0.0,
        discharged_total=0.0,
        rest=RestLoss(None, 0.0),
        capacity=CapacityEstimate(
            estimate, reason=None if estimate else TOO_FEW_DISCHARGES
        ),
        first_day=first,
    )


def test_template_complete_in_german() -> None:
    text = storage_summary(
        DATA,
        SOURCES,
        template_label="Fronius (GEN24, Modbus TCP)",
        analysis=analysis(9.8, date(2025, 3, 1)),
        language="de",
    )
    assert text == (
        "**Eingerichtet**\n"
        "- Quelle: Vorlage Fronius (GEN24, Modbus TCP)\n"
        "- Zähler: Gesamtzähler (Lebenszeit) in Wh, messen den Akku (DC)\n"
        "- Ladezustand: jetzt 56,5 %\n"
        "- Kapazität: 10 kWh laut Datenblatt, geschätzt 9,8 kWh\n"
        "- Ausgewertet: Wirkungsgrad mit Korrektur über den Ladezustand, "
        "Vollzyklen, Ruheverlust, geschätzte Kapazität, Garantie-Durchsatz (25 MWh)\n"
        "- Daten seit 01.03.2025 (Langzeitstatistik, auch vor der Einrichtung)"
    )


def test_own_mapping_from_the_energy_dashboard_in_english() -> None:
    text = storage_summary(
        {"capacity": 2.24, "boundary": "system"},
        {
            **SOURCES,
            Signal.DISCHARGED: Source("sensor.discharged", "kWh", 1.1),
        },
        template_label=None,
        energy_dashboard=True,
        language="en-GB",
    )
    assert "- Source: own mapping, counters as in the energy dashboard\n" in text
    assert (
        "- Counters: lifetime counters, charged in Wh, discharged in kWh, "
        "measuring the whole storage (AC)\n"
    ) in text
    # Not analysed yet: no estimate, no start of the data.
    assert "- Capacity: 2.24 kWh from the data sheet\n" in text
    assert "- Data: not read yet (shortly after the start)" in text
    assert text.endswith(
        "**Missing**\n"
        "- No warranted throughput (under “More”): no sensor “Warranted "
        "throughput used”."
    )


def test_own_mapping_from_tarifwacht() -> None:
    text = storage_summary(
        DATA,
        SOURCES,
        template_label=None,
        tarifwacht="Haus",
        analysis=analysis(None, date(2026, 1, 5)),
        language="de",
    )
    assert "- Quelle: eigene Zuordnung, Zähler wie in Tarifwacht „Haus“\n" in text
    assert (
        "- Kapazität: 10 kWh laut Datenblatt, Schätzung offen (braucht 3 "
        "Entladungen von ≥ 90 % bis ≤ 15 % in 90 Tagen)\n"
    ) in text
    assert "Was fehlt" not in text


def test_plain_own_mapping() -> None:
    text = storage_summary(DATA, SOURCES, template_label=None, language="de")
    assert text.startswith("**Eingerichtet**\n- Quelle: eigene Zuordnung\n")


def test_state_of_charge_not_read() -> None:
    """An own sensor as state of charge (entries up to 0.1.3) is not read:
    only the full cycles remain."""
    text = storage_summary(
        DATA,
        {**SOURCES, Signal.SOC: Source("sensor.akku_month", "%", 93.0, OWN)},
        template_label=None,
        analysis=analysis(None, date(2026, 1, 5)),
        language="de",
    )
    assert "- Ladezustand: wird nicht gelesen\n" in text
    # No estimate without a state of charge.
    assert "- Kapazität: 10 kWh laut Datenblatt\n" in text
    assert "- Ausgewertet: Vollzyklen, Garantie-Durchsatz (25 MWh)\n" in text
    assert text.endswith(
        "**Was fehlt**\n"
        "- Als Ladezustand ist ein Sensor von Speicherwacht selbst gewählt, er "
        "wird nicht gelesen: kein Wirkungsgrad, kein Ruheverlust, keine "
        "geschätzte Kapazität."
    )


def test_state_of_charge_missing() -> None:
    text = storage_summary(
        DATA,
        {**SOURCES, Signal.SOC: Source("sensor.soc", problem=MISSING)},
        template_label=None,
        language="de",
    )
    assert "- Ladezustand: zurzeit ohne Wert\n" in text
    assert (
        "- Ladezustand sensor.soc gibt es nicht: für neue Tage kein "
        "Wirkungsgrad, kein Ruheverlust, keine geschätzte Kapazität."
    ) in text


def test_counter_problems_day_counter_and_no_data() -> None:
    text = storage_summary(
        {"capacity": 5.0},
        {
            Signal.CHARGED: Source("sensor.charged", problem=MISSING),
            Signal.DISCHARGED: Source("sensor.discharged", "W", 300.0, UNIT),
            Signal.SOC: Source("sensor.soc", "%", 40.0),
        },
        template_label=None,
        analysis=analysis(None, None),
        day_counter=True,
        language="de",
    )
    assert "- Zähler: Gesamtzähler (Lebenszeit) in W, messen den Akku (DC)\n" in text
    assert "Daten seit" not in text
    hints = text.split("**Was fehlt**\n", 1)[1].split("\n")
    assert hints == [
        "- Ladezähler sensor.charged gibt es nicht: keine neuen Zahlen, bis er "
        "wieder da ist oder hier ein anderer gewählt ist.",
        "- Entladezähler in W: Speicherwacht rechnet nur mit Wh, kWh oder MWh, "
        "die Zahlen stimmen nicht.",
        "- Ein Zähler beginnt jeden Tag neu wie ein Tageszähler: Speicherwacht "
        "zählt zu wenig – hier einen Gesamtzähler (Lebenszeit) wählen.",
        "- Noch keine Stunde in der Langzeitstatistik: noch keine Zahlen (Home "
        "Assistant schreibt sie stündlich).",
        "- Kein Garantie-Durchsatz (unter „Weitere Angaben“): kein Sensor "
        "„Garantie-Durchsatz genutzt“.",
    ]


def test_day_values_of_a_template() -> None:
    text = storage_summary(
        DATA, SOURCES, template_label="X", day_values=True, language="de"
    )
    assert "- Zähler: Tageszähler (Vorlage) in Wh, messen den Akku (DC)\n" in text
