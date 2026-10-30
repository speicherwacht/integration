# Changelog

## Unveröffentlicht

## 0.1.0b1 – 2026-10-30

Erste Version (Beta).

- **Wirkungsgrad** je Monat, Jahr und gesamt (je Tag deaktiviert) aus Lade- und Entladezähler, korrigiert um die Änderung des Ladezustands; Ruhetage (Laden und Entladen je unter 5 % der Kapazität) zählen getrennt.
- **Vollzyklen** seit Inbetriebnahme (Zählerstand) und im Jahr, optional **Garantie-Durchsatz genutzt**.
- **Ruheverlust** in W aus Ruhephasen der letzten 30 Tage.
- **Kapazität (geschätzt)** aus Entladungen von voll bis leer, im Vergleich zum Datenblatt.
- Alles aus der Langzeitstatistik, auch für die Zeit vor der Einrichtung; keine eigene Speicherdatei.
- Vorlagen: Fronius (Core, Modbus TCP), als Beta Huawei Solar, solarman, Anker SOLIX (Cloud) und Anker SOLIX (offiziell). Eigene Zuordnung mit Vorschlag aus dem Energie-Dashboard.
- Reparaturhinweise: Entität fehlt, Quelle nicht erreichbar, unerwartete Einheit.
