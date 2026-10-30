"""Generate strings.json, translations/en.json, de.json and icons.json for Speicherwacht.

Run from the repository root: uv run python tools/make_strings.py .
Texts are changed here, never in the generated files.
"""

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) / "custom_components" / "speicherwacht"

PERIODS = {
    "today": ("today", "heute"),
    "month": ("month", "Monat"),
    "year": ("year", "Jahr"),
    "total": ("total", "gesamt"),
}
SENSORS = {
    "full_cycles_total": ("Full cycles total", "Vollzyklen gesamt", "mdi:battery-sync"),
    "full_cycles_year": ("Full cycles year", "Vollzyklen Jahr", "mdi:battery-sync"),
    "rest_loss": ("Rest loss", "Ruheverlust", "mdi:battery-clock"),
    "warranty_used": (
        "Warranted throughput used",
        "Garantie-Durchsatz genutzt",
        "mdi:shield-check-outline",
    ),
    "capacity_estimate": (
        "Capacity (estimated)",
        "Kapazität (geschätzt)",
        "mdi:battery-heart-variant",
    ),
}
EFFICIENCY = ("Efficiency", "Wirkungsgrad", "mdi:battery-charging-high")
BINARY = {
    "efficiency_drop": (
        "Efficiency below last year",
        "Wirkungsgrad unter Vorjahr",
        "mdi:battery-arrow-down",
    ),
    "capacity_low": ("Capacity low", "Kapazität gesunken", "mdi:battery-alert"),
    "rest_loss_high": (
        "Rest loss high",
        "Ruheverlust hoch",
        "mdi:battery-clock-outline",
    ),
}

