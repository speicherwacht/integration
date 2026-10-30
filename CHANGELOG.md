# Changelog

## Unveröffentlicht

- **Gesundheits-Check:** drei Problem-Sensoren – „Wirkungsgrad unter Vorjahr“ (letzte 30 Tage mindestens 3 Punkte unter denselben Tagen des Vorjahres), „Kapazität gesunken“ (unter 80 % des Datenblatts oder 10 Punkte unter dem Vorjahr), „Ruheverlust hoch“ (über 64 W oder deutlich über dem Vorjahr) – und der Reparaturhinweis „Zähler und Ladezustand passen nicht zusammen“. Regeln und Quellen in `docs/GESUNDHEITSCHECK.md`.

## 0.1.0b2 – 2026-10-30

Korrekturen nach einer unabhängigen Durchsicht:

- **Teiltage zählen nicht mehr:** Ein Tag geht nur in den Wirkungsgrad ein, wenn die Zähler an beiden Mitternächten einen Wert hatten. Bisher verfälschte der erste Tag der Zähler den Wirkungsgrad, wenn der Ladezustand schon länger aufgezeichnet wurde (bei Fronius typisch: Zähler erst mit Modbus TCP) – in einer Simulation um bis zu 2 Prozentpunkte über einen Monat. Neues Attribut `incomplete_days`.
- **Tageszähler werden erkannt:** Die Einrichtung lehnt Zähler ab, die in den letzten Tagen mehrmals auf unter die Hälfte gefallen sind (Energie heute statt Gesamtenergie). Für bestehende Einträge gibt es den Reparaturhinweis „Zähler beginnt immer wieder neu“.
- **Zeitzonen mit Halbstunden-Versatz** (z. B. Indien, Adelaide): Der Ladezustand an Mitternacht wird jetzt zwischen den Stundenmitteln interpoliert; bisher blieben dort alle Wirkungsgrade unbekannt.
- **Vollzyklen gesamt und Garantie-Durchsatz** rechnen ab dem ersten Zählerstand plus den bereinigten Zuwächsen; ein kurzer Ausreißer des Zählers erscheint nicht mehr. Zustandsklasse `total` (Vollzyklen Jahr mit Rücksetzung am 1. Januar), damit eine geänderte Kapazität nicht als Neustart zählt.
- Ein Ladezähler kann nur noch zu einem Eintrag gehören, auch wenn derselbe Speicher einmal über die Vorlage und einmal von Hand gewählt wird.
- Reparaturhinweise verschwinden auch beim Deaktivieren oder Neuladen des Eintrags; Aufräumen, wenn die Einrichtung abbricht.

## 0.1.0b1 – 2026-10-30

Erste Version (Beta).

- **Wirkungsgrad** je Monat, Jahr und gesamt (je Tag deaktiviert) aus Lade- und Entladezähler, korrigiert um die Änderung des Ladezustands; Ruhetage (Laden und Entladen je unter 5 % der Kapazität) zählen getrennt.
- **Vollzyklen** seit Inbetriebnahme (Zählerstand) und im Jahr, optional **Garantie-Durchsatz genutzt**.
- **Ruheverlust** in W aus Ruhephasen der letzten 30 Tage.
- **Kapazität (geschätzt)** aus Entladungen von voll bis leer, im Vergleich zum Datenblatt.
- Alles aus der Langzeitstatistik, auch für die Zeit vor der Einrichtung; keine eigene Speicherdatei.
- Vorlagen: Fronius (Core, Modbus TCP), als Beta Huawei Solar, solarman, Anker SOLIX (Cloud) und Anker SOLIX (offiziell). Eigene Zuordnung mit Vorschlag aus dem Energie-Dashboard.
- Reparaturhinweise: Entität fehlt, Quelle nicht erreichbar, unerwartete Einheit.
