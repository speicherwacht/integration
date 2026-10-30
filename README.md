<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/github/readme-header-dark@2x.png">
  <img alt="Speicherwacht – Jede Ladung. Jeder Zyklus." src="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/github/readme-header-light@2x.png" width="640">
</picture>

[![Release](https://img.shields.io/github/v/release/speicherwacht/integration?color=007D7F)](https://github.com/speicherwacht/integration/releases)
[![CI](https://github.com/speicherwacht/integration/actions/workflows/ci.yml/badge.svg)](https://github.com/speicherwacht/integration/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623.svg)](LICENSE)

**Deutsch** · [English](https://github.com/speicherwacht/integration/blob/main/README.en.md)

**Wie gut arbeitet mein Batteriespeicher wirklich?** Speicherwacht ist eine Home-Assistant-Integration, die aus den vorhandenen Zählern deines Heim- oder Balkonspeichers den Wirkungsgrad je Monat und Jahr, die Vollzyklen, den Ruheverlust und die tatsächlich entnehmbare Kapazität berechnet – herstellerneutral, nur lesend, ohne Cloud.

> **Beta.** Speicherwacht ist neu. Die Vorlage für Fronius ist an einer echten Anlage erprobt, die übrigen stammen aus dem Quellcode der jeweiligen Integration. Rückmeldungen sind willkommen.

## Inhalt

- [Was Speicherwacht kann](#was-speicherwacht-kann) · [Voraussetzungen](#voraussetzungen) · [Installation](#installation) · [Einrichtung](#einrichtung)
- [Entitäten](#entitäten) · [Gesundheits-Check](#gesundheits-check) · [Wie gerechnet wird](#wie-gerechnet-wird) · [Grenzen der Aussage](#grenzen-der-aussage)
- [Fehlerbehebung](#fehlerbehebung) · [Datenschutz](#datenschutz) · [Entfernen](#entfernen) · [Verwandte Projekte](#verwandte-projekte)

## Was Speicherwacht kann

- **Wirkungsgrad** je Monat, Jahr und gesamt (je Tag abschaltbar): Entladung gegen Ladung, korrigiert um die Änderung des Ladezustands. Ohne diese Korrektur schwankt ein Monatswert mit dem Füllstand am Monatsende.
- **Ruhetage getrennt:** Tage, an denen der Speicher kaum arbeitet (Winter, Notstrom-Reserve, Wartung), zählen nicht in den Wirkungsgrad; ihre Verluste stehen als eigenes Attribut daneben.
- **Vollzyklen** seit Inbetriebnahme und im laufenden Jahr, optional **Garantie-Durchsatz genutzt** in %.
- **Ruheverlust:** mittlere Leistung, die der ruhende Speicher verliert (meist der Eigenverbrauch des Batteriemanagements).
- **Kapazität (geschätzt):** entnehmbare Energie aus Entladungen von voll bis leer, im Vergleich zum Datenblatt.
- **Rückblick ab dem ersten Tag:** Speicherwacht rechnet aus der Langzeitstatistik von Home Assistant, also auch für die Zeit vor der Einrichtung.
- **Reparaturhinweise**, wenn eine Quelle fehlt, lange nicht verfügbar ist oder eine falsche Einheit hat.
- Keine eigene Speicherdatei, keine zusätzliche Schreiblast auf SD-Karten.

## Voraussetzungen

- Home Assistant **2026.4** oder neuer, mit Recorder.
- Drei Entitäten deines Speichers, jeweils **mit Langzeitstatistik**:
  - **Energie geladen** und **Energie entladen** als Lebenszeit-Zähler (Wh, kWh oder MWh; Zustandsklasse `total` oder `total_increasing`),
  - **Ladezustand** in % (Zustandsklasse `measurement`).
- Die **nutzbare Kapazität** laut Datenblatt.
- **Nur Leistung (W), keine Zähler?** Lege mit dem Helfer *Integral* (Einstellungen → Geräte & Dienste → Helfer → Integral, Methode „Links“) je einen Zähler für Laden und Entladen an. Die Rückschau beginnt dann mit dem Anlegen der Helfer.

## Installation

Speicherwacht wird über HACS als benutzerdefiniertes Repository installiert. Jede Version ist ein reguläres GitHub-Release.

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/speicherwacht/integration`, Typ *Integration*.
2. Speicherwacht suchen und herunterladen. Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Speicherwacht*.

## Einrichtung

Im ersten Schritt zeigt Speicherwacht die Speicher, die es erkannt hat, und „Eigene Zuordnung“. Im zweiten Schritt prüfst du die Entitäten, trägst die nutzbare Kapazität ein und wählst, was die Zähler messen.

| Quelle | Integration | Stand |
| --- | --- | --- |
| Fronius GEN24 mit Speicher | Core `fronius` mit Modbus TCP (ab HA 2026.9) | erprobt |
| Huawei SUN2000 mit LUNA2000 | [huawei_solar](https://github.com/wlcrs/huawei_solar) | experimentell (beta) |
| Deye und andere über Solarman-Logger | [solarman](https://github.com/davidrapan/ha-solarman) | experimentell (beta) |
| Anker SOLIX Solarbank 1–4 | [anker_solix](https://github.com/thomluther/ha-anker-solix) | experimentell (beta) |
| Anker SOLIX Solarbank 4, Max, XE | [anker_solix_official](https://github.com/anker-charging/ha-anker-solix-official) | experimentell (beta) |
| alle anderen | eigene Zuordnung | – |

- **Eigene Zuordnung:** Hast du den Speicher im Energie-Dashboard eingetragen, übernimmt Speicherwacht Zähler, Ladezustand und Kapazität von dort als Vorschlag.
- **Fronius:** Ohne Modbus TCP liefert die Integration keine Batteriezähler; dann bleibt die eigene Zuordnung (z. B. mit Integral-Helfern).
- **Anker SOLIX (Cloud):** Die Lebenszeit-Zähler kommen nur per MQTT mit dem Eigentümer-Konto, und die Integration legt sie erst an, wenn du die Kategorie `solarbank_energy` in ihren Optionen nicht mehr ausschließt. Speicherwacht weist in der Einrichtung darauf hin.
- **Die Zähler messen:** *den Akku* (DC, z. B. die Batteriezähler des Wechselrichters) oder *den ganzen Speicher* (AC, z. B. ein Zwischenstecker vor einem Balkonspeicher). Die Werte beider Grenzen sind nicht vergleichbar; AC enthält die Verluste des Wechselrichters.
- **Garantie-Durchsatz (optional):** die Energie in MWh, die die Garantie abdeckt (Garantiebedingungen deines Speichers). Dann entsteht der Sensor „Garantie-Durchsatz genutzt“.
- **Neu konfigurieren:** Geräte & Dienste → Speicherwacht → ⋮ → *Neu konfigurieren*.

Nach der Einrichtung rechnet Speicherwacht nach etwa einer Minute zum ersten Mal und dann jede Stunde (kurz nach :12, wenn Home Assistant die Stundenstatistik geschrieben hat).

## Entitäten

| Entität | Bedeutung |
| --- | --- |
| Wirkungsgrad Monat / Jahr / gesamt | Entladung + Änderung der gespeicherten Energie, geteilt durch Ladung, über die Betriebstage. „gesamt“ beginnt mit der Langzeitstatistik der Zähler. |
| Wirkungsgrad heute | wie oben für den laufenden Tag; standardmäßig deaktiviert, weil ein einzelner Tag stark vom Ladezustand an den Grenzen abhängt |
| Vollzyklen gesamt | Entladung seit Inbetriebnahme (Zählerstand) geteilt durch die Kapazität |
| Vollzyklen Jahr | Entladung im Kalenderjahr geteilt durch die Kapazität |
| Garantie-Durchsatz genutzt | Entladung seit Inbetriebnahme in % des Garantie-Durchsatzes (nur, wenn eingetragen) |
| Ruheverlust | mittlere Verlustleistung in Ruhephasen der letzten 30 Tage, in W |
| Kapazität (geschätzt) | Median der entnehmbaren Energie je 100 % Ladezustand aus Entladungen von voll bis leer (90 Tage) |

Attribute zeigen, woraus ein Wert entsteht: geladen, entladen, Änderung der gespeicherten Energie, Betriebs- und Ruhetage, Verlust an Ruhetagen, Bilanzgrenze, Zeitraum. Ist ein Wert unbekannt, nennt `reason` den Grund:

| `reason` | Bedeutung |
| --- | --- |
| `not_analysed_yet` | noch nicht gerechnet (etwa eine Minute nach dem Start) |
| `no_recorder` | Recorder nicht aktiv |
| `no_data` | im Zeitraum keine Zählerwerte |
| `too_little_charge` | weniger geladen als eine Kapazität (Tag: eine halbe) |
| `no_soc` | kein Ladezustand an den Tagesgrenzen |
| `too_few_rest_hours` | weniger als 24 Ruhestunden in 30 Tagen |
| `too_few_discharges` | weniger als drei Entladungen von voll bis leer in 90 Tagen |

## Gesundheits-Check

Drei Problem-Sensoren (an = auffällig, unbekannt = noch zu wenig Daten, Grund im Attribut `reason`) und ein Reparaturhinweis. Sie sagen, *was* auffällt, nicht *warum* – keine Fachdiagnose.

| Entität | An, wenn … |
| --- | --- |
| Wirkungsgrad unter Vorjahr | der Wirkungsgrad der letzten 30 Tage mindestens 3 Prozentpunkte unter denselben 30 Tagen des Vorjahres liegt (Vergleich mit dem Vorjahr, weil der Wirkungsgrad mit der Jahreszeit schwankt) |
| Kapazität gesunken | die geschätzte Kapazität unter 80 % des Datenblatts liegt (Lebensende im Feld) oder 10 Punkte unter der Schätzung vor einem Jahr (normal sind 2–3 Punkte pro Jahr) |
| Ruheverlust hoch | der Ruheverlust über 64 W liegt (höchster Stand-by-Wert im Labortest der HTW Berlin) oder mindestens 50 % und 10 W über denselben Tagen des Vorjahres |

**Reparaturhinweis „Zähler und Ladezustand passen nicht zusammen“:** Im letzten Tag hat sich der Ladezustand stark bewegt und die Zähler nicht – oder umgekehrt. Meist hängt ein Zähler, der Ladezustand ist eingefroren oder eine Entität ist falsch zugeordnet.

Die Vergleiche mit dem Vorjahr brauchen ein Jahr Langzeitstatistik; vorher sind diese Prüfungen unbekannt. Regeln, Quellen und Schwellen: [docs/GESUNDHEITSCHECK.md](docs/GESUNDHEITSCHECK.md).

## Wie gerechnet wird

- **Grundlage** sind die Stundenwerte der Langzeitstatistik. Speicherwacht liest den Zählerstand je Stunde und fängt Rücksprünge, Neustarts des Zählers und Ausreißer selbst ab (manche Integrationen melden Zähler ohne Reset-Kennung oder kurz einen falschen Wert).
- **Korrektur über den Ladezustand:** Wirkungsgrad = (Entladung + ΔLadezustand × Kapazität) / Ladung. Das ist eine **eigene Näherung**: Prüfstände wie die HTW-Stromspeicher-Inspektion messen stattdessen nur zwischen gleichen Ladezuständen (voll → leer → voll). Über einen Monat oder ein Jahr bleibt der Unterschied klein (unter 1 %), weil der Durchsatz viele Kapazitäten beträgt; einzelne Tage schwanken stärker.
- **Ruhetag:** Laden und Entladen jeweils unter 5 % der Kapazität.
- **Ruheverlust:** Abfall des Ladezustands in Stunden ohne nennenswertes Laden oder Entladen, mindestens drei Stunden am Stück.
- **Kapazität (geschätzt):** nur aus Entladungen von mindestens 90 % bis höchstens 15 % Ladezustand, ohne Laden dazwischen. Kleinere Hübe zählen nicht, weil der Ladezustand vom Batteriemanagement berechnet wird und sonst nur dessen eigene Annahme zurückkäme.
- **Vollzyklen** zählen wie die Garantien die abgegebene Energie.

Quellen und Begründungen: [docs/ENTWICKLUNG.md](docs/ENTWICKLUNG.md), Abschnitt 3.

## Grenzen der Aussage

- Speicherwacht ist eine **Orientierung, keine Fachdiagnose**. Es rechnet mit den Zählern deines Wechselrichters bzw. Speichers – sind die ungenau, sind es die Ergebnisse auch.
- Der Ladezustand ist bei LFP-Akkus ein berechneter Wert und kann springen (z. B. bei einer Kalibrierladung). Ein Sprung an einer Monatsgrenze verschiebt den Wirkungsgrad dieses Monats etwas.
- Ein Labor-Batteriewirkungsgrad (DC) liegt bei aktuellen Heimspeichern um 95–97 %. Im Alltag liegen Werte darunter: Teillast, Eigenverbrauch des Batteriemanagements und Ruhephasen kosten Energie. AC-Werte (Bilanzgrenze „ganzer Speicher“) enthalten zusätzlich die Wandlerverluste.
- Die geschätzte Kapazität streut. Für LFP-Akkus nennt eine Feldstudie der RWTH Aachen (Figgener et al. 2024) rund ±8 Prozentpunkte für ein ausgefeilteres Verfahren. Achte auf den Verlauf über Monate, nicht auf einen Einzelwert.

## Fehlerbehebung

- **Reparaturhinweis „Entität fehlt“, „Quelle nicht erreichbar“ oder „unerwartete Einheit“:** Quell-Integration prüfen oder unter *Neu konfigurieren* andere Entitäten wählen. Die Hinweise verschwinden von selbst.
- **Alle Werte bleiben unbekannt:** Haben die Zähler und der Ladezustand Langzeitstatistik? *Werkzeuge → Statistik* (vor 2026.8: Entwicklerwerkzeuge) zeigt es. Ohne Zustandsklasse gibt es keine.
- **Wirkungsgrad über 100 %:** Meist messen Lade- und Entladezähler an verschiedenen Stellen, oder der Ladezustand ist falsch zugeordnet.
- **Diagnose-Datei:** Geräte & Dienste → Speicherwacht → ⋮ → *Diagnose herunterladen*; sie enthält auch die vom Zählerbaustein verworfenen Werte.

## Datenschutz

Speicherwacht ruft nichts aus dem Netz ab und sendet nichts. Die Diagnose-Datei enthält Energiesummen und die Zustände deiner Quell-Entitäten – prüfe sie, bevor du sie teilst.

## Entfernen

Geräte & Dienste → Speicherwacht → ⋮ → *Löschen*. Speicherwacht legt keine Dateien an; die Langzeitstatistik der eigenen Sensoren bleibt im Recorder, bis du sie unter *Werkzeuge → Statistik* (vor 2026.8: Entwicklerwerkzeuge) löschst. Danach in HACS deinstallieren.

## Fehler melden

[Issue anlegen](https://github.com/speicherwacht/integration/issues/new/choose), möglichst mit Diagnose-Datei, Speichermodell und Integration.

## Verwandte Projekte

- [Marstek Capacity Monitor](https://github.com/satscan1/marstek-capacity-monitor): Kapazitätsmessung, Zyklen und SoC-Drift für Marstek-Speicher. Für Marstek tiefer als Speicherwacht.
- [battery_sim](https://github.com/hif2k1/battery_sim): simuliert, was ein Speicher bringen würde – für die Zeit vor dem Kauf.
- Viele Hersteller-Integrationen (Zendure, Anker SOLIX, Marstek) zeigen eigene Wirkungsgrade, meist Entladung / Ladung ohne Korrektur über den Ladezustand.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