USER = {
    "title": ("Battery storage", "Batteriespeicher"),
    "description": (
        "Speicherwacht reads the counters of your battery (energy charged and "
        "discharged, lifetime) and its state of charge from their long-term "
        "statistics. Pick a detected storage or map the entities yourself.",
        "Speicherwacht liest die Zähler deines Speichers (geladen und entladen, "
        "Lebenszeit) und seinen Ladezustand aus der Langzeitstatistik. Wähle "
        "einen erkannten Speicher oder ordne die Entitäten selbst zu.",
    ),
    "data": {
        "name": ("Name", "Name"),
        "source": ("Source", "Quelle"),
    },
    "data_description": {
        "name": (
            "Name of the device Speicherwacht creates.",
            "Name des Geräts, das Speicherwacht anlegt.",
        ),
        "source": (
            "Templates marked (beta) were built from the integration's source code and are not yet confirmed on a real installation.",
            "Mit (beta) markierte Vorlagen stammen aus dem Quellcode der Integration und sind an einer echten Anlage noch nicht bestätigt.",
        ),
    },
}
HINTS = {
    "goodwe": (
        "GoodWe: an inverter was found without battery lifetime counters. Only the ET family (ET, EH, BT, BH and newer ES/EM G2) provides them; ES, EM and BP show the state of charge only. Map counters yourself, e.g. with Integral helpers.",
        "GoodWe: Ein Wechselrichter hat keine Lebenszeit-Zähler für den Akku. Nur die ET-Familie (ET, EH, BT, BH und neuere ES/EM G2) liefert sie; ES, EM und BP zeigen nur den Ladezustand. Ordne Zähler selbst zu, z. B. mit Integral-Helfern.",
    ),
    "victron_gx": (
        "Victron: a battery was found without lifetime counters. They come from a battery monitor (SmartShunt, BMV); batteries reporting over a CAN BMS do not have them. Choose the battery monitor, or map counters yourself.",
        "Victron: Ein Akku hat keine Lebenszeit-Zähler. Sie kommen von einem Batteriemonitor (SmartShunt, BMV); Akkus mit CAN-BMS liefern sie nicht. Wähle den Batteriemonitor oder ordne Zähler selbst zu.",
    ),
    "solax_modbus": (
        "SolaX: the lifetime battery counters are disabled. Enable 'Battery Input Energy Total' and 'Battery Output Energy Total' in the SolaX device, reload the integration, then start this setup again.",
        "SolaX: Die Lebenszeit-Zähler des Akkus sind deaktiviert. Aktiviere im SolaX-Gerät „Battery Input Energy Total“ und „Battery Output Energy Total“, lade die Integration neu und starte diese Einrichtung erneut.",
    ),
    "anker_solix": (
        "Anker SOLIX: a Solarbank was found without lifetime counters. They "
        "come only by MQTT with the owner account, and the integration leaves "
        "them out until you allow the energy category: Anker SOLIX → Configure "
        "→ remove 'solarbank_energy' from the excluded categories, enable MQTT.",
        "Anker SOLIX: Eine Solarbank hat keine Lebenszeit-Zähler. Sie kommen "
        "nur per MQTT mit dem Eigentümer-Konto, und die Integration legt sie "
        "erst an, wenn du die Energie-Kategorie freigibst: Anker SOLIX → "
        "Konfigurieren → „solarbank_energy“ aus den ausgeschlossenen Kategorien "
        "nehmen, MQTT einschalten.",
    ),
}
ENTITIES = {
    "title": ("Entities and capacity", "Entitäten und Kapazität"),
    "description": (
        "Counters need a state class (total or total_increasing), the state "
        "of charge the state class measurement: Speicherwacht works from "
        "their long-term statistics, including the time before the setup.",
        "Zähler brauchen eine Zustandsklasse (total oder total_increasing), "
        "der Ladezustand die Zustandsklasse measurement: Speicherwacht rechnet "
        "aus deren Langzeitstatistik, auch für die Zeit vor der Einrichtung.",
    ),
    "data": {
        "charged": ("Energy charged (lifetime)", "Energie geladen (Lebenszeit)"),
        "discharged": ("Energy discharged (lifetime)", "Energie entladen (Lebenszeit)"),
        "soc": ("State of charge", "Ladezustand"),
        "capacity": ("Usable capacity", "Nutzbare Kapazität"),
        "boundary": ("The counters measure", "Die Zähler messen"),
        "warranty_mwh": (
            "Warranted throughput (optional)",
            "Garantie-Durchsatz (optional)",
        ),
    },
    "data_description": {
        "charged": (
            "Energy into the battery. Only power in W? Create a counter with the helper 'Integral' (left Riemann sum).",
            "Energie in den Akku. Nur Leistung in W? Lege mit dem Helfer „Integral“ (linke Riemann-Summe) einen Zähler an.",
        ),
        "discharged": ("Energy out of the battery.", "Energie aus dem Akku."),
        "soc": ("In %.", "In %."),
        "capacity": (
            "From the data sheet (usable, not gross). Needed for the state of charge correction and full cycles; the estimated capacity never replaces it.",
            "Laut Datenblatt (nutzbar, nicht brutto). Nötig für die Korrektur über den Ladezustand und die Vollzyklen; die geschätzte Kapazität ersetzt sie nie.",
        ),
        "boundary": (
            "Results of the two boundaries are not comparable.",
            "Ergebnisse der beiden Grenzen sind nicht vergleichbar.",
        ),
        "warranty_mwh": (
            "Energy the warranty covers, in MWh discharged (data sheet or warranty terms). Adds the sensor 'Warranted throughput used'.",
            "Energie, die die Garantie abdeckt, in MWh entladen (Datenblatt oder Garantiebedingungen). Ergibt den Sensor „Garantie-Durchsatz genutzt“.",
        ),
    },
}
ERRORS = {
    "counter_in_use": (
        "This charge counter already belongs to another Speicherwacht entry.",
        "Dieser Ladezähler gehört schon zu einem anderen Speicherwacht-Eintrag.",
    ),
    "day_counter": (
        "A counter fell back several times in the last days: it looks like a day counter (energy today). Speicherwacht needs lifetime counters (total energy).",
        "Ein Zähler ist in den letzten Tagen mehrmals zurückgefallen: Er sieht nach einem Tageszähler aus (Energie heute). Speicherwacht braucht Lebenszeit-Zähler (Gesamtenergie).",
    ),
    "same_entity": (
        "Choose three different entities.",
        "Wähle drei verschiedene Entitäten.",
    ),
    "entity_missing": (
        "An entity does not exist (yet).",
        "Eine Entität existiert (noch) nicht.",
    ),
    "soc_unit": (
        "The state of charge must be in %.",
        "Der Ladezustand muss in % sein.",
    ),
    "soc_statistics": (
        "The state of charge has no long-term statistics (state class measurement missing).",
        "Der Ladezustand hat keine Langzeitstatistik (Zustandsklasse measurement fehlt).",
    ),
    "energy_unit": (
        "Counters must be in Wh, kWh or MWh.",
        "Zähler müssen in Wh, kWh oder MWh sein.",
    ),
    "counter_statistics": (
        "A counter has no long-term statistics (state class total or total_increasing missing).",
        "Ein Zähler hat keine Langzeitstatistik (Zustandsklasse total oder total_increasing fehlt).",
    ),
}
ABORTS = {
    "already_configured": (
        "This storage is already set up.",
        "Dieser Speicher ist schon eingerichtet.",
    ),
    "reconfigure_successful": (
        "Saved. Speicherwacht reloads.",
        "Gespeichert. Speicherwacht lädt neu.",
    ),
}
SOURCE_MANUAL = ("Map entities myself", "Eigene Zuordnung")
BOUNDARY = {
    "battery": (
        "the battery (DC, e.g. inverter battery counters)",
        "den Akku (DC, z. B. Batteriezähler des Wechselrichters)",
    ),
    "system": (
        "the whole storage (AC, e.g. a plug meter in front of it)",
        "den ganzen Speicher (AC, z. B. Zwischenstecker davor)",
    ),
}
ISSUES = {
    "counter_soc_mismatch": (
        "Speicherwacht: counters and state of charge disagree",
        "Speicherwacht: Zähler und Ladezustand passen nicht zusammen",
        "Over the last day the state of charge of {name} and its counters told different stories (the state of charge moved while the counters stood still, or the other way round). Check these entities: {entities}. A stuck counter, a frozen state of charge or a wrong mapping (Reconfigure) are the usual causes. The issue disappears once both move together again.",
        "Bei {name} haben Ladezustand und Zähler im letzten Tag nicht zusammengepasst (der Ladezustand hat sich bewegt, die Zähler standen – oder umgekehrt). Prüfe diese Entitäten: {entities}. Meist hängt ein Zähler, der Ladezustand ist eingefroren oder etwas ist falsch zugeordnet (Neu konfigurieren). Der Hinweis verschwindet, sobald beide wieder zusammenpassen.",
    ),
    "counter_resets": (
        "Speicherwacht: counter starts anew again and again",
        "Speicherwacht: Zähler beginnt immer wieder neu",
        "These counters of {name} started anew at least 3 times in the last 7 days: {entities}. That is how a day counter (energy today) behaves; Speicherwacht then counts too little. Choose lifetime counters (total energy) under Settings → Devices & services → Speicherwacht → ⋮ → Reconfigure.",
        "Diese Zähler von {name} haben in den letzten 7 Tagen mindestens 3-mal neu begonnen: {entities}. So verhält sich ein Tageszähler (Energie heute); Speicherwacht zählt dann zu wenig. Wähle unter Einstellungen → Geräte & Dienste → Speicherwacht → ⋮ → Neu konfigurieren Lebenszeit-Zähler (Gesamtenergie).",
    ),
    "missing_entity": (
        "Speicherwacht: entity missing",
        "Speicherwacht: Entität fehlt",
        "These entities of {name} do not exist: {entities}. Choose others under Settings → Devices & services → Speicherwacht → ⋮ → Reconfigure.",
        "Diese Entitäten von {name} gibt es nicht: {entities}. Wähle unter Einstellungen → Geräte & Dienste → Speicherwacht → ⋮ → Neu konfigurieren andere.",
    ),
    "source_unavailable": (
        "Speicherwacht: source not available",
        "Speicherwacht: Quelle nicht erreichbar",
        "These entities of {name} have been unavailable for more than {minutes} minutes: {entities}. Speicherwacht lacks values meanwhile. Check the source integration. The issue disappears once values arrive again.",
        "Diese Entitäten von {name} sind seit mehr als {minutes} Minuten nicht verfügbar: {entities}. Solange fehlen Speicherwacht Werte. Prüfe die Quell-Integration. Der Hinweis verschwindet, sobald wieder Werte kommen.",
    ),
    "source_unit": (
        "Speicherwacht: unexpected unit",
        "Speicherwacht: unerwartete Einheit",
        "These entities of {name} have a unit Speicherwacht cannot use (counters Wh/kWh/MWh, state of charge %): {entities}. Choose others under Reconfigure.",
        "Diese Entitäten von {name} haben eine Einheit, mit der Speicherwacht nicht rechnen kann (Zähler Wh/kWh/MWh, Ladezustand %): {entities}. Wähle unter Neu konfigurieren andere.",
    ),
}


def _pick(table: dict, lang: int) -> dict:
    return {k: v[lang] for k, v in table.items()}


def build(lang: int) -> dict:
    user = {
        "title": USER["title"][lang],
        "description": USER["description"][lang],
        "data": _pick(USER["data"], lang),
        "data_description": _pick(USER["data_description"], lang),
    }
    steps = {"user": user}
    for key, text in HINTS.items():
        steps[f"user_hint_{key}"] = {
            **user,
            "description": user["description"] + "\n\n" + text[lang],
        }
    steps["entities"] = {
        "title": ENTITIES["title"][lang],
        "description": ENTITIES["description"][lang],
        "data": _pick(ENTITIES["data"], lang),
        "data_description": _pick(ENTITIES["data_description"], lang),
    }
    sensor = {
        f"efficiency_{key}": {"name": f"{EFFICIENCY[lang]} {period[lang]}"}
        for key, period in PERIODS.items()
    }
    sensor.update({k: {"name": v[lang]} for k, v in SENSORS.items()})
    return {
        "config": {
            "step": steps,
            "error": _pick(ERRORS, lang),
            "abort": _pick(ABORTS, lang),
        },
        "selector": {
            "source": {"options": {"manual": SOURCE_MANUAL[lang]}},
            "boundary": {"options": _pick(BOUNDARY, lang)},
        },
        "entity": {
            "sensor": sensor,
            "binary_sensor": {k: {"name": v[lang]} for k, v in BINARY.items()},
        },
        "issues": {
            key: {"title": text[lang], "description": text[2 + lang]}
            for key, text in ISSUES.items()
        },
    }


def icons() -> dict:
    sensor = {f"efficiency_{key}": {"default": EFFICIENCY[2]} for key in PERIODS}
    sensor.update({k: {"default": v[2]} for k, v in SENSORS.items()})
    return {
        "entity": {
            "sensor": sensor,
            "binary_sensor": {k: {"default": v[2]} for k, v in BINARY.items()},
        }
    }


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


write(ROOT / "strings.json", build(0))
write(ROOT / "translations" / "en.json", build(0))
write(ROOT / "translations" / "de.json", build(1))
write(ROOT / "icons.json", icons())
print("ok")
