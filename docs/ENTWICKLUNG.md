# Speicherwacht – Entwicklerdokumentation

Stand: 2026-10-30 (Projektstart, vor 0.1.0b1). Vor größeren Arbeiten lesen. Maßgeblich ist der Code; dieses Dokument erklärt, was dort nicht steht.

## 1. Ziel und Umfang

Speicherwacht wertet aus vorhandenen Home-Assistant-Entitäten aus, wie gut ein Batteriespeicher (Heim- oder Balkonspeicher) arbeitet: Wirkungsgrad, Vollzyklen, Ruheverlust und nutzbare Kapazität. Nur lesen, nie steuern; keine Cloud, keine Abhängigkeiten. Muster ist Wärmewacht.

**MVP (erste Beta)**, entschieden vom Inhaber am 2026-10-30:

- Wirkungsgrad je Tag (standardmäßig aus), Monat, Jahr und gesamt, mit Korrektur über den Ladezustand und ohne Ruhetage.
- Vollzyklen gesamt (seit Inbetriebnahme, aus dem Zählerstand) und im Jahr; optional „Garantie-Durchsatz genutzt“.
- Ruheverlust (mittlere Leistung in Ruhephasen, 30 Tage).
- Kapazität (geschätzt) aus Entladungen von voll bis leer.
- Rückblick: alles aus der Langzeitstatistik, also auch vor der Einrichtung.
- Reparaturhinweise für Datenfehler (Entität fehlt, Quelle nicht verfügbar, falsche Einheit).
- Vorlagen: Fronius (echte Anlage), dazu als Beta Huawei Solar, solarman, Anker SOLIX (Cloud), Anker SOLIX (offiziell, lokal), GoodWe, Victron GX, SolarEdge (solaredge_modbus_multi), SolaX (solax_modbus), Sungrow (Modbus-YAML), Sigenergy, Zendure und Marstek Venus E.

**Später** (nicht im MVP): Wirtschaftlichkeit (Ersparnis, Amortisation; Entscheidung 2026-10-30 „später“), Problem-Sensoren (Wirkungsgrad oder Kapazität gesunken, Ruheverlust hoch), Verluste nach Leistungsklassen, Standby-Signal des Wechselrichters, Aktion „Bericht“.

## 2. Abgrenzung (geprüft 2026-10-30)

| Projekt | Stand | Warum keine Lösung |
| --- | --- | --- |
| [lemuba/ha-battery-storage-roi](https://github.com/lemuba/ha-battery-storage-roi) | 3 ★, ein Upload 23.09.2025, keine Releases/Tests, nicht in HACS | Wirkungsgrad = Entladung / Ladung seit Startdatum, ohne SoC-Korrektur, ohne Monatswerte, Ruheverlust, Kapazität. Schwerpunkt ROI. |
| [satscan1/marstek-capacity-monitor](https://github.com/satscan1/marstek-capacity-monitor) | seit 20.10.2026, HACS-Standardliste, Tests | Nächster Nachbar: DC-Kapazität bei Entladung ≥ 95 → ≤ 15 % SoC, Zyklen, SoC-Drift. **Nur Marstek**, kein Wirkungsgrad, kein Ruheverlust. |
| [hif2k1/battery_sim](https://github.com/hif2k1/battery_sim) | 231 ★, HACS-Standardliste | Simuliert einen virtuellen Speicher; Wirkungsgrad und Alterung sind Eingaben. |
| Zendure-HA, ha-anker-solix, Marstek-Modbus-Integrationen | herstellergebunden | Wirkungsgrad = Entladung / Ladung kumuliert, ohne SoC-Korrektur (Zendure `device.py`, Anker `apibase.py` Z. 1094–1147, Marstek-Register). |
| [davidrapan/ha-solarman](https://github.com/davidrapan/ha-solarman) | HACS-Standardliste | SoH ist eine lineare Abschreibung über den Durchsatz (`sensor.py` Z. 174–187), keine Messung. Kein Wirkungsgrad. |
| HA Core, Energie-Dashboard | bis 2026.11-Beta | Kein Wirkungsgrad, kein Ruheverlust, kein SoH. Seit 2026.6 SoC-Sensor je Speicher, seit 2026.8 Kapazität (für den gewichteten Gesamt-SoC) – Speicherwacht belegt daraus die eigene Zuordnung vor. |
| Karten (universal-battery-card u. a.) | – | Nur Anzeige. |

Name: keine Treffer für „Speicherwacht“/`speicherwacht` auf GitHub (Organisation frei), PyPI, HACS, im Web; Domains .de/.com/.eu laut Index vom 29.10. frei. Marken (2026-10-30, im Browser): DPMAregister (deutsche, Unions- und internationale Marken) ohne Treffer für `?speicherwacht?` und `?speicher?wacht?`; TMview (EUIPO und nationale Ämter der EU) ohne Treffer für „speicherwacht“ (Gegenprobe „tesla“ lieferte Treffer). Keine Rechtsberatung. Bericht: Recherche vom 30.10. (Scratchpad, nicht im Repo).

## 3. Fachregeln

Jede Definition und jeder Feldwert hat eine Quelle; eigene Annahmen sind als solche markiert. Lesart: primär gelesen, wenn nicht anders vermerkt.

### Quellen

| Kürzel | Dokument |
| --- | --- |
| EL | BVES/BSW, [Effizienzleitfaden für PV-Speichersysteme](https://www.solarwirtschaft.de/datawall/uploads/2020/02/effizienzleitfaden_speichersysteme.pdf), V 2.0.1, 07/2019 |
| SSI26 | HTW Berlin/aquu, [Stromspeicher-Inspektion 2026](https://solar.htw-berlin.de/wp-content/uploads/HTW-aquu-Stromspeicher-Inspektion-2026.pdf), V 1.0, März 2026 |
| SSI25 | HTW Berlin, [Stromspeicher-Inspektion 2025](https://solar.htw-berlin.de/wp-content/uploads/HTW-Stromspeicher-Inspektion-2025.pdf) |
| FIG | Figgener et al., [Multi-year field measurements of home storage systems and their use in capacity estimation](https://www.nature.com/articles/s41560-024-01620-9), Nature Energy 9, 1438–1447, 16.09.2024 (Open Access), mit Supplementary Information |

### Wirkungsgrad

- **Batteriewirkungsgrad** = entladene / geladene Energie an den Batterieklemmen (DC), über eine definierte Anzahl Vollzyklen; der BMS-Verbrauch kann ihn senken (EL Kap. 4.9.6, Formel 22). Gemessen wird von voll über leer nach voll (EL Kap. 8.1).
- **Keine Quelle korrigiert über ΔSoC × Kapazität.** EL, SSI25/26 und FIG werten nur Intervalle zwischen gleichen Zuständen aus (voll→voll, leer→leer); im Feld bleibt selbst dann ein Saldo, weil die Endspannung schwankt und BMS/Balancing aus der Batterie gespeist werden (FIG, SI S. 17).
- **Speicherwacht:** Wirkungsgrad = (Entladung + ΔE) / Ladung mit ΔE = (SoC_Ende − SoC_Anfang) / 100 × Kapazität, summiert über die Betriebstage des Zeitraums (`analysis.corrected_ratio`). **Eigene Näherung** (Entscheidung des Inhabers 2026-10-30: beibehalten und kennzeichnen). Sie bucht gespeicherte Energie zum vollen Wert; liegen die Verluste je zur Hälfte beim Laden und Entladen, weicht das um höchstens |ΔE| × (1 − √η) ab. Bei Monat, Jahr und gesamt ist |ΔE| ≤ Kapazität gegen einen Durchsatz von vielen Kapazitäten – der Fehler bleibt unter 1 %. Tageswerte sind unsicherer und deshalb standardmäßig aus.
- **SoC ist ein berechneter Wert.** BYD: Der SoC eines LFP-Akkus „cannot be measured; it is a calculated value“ und kann bei der Korrektur springen ([Service Guideline V1.1, Nr. 27](https://www.bydbatterybox.com/uploads/downloads/BCU2.0_250808_BYD%20Battery-Box%20Premium%20HVS&HVM_Service%20Guideline%20and%20Checklist_V1.1_EN-689566346f0c5.pdf)). Ein Sprung an einer Periodengrenze geht voll in ΔE ein – ein Grund mehr, kurze Zeiträume nicht zu bewerten.
- **Trockenlauf an der Testanlage (2026-10-30, Werte nur in `CLAUDE.local.md`):** Über 15 Monate Stundenstatistik keine verworfenen Zählerwerte; die korrigierten Monatswerte der Sommermonate liegen in einem Band von gut einem Prozentpunkt, die unkorrigierten streuen über sechs Punkte. Fronius-Modbus-Zähler und Riemann-Helfer derselben Anlage liefern denselben Monatswert (±0,3 Punkte).
- **SoC an der Tagesgrenze:** Die Statistik hat nur Stundenmittel. Mitternacht = Mittel der Stunde davor und danach; am Rand der Daten (erste Stunde, laufende Stunde) wird der Trend der zwei nächsten Stunden um eine halbe Stunde verlängert (`days.soc_at`). In der Testsimulation (`tests/sim.py`, 0,8 kW Entladung, Start bei 10/50/90 % SoC) senkte das den Fehler einer Woche von 1,0–1,3 auf höchstens 0,2 Prozentpunkte; ein Monat liegt höchstens 0,05 Punkte daneben (gemessen 2026-10-30).
- **Abdeckung:** Ein Tag zählt nur, wenn beide Zähler in der letzten Stunde vor jeder seiner Mitternächte einen Stand hatten (`Day.covered_start`/`covered_end`). Sonst gehört seine Energie nicht zu derselben Spanne wie sein ΔSoC: erster Tag der Zähler (bei Fronius beginnt die Zählerstatistik mit Modbus TCP, der SoC viel früher), Ausfälle über Mitternacht. Befund der Durchsicht vom 2026-10-30: In der Simulation (Zähler ab 15 Uhr des ersten Tages) lag ein 30-Tage-Wert bei 92,2 statt 90,0 %.
- **Zeitzonen mit Halbstunden-Versatz:** Der SoC an einer Grenze wird zwischen den Mitten der Stundenmittel interpoliert (`days.soc_at`); an vollen Stunden ergibt das das Mittel der Stunde davor und danach.
- **Mindestmenge:** Wirkungsgrad erst ab einer geladenen Energie von 1 × Kapazität (Tag: 0,5 ×), sonst `unknown` mit `too_little_charge` (**eigene Annahme**).
- **Bilanzgrenze:** „Akku“ (DC, Zähler des Wechselrichters am Batterieeingang) oder „System“ (AC, z. B. Zwischenstecker vor einem Balkonspeicher). Je Eintrag eine, als Attribut `boundary` an jedem Wirkungsgrad, nie gemischt. Der EL kennt nur Pfadwirkungsgrade (PV2BAT, AC2BAT, BAT2AC, EL S. 11–12); AC→AC ist ungefähr Laden × Batterie × Entladen (SSI26 S. 42).

### Ruhetage und Ruheverlust

- **Ruhetag:** Laden und Entladen je unter 5 % der Kapazität (**eigene Annahme**). Seine Verluste stehen getrennt (`rest_loss_kwh`) und zählen nicht in den Wirkungsgrad. Hintergrund: Speicher sind 1.250–3.500 h/a leer (SSI25 S. 37; SSI26 S. 26), im Winter oft tagelang; Fronius schaltet dann in „Batterie-Standby“ ([GEN24-Anleitung](https://manuals.fronius.com/html/4204260315/de.html): Energiesparmodus nach 10 min bei SoC ≤ Min-SoC, nach 12 min ohne Betrieb Batterie-Standby). Tage ohne SoC an einer Grenze bleiben ganz außen vor (`days_without_soc`).
- **Ruheverlust:** Läufe von mindestens 3 ruhigen Stunden (Laden + Entladen ≤ 0,5 % der Kapazität je Stunde, Erhaltungsladung des BMS eingeschlossen). Verlust = SoC-Abfall × Kapazität + Ladung − Entladung, je Stunde zwischen dem ersten und letzten Stundenmittel; Mittel über 30 Tage, ab 24 Ruhestunden (alle Schwellen **eigene Annahme**). Ein Ergebnis unter 0 heißt, der Ladezustand stieg in Ruhe (Laden am Ladezähler vorbei, etwa PV direkt in den Akku bei DC-gekoppelten Balkonspeichern, oder SoC-Drift; erste Meldung 30.10.2026, Maxxisun CCU V1, −3 W). Bis zu einer SoC-Stufe von 1 % der Kapazität über alle Ruhestunden gilt es als Rundung und zeigt 0 W (Ladezustände kommen meist in ganzen Prozent; 1 % von 10 kWh über 100 Ruhestunden sind 1 W; **eigene Annahme**), darunter `unknown` mit `reason` `soc_rose_at_rest`, Rohwert im Attribut `raw_watts`. „Ruheverlust hoch“ bleibt dann unbekannt.
- **Was er misst:** vor allem den BMS-Verbrauch aus den Zellen, nicht die Selbstentladung. BYD HVS 12.8: 8 W aus den Zellen, RCT 9 W, bis 37 W (SSI25 S. 38; SSI26 S. 26). Selbstentladung einer LFP-Zelle ≤ 3 %/Monat (EVE LF280N, Datenblatt Ver. A, Pos. 11, über einen Forenspiegel). Stand-by-Verbrauch im leeren Zustand 4–64 W, Mittel 14 W (SSI26 Bild 24, aus Grafik abgelesen); Fronius GEN24 + BYD leer 9–12 W, voll 1–2 W (SSI25 Bild 42/43). Ein AC-seitig versorgter Standby (Wechselrichter) erscheint an DC-Zählern nicht.

### Vollzyklen und Durchsatz

- **Durchsatz = abgegebene Energie.** HTW-Glossar: „Energiedurchsatzmenge = von der Batterie abgegebene Gesamtenergie“ (SSI26 S. 47); BYD zählt für die Garantie die abgegebene Energie ([Garantie V1.2, Kl. 1.3](https://site.bydbatterybox.com/uploads/downloads/BYD%20Battery-Box%20Premium%20HVS&HVM%20Limited%20Warranty-Europe-DE%20V1.2-640eecebbc339.pdf)), ebenso Huawei.
- **Äquivalente Vollzyklen** = Entladung / Kapazität. Eine Formel in Norm oder Studie wurde nicht gefunden; HTW: „Teilzyklen werden zu Vollzyklen aufaddiert“ (SSI26 S. 47). Die Variante „Durchsatz / (2 × Kapazität)“ ergibt bei Wirkungsgraden um 90 % fast dasselbe; gewählt ist die, die zum Garantie-Durchsatz passt.
- **Feldwerte:** 150–300 äquivalente Vollzyklen pro Jahr, garantiert 3.500–10.000 (SSI26 S. 49); ~200/a bei RWTH-Feldanlagen (FIG Fig. 1g).
- **Gesamt seit Inbetriebnahme:** aus dem letzten Zählerstand des Entladezählers (Lebenszeit), nicht aus der Statistiksumme (die beginnt erst mit der Statistik). Bei Tageszählern die Statistiksumme.
- **Garantie-Durchsatz** (optional, MWh): BYD HVS/HVM EU ab 08.03.2023 60 % nach 10 Jahren, z. B. HVS 10.2: 30,82 MWh (V1.2); in Deutschland ab 2020 80 % und HVS 10.2: 24,96 MWh. HTW 2026 nennt für BYD 80 % und 2,4 MWh/kWh (SSI26 Tab. 2) – passt zum Brief von 2020, nicht zu V1.2. Huawei LUNA2000 S0 EU: 60 %, 16,45 MWh je 5-kWh-Modul. Darum **keine Vorgabe**: Der Nutzer trägt den Wert seiner Garantiebedingungen ein.

### Kapazität (geschätzt)

- **SoH** = nutzbare / nominale Kapazität (FIG Gl. 3). Datenblätter enthalten oft eine Alterungsreserve, ein Garantie-SoH von 100 % kann technisch 65 % sein (FIG SI Note 6).
- **Feldmethode (FIG):** Ruhephasen an Lade- und Entladeschluss, Ruhespannung über Ersatzschaltbild, offsetkorrigiertes Coulomb Counting von voll nach leer. Streuung (75-%-Intervall) bei LFP 8,0 Prozentpunkte; Alterung im Feld 2–3 Prozentpunkte pro Jahr; Messungen mit höherer Leistung lagen beim LFP-System unter der Schätzung.
- **Speicherwacht:** nur Entladungen von voll (Höchstwert der ersten Stunde ≥ 90 %) bis leer (Tiefstwert der letzten Stunde ≤ 15 %) ohne Laden dazwischen; Schätzung = Entladung / (SoC-Hub / 100), Median der letzten 10 im 90-Tage-Fenster, ab 3. Grenzen angelehnt an den Marstek Capacity Monitor (≥ 95 → ≤ 15 %), etwas weiter für Speicher, die bei 90 % stoppen (**eigene Annahme**). Kleinere Hübe zählen nicht, weil der SoC des BMS über dessen eigenes Kapazitätsmodell berechnet wird – die Schätzung würde es nur nachrechnen.
- Anzeige mit `share_of_data_sheet_percent` gegen die eingetragene Kapazität. Die Schätzung ersetzt die eingetragene Kapazität nie.

### Zähler

- **Tageszähler** (Energie heute) sind keine Lebenszeitzähler: Ohne Kennzeichnung bucht der Zählerbaustein nach dem ersten Tag nichts mehr (Rücksprung unter 1 kWh gilt als DIP) oder verliert jede Nacht die erste Stunde. Erkennung (`counter.looks_like_day_counter`, gleich in Wärmewacht): in den letzten 4 Tagen zwei Rückfälle auf unter die Hälfte (ab 0,1 kWh) an verschiedenen lokalen Tagen zur selben lokalen Stunde ± 1 h (Umstellungstage). Neustarts eines Geräts, das bei 0 beginnt, und hängende Ausreißer fallen zu beliebigen Uhrzeiten und zählen nicht (bis 0.1.1 zählte jeder Rückfall; Review 30.10.). Die Einrichtung warnt (`day_counter`), ein zweites Absenden mit unveränderter Auswahl übernimmt die Zähler; beim Neu konfigurieren werden nur geänderte Zähler geprüft; ein Fehler der Statistikabfrage überspringt die Prüfung (geloggt). Im Betrieb meldet der Reparaturhinweis `counter_resets` dieselbe Regel auf den gelesenen Stundenständen (bis 0.1.1: 3 Neustarts in 7 Tagen, unabhängig von der Uhrzeit; kleine Tageszähler unter 1 kWh fielen dabei als DIP durch). Schwellen **eigene Annahme**.
- **Lebenszeit-Wert** (Vollzyklen gesamt, Garantie): erster Zählerstand der Statistik plus gebuchte Zuwächse, nie der rohe letzte Stand.

- Lebenszeitzähler vor Tageszählern. Rücksprünge: Huawei meldet die Summen als `total` ohne `last_reset` (HA bucht Rücksprünge als negative Änderung), Ausreißer bis in den MWh-Bereich bei Huawei (#307, #582) und solarman (#581, #1022, #986). HA bucht bei `total_increasing` einen Ausreißer auf 0 und zurück als vollen Zuwachs.
- Deshalb liest Speicherwacht den **Zählerstand** je Stunde (`state` der Statistik) und lässt den Zählerbaustein aus Wärmewacht darüberlaufen (`hours.py`): kleine Rücksprünge halten, Reset = neue Basis, Sprung über 2 C × Stunden × 1,5 + 1 kWh verwerfen (2 C: **eigene Annahme**, Heim- und Balkonspeicher laden höchstens mit etwa 1 C).

### Teillast (für später)

- Bei 100 W liegt der Entladewirkungsgrad je nach Gerät bei 54–86 %, Fronius GEN24 12.0 SC 75,9 % (SSI25 S. 33); 72 % der nächtlichen Leistungsflüsse liegen unter 300 W (SSI26 S. 21–22). Ein schwaches System kommt bei Ø 100 W unter 50 % AC→AC (SSI26 S. 42). Grundlage für „Verluste nach Leistungsklassen“.

### Feldwerte zur Einordnung (nicht im MVP angezeigt)

- Batteriewirkungsgrad (DC) im Labor: Fronius GEN24 + BYD HVS 96,4–96,9 % (SSI25 S. 25), Spanne 2026 87,9–97,1 %, Mittel 95,0 % (SSI26 S. 17).
- Balkonspeicher AC→AC: Zendure SolarFlow 800 Plus 85,0 % bei 800 W, 86,1 % bei 200 W (heise, 29.07.2026). Die Forenangabe „64–80 %“ ist **nicht belegt** (Recherche 30.10.).

## 4. Datenquellen – verifizierte Eigenheiten

Erkennung immer über die Entitäten-Registry (Plattform + `unique_id`), nie über Entity-IDs. Fixtures: `tests/fixtures/` mit Herkunft in `_index.json`.

### Fronius (Core `fronius`, Modbus TCP)

- Modbus seit [#179995](https://github.com/home-assistant/core/pull/179995) (25.08.2026), also ab HA 2026.9. Ohne Modbus nur SoC und Leistung → keine Vorlage, eigene Zuordnung.
- Zähler am Wechselrichter: `<id>-modbus-storage_energy_charged_total` / `…_discharged_total`, Wh, `total_increasing`, aus dem MPPT-Modell (`mppt.storage_charge_energy_total`), also am Batterieeingang (DC). „MPPT 3/4 Energie“ wiederholt dieselben Werte und wird nicht genutzt.
- Akku (eigenes Gerät): `<Seriennummer mit Leerzeichen aufgefüllt>-state_of_charge` (%, `measurement`), `-capacity_designed` und `-capacity_maximum` (Wh, ohne `state_class`, beide = Nennwert, kein SoH).
- Gruppierung je Config-Entry: Ein GEN24 hat einen Batterieeingang.
- Leistung `solar_net_<id>-power_flow-power_battery`: negativ = Laden. Binärsensor `…-battery_standby`.
- Geprüft an Tag 2026.10.4 und `dev` (30.10.): Auf `dev` stellt `_async_fix_modbus_sensor_unique_ids` das Format `<id>-modbus-<key>` sicher.

### Huawei Solar (HACS `huawei_solar`, beta)

- wlcrs/huawei_solar 2.1.5 (`9738e50`), huawei-solar-lib 3.0.7. unique_id `<Wechselrichter-Seriennummer>_<Registerschlüssel>`.
- Summen über alle Stapel: `storage_total_charge` / `storage_total_discharge` (kWh, 0,01, **`total` ohne `last_reset`**), SoC `storage_state_of_capacity`, Nennkapazität `storage_rated_capacity` (Wh, standardmäßig deaktiviert). Stapel- und Modulzähler sind deaktiviert und werden nicht genutzt. Leistung positiv = Laden. Kein SoH, keine Zyklen. DC-seitig wahrscheinlich, im Code nicht belegt.

### solarman (HACS, beta)

- davidrapan/ha-solarman (`ac1d88b`, gleiche IDs in v25.08.16, die meisten Installationen). unique_id `<Config-Entry-ID klein>_<slugify(englischer Profilname)>_<plattform>`, unabhängig von der Sprache.
- Deye-Hybrid (1P/3P): `total_battery_charge_sensor`, `total_battery_discharge_sensor` (kWh, 0,1), SoC `battery_sensor`. Leistung negativ = Laden. „Battery Capacity“ ist eine Schätzung der Integration, „Battery SOH“ (3P) eine lineare Abschreibung – beides nicht genutzt. Die archivierte Variante StephanJoubert (gleiche Domain, ~3.170 Installationen) hat andere IDs und wird nicht unterstützt.

### Anker SOLIX (beta)

- **`anker_solix`** (thomluther/ha-anker-solix 3.9.1, `d510255`, Cloud): unique_id `<Seriennummer klein>_<key>`. Lebenszeitzähler `charged_energy` / `discharged_energy` **nur über MQTT** (Eigentümer-Konto), und neue Einträge schließen die Energie-Kategorie aus – dann gibt es die Zähler gar nicht. Die Einrichtung zeigt dafür einen Hinweis (`counter_hint`). SoC `state_of_charge` (gesamt mit Erweiterungsakkus), Kapazität `number.…_battery_capacity` (Wh, Nennwert × SoH). Ob DC oder AC gezählt wird, ist nicht dokumentiert.
- **`anker_solix_official`** (v1.5.0, `3ecc42b`, lokal, nur Solarbank 4 E5000 Pro, Max, XE): unique_id `<Config-Entry-ID>_<key>`. `cumulative_charge_energy` / `cumulative_discharge_energy` (0,1 kWh), `battery_soc`, `rated_energy` (fälschlich `total_increasing`, #151).

### GoodWe (Core `goodwe`, beta)

- Core 2026.10.4 (`357cae5`), Bibliothek goodwe 0.4.10 (`66dfcdd`); die HACS-Variante mletenay/home-assistant-goodwe-inverter hat dieselbe Domain und dieselben IDs. unique_id `goodwe-<Schlüssel>-<Seriennummer>`, ein Gerät je Config-Entry.
- `e_bat_charge_total` / `e_bat_discharge_total` (0,1 kWh, `total_increasing`) nur in der ET-Klasse (ET/EH/BT/BH und die Plattformen 205/745/753). ES/EM/BP (Plattform 105) haben nur den SoC `battery_soc` → Hinweis in der Einrichtung (`counter_hint`). Die Tageszähler `e_bat_*_day` sind ebenfalls `total_increasing` und werden nicht genutzt.
- Gemessen am Batterieanschluss des Wechselrichters (DC; GoodWe-Support in core#168158). Kein Kapazitätssensor. Ein gelesener Wert 0 wird durch den letzten ersetzt (`coordinator.py` Z. 83). Nach Firmware 1230 zählte ein GW10K-ET nur die halbe Ladung (core#138278); bei zwei Akkus unklar, ob die Zähler summieren (core#146383).

### Victron GX (Core `victron_gx`, beta)

- Core seit 2026.5, Bibliothek victron-mqtt 2026.9.5 (`37fbc4d`), MQTT direkt zum GX. unique_id `<VRM-Portal-ID>_battery_<Instanz>_<Schlüssel>`; ein Speicher je Batteriedienst (BMV, SmartShunt, Lynx), ein Config-Entry je Anlage → Gruppierung nach Präfix.
- `battery_charged_energy` / `battery_discharged_energy` (`History/ChargedEnergy`, kWh, `total_increasing`, DC am Shunt), SoC `battery_soc`. Kapazität nur in Ah → keine Kapazität aus der Vorlage.
- Die Systemwerte `system_dc_battery_charge_energy` usw. sind Riemann-Summen der Bibliothek und beginnen bei jedem HA-Start bei 0 (core#172369) → nicht genutzt, die Regex trifft sie nicht. CAN-BMS-Akkus haben vermutlich keine Zähler (nicht im Code belegt) → `counter_hint`. „History löschen“ am BMV setzt die Zähler auf 0.

### SolarEdge (HACS `solaredge_modbus_multi`, beta)

- WillCodeForCats/solaredge-modbus-multi 4.0.10 (`70aa159`). Batterie-Entitäten nur mit der Option „Auto-Detect Batteries“ (standardmäßig aus); ohne sie fehlt auch der SoC, ein Hinweis in der Einrichtung greift also nicht → README. unique_id `<Modell>_<Seriennummer>_B<1–3>_<Schlüssel>`, ein Speicher je Batterie.
- `energy_import` (Laden) / `energy_export` (Entladen), Wh, `total_increasing`; SoC `battery_soe`; Kapazität `max_energy` (aktuelle Maximalenergie, nicht der Nennwert; Zusammenhang mit dem SoH nicht belegt). DC oder AC nicht dokumentiert.
- **Zähler:** LG und BYD setzen sie auf 0, die SolarEdge Home Battery 48V springt und läuft rückwärts (Wiki „Known Issues“, #273, #606, #1156). Ohne die Option „Allow Battery Energy to Reset“ (Standard) hält die Integration den alten Wert; der Zähler friert dann ein, bis der Rohwert ihn wieder erreicht – Speicherwacht meldet das über `counter_soc_mismatch`. PR #1129 (geplant 4.1.0) summiert künftig selbst, gleiche IDs.
- Die Core-Integration `solaredge_modbus` (seit 2026.10) ist eine eigene Plattform und nicht untersucht.

### SolaX (HACS `solax_modbus`, beta)

- wills106/homeassistant-solax-modbus 2026.10.02 (`b6880b6`). unique_id `<Hubname>_<Schlüssel>` ohne Seriennummer (Hubname aus der Einrichtung, Standard „SolaX“, darf Leerzeichen enthalten), ein Config-Entry je Wechselrichter → Gruppierung je Entry. Das virtuelle Gerät „Energy Dashboard“ hat nur Tageswerte und wird ausgeschlossen.
- `battery_input_energy_total` / `battery_output_energy_total` (kWh, 0,1, **`total` ohne `last_reset`**) sind standardmäßig deaktiviert und werden dann nicht einmal abgefragt → `counter_hint`, nach dem Einschalten neu laden. SoC heißt `battery_capacity` (%), bei Sofar `battery_capacity_total`. Kapazität `battery_system_installed_capacity` (Wh, Nennwert, GEN4–6 mit Protokoll ≥ 1.00, deaktiviert).
- Bei instabiler Verbindung springen die Summen kurz auf 0 und zurück (#2115) – mit `total` als negative und gleich große positive Änderung, das fängt der Zählerbaustein ab. Andere Plugins derselben Domain (AlphaESS, Solis, Growatt …) haben andere Schlüssel; bei AlphaESS ist `battery_capacity` kWh, deshalb nimmt die Vorlage nur SolaX- und Sofar-Schlüssel. DC oder AC nicht dokumentiert.

### Sungrow (Core `modbus` mit dem YAML-Paket, beta)

- mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant (`310635c`, Stand 2026-06-19, ohne Tags), die verbreitetste Variante; Installationen nicht zählbar (Plattform `modbus`). Die unique_id ist der YAML-Wert selbst, kein Config-Entry; bei mehreren Wechselrichtern `_inv_<n>` angehängt → Speicher-ID leer bzw. `_inv_<n>`.
- `sg_total_battery_charge` / `sg_total_battery_discharge` (kWh, 0,1, **`total` ohne `last_reset`**, alle 600 s gelesen), SoC `sg_battery_level`, Kapazität `uid_battery_capacity_high_precision` (kWh; 2025-11/12 umbenannt). Leistung negativ = Laden. DC oder AC unbekannt.
- **SoC:** Laut Kommentar im Paket läuft „Battery level“ zwischen min_soc und max_soc von 0 bis 100 %, nicht absolut (nicht geprüft). Die SoC-Korrektur verschiebt sich um den Anteil des Fensters, die Kapazitätsschätzung zeigt das Fenster → Hinweis im Zuordnungsschritt (`note`), Kapazität des Fensters eintragen, wenn es deutlich enger ist.
- Der Nachfolger `sungrow_modbus` (Alpha) behält die entity_ids, wechselt aber Plattform und unique_ids (`<Seriennummer>_<key>`) → dann eine zweite Vorlage. KRoperUK/sungrow-hass (`sungrow`, 745 Installationen) ohne Vorlage: Welche Cloud-Punktcodes ein Heimspeicher füllt, ist ohne Diagnose-Dump offen.

### Sigenergy (HACS `sigen`, beta)

- TypQxQ/Sigenergy-Local-Modbus 1.2.7.5 (`b66e304`; 1.3.0 an diesen Stellen gleich). unique_id `<Config-Entry-ID>_<Gerätename klein>_<key>`, ein Config-Entry je Anlage.
- **Nur die Anlagenzähler** (Entscheidung 2026-10-30): `plant_accumulated_battery_charge_energy` / `…_discharge_energy` (0,01 kWh, **`total` ohne `last_reset`**, ab Protokoll v2.7, Anzeige in MWh), SoC `plant_ess_soc`, Kapazität `plant_ess_rated_energy_capacity`. Die Wechselrichter haben eigene Zähler desselben Akkus; sie anzubieten hieße, denselben Akku zweimal zur Wahl zu stellen. Ältere Firmware hat nur den Anlagen-SoC → Hinweis (`counter_hint`), dann eigene Zuordnung mit den Wechselrichterzählern.
- Leistung positiv = Laden. Kurze Nullwerte nach einer Wiederverbindung sind bei Tageszählern belegt (#313), der Null-Schutz der Integration deckt die Speicherzähler nicht ab. Bis 1.1.0 (2025-08) war der Anlagenzähler ein berechneter Sensor mit demselben Schlüssel.

### Zendure (HACS `zendure_ha`, beta)

- Zendure/Zendure-HA 1.4.4 (`8d59bac`). unique_id `<Gerätename aus der App, snake_case>_<key>`, eine Instanz → Gruppierung nach Präfix. Umbenennen in der App zieht unique_id und entity_id um (`migration.py`) → Speicherwacht meldet `missing_entity`, Neu konfigurieren hilft. Zwei Geräte mit gleichem Namen kollidieren (#1518).
- `aggr_charge` / `aggr_discharge` (kWh, `total_increasing`) **rechnet die Integration in HA** als Linkssumme aus der Pack-Leistung hoch und stellt sie beim Start wieder her; das Gerät liefert keinen Zählerstand. Speicherwacht prüft hier also die Stimmigkeit der Integration, nicht ein Gerätemaß → Hinweis im Zuordnungsschritt (`note`). SoC `electric_level`, Kapazität `total_kwh` (Nennwerte der Packs aus der Seriennummer). Erweiterungsakkus und „Zendure Manager“ haben keine Zähler.
- #1599: `aggr_charge` wuchs auf 3e75 (vermutlich Restore in der Anzeigeeinheit Wh) – der Zählerbaustein verwirft solche Sprünge (`MAX_C_RATE`). Bei einem Verbindungsabbruch bucht die Integration „letzte Leistung × Lücke“ nach (nur aus dem Code).

### Marstek Venus E (HACS `marstek_modbus`, beta)

- Zwei Integrationen mit derselben Domain und unique_id `<Config-Entry-ID>_<key>`: ViperRNMC/marstek_venus_modbus 2026.10.1 (`cb5a241`) und sphings79/marstek-modbus-suite 3.1.3 (`60c023d`). Eine Vorlage für beide.
- `total_charging_energy` / `total_discharging_energy` (Register 33000/33002, 0,01 kWh, `total_increasing`) zählen an der AC-Seite → `Boundary.SYSTEM`. SoC `battery_soc` (E v3: vom Wechselrichter hochgerechnet, bei 0/100 % auf den BMS-Wert gesetzt). Kapazität `battery_rated_capacity` (Suite ab 3.1.0-beta.3) oder `battery_total_energy` (Viper, Suite E v1/v2) → `capacity` ist ein Tupel.
- **Venus A/D ausgeschlossen:** Dort läuft PV→Haus durch den Entladezähler (Viper #207). Erkennbar an `mppt1_power`, auch deaktiviert in der Registry → `exclude_keys`, die Prüfung sieht auch deaktivierte Einträge.
- Firmware: EMS 144/147 Zähler auf 0 oder still (#170, #192), Firmware-Update oder Werksreset setzt sie zurück (#226), EMS 148 einzelne Werte als 1/10 (#216). Beide Integrationen verwerfen Rückgänge nur bis zum nächsten HA-Neustart.
- Ohne Vorlage: B2500 (nur Tageswerte, MQTT), `marstek_local_api` (keine Akkuzähler); HA-Core hat keine Marstek-Integration.

### Weitere Hersteller (Recherche 29.10.2026, noch ohne Fixture)

Grundlage für die Reihenfolge weiterer Vorlagen; vor dem Bau jeweils am Quellcode und mit Fixture prüfen.

- **Heimspeicher mit Lebenszeitzählern** (geschätzt 55–65 % der verbauten Kapazität): BYD über den Wechselrichter, Sungrow, Huawei, Fox, SMA, Kostal, SolarEdge, GoodWe, Victron, Sigenergy, RCT, SolaX, Deye/solarman. Rücksprünge: `total` ohne `last_reset` bei Huawei (bestätigt, oben), Sungrow und Fox (ungeprüft); SolarEdge-Zähler laufen teils rückwärts (ungeprüft).
- **Nur Leistung oder Periodenwerte:** E3/DC, sonnen, SENEC (V4 nur Cloud) → Integral-Helfer.
- **SoH vom BMS:** SolarEdge, Victron, sonnen, RCT, GoodWe, Sungrow, Sigenergy, SolaX, BYD HVS; **Zyklen:** Kostal, sonnen, Victron, Fox, RCT, Varta.
- **Balkonspeicher:** Lebenszeitzähler bei Indevolt (Core), Marstek Modbus, Solakon, Anker official, Jackery, Anker SB1–3 (MQTT), EcoFlow STREAM. Nur Tageswerte: Hoymiles MS-A2/HiBattery, Marstek B2500, EcoFlow PowerStream. Nur in HA integriert: Zendure, EcoFlow Delta. Ohne Akkuzähler (nur über einen AC-Zähler, Bilanzgrenze „System“): Growatt NOAH, Bluetti, Sunlit, Marstek Local API.
- **Marktanteile 2025** nach Kapazität (P3/ISEA, pv magazine 26.06.2026): BYD 16,5 %, Sungrow 9,0 %, Huawei 7,8 %, Anker 6,9 %, Fox 5,4 %, E3/DC 4,3 %, sonnen 3,3 %.
- **Installationen laut HA-Analytics** (29.10.2026): fronius 10.403, solarman 10.503 (davon ~7.200 davidrapan, ~3.170 StephanJoubert), huawei_solar 6.520, anker_solix 6.368, zendure_ha 4.318, ecoflow_cloud 4.299, goodwe 3.726, victron_gx 3.456, solaredge_modbus_multi 3.183, solax_modbus 3.031, sigen 2.736; anker_solix_official 1.159 (30.10.).
- **Nachfrage:** vor allem Balkonspeicher; Amortisation umstritten (~4 Jahre laut EUPD/Anker gegen > 10 Jahre laut HTW, nicht primär geprüft).

## 5. Home Assistant – technischer Stand

- Mindestversion **2026.4** (Entitätsauswahl mit Filter nach Einheit), wie Wärmewacht; CI-Job `compat`.
- Energie-Einstellungen: Speicher als `type: battery` mit `stat_energy_to` (Laden), `stat_energy_from` (Entladen), `stat_soc` (seit 2026.6), `capacity` in kWh (seit 2026.8) – `energy/data.py` an Tag 2026.10.4. Die eigene Zuordnung belegt sich daraus vor (nur lesen).
- Binärsensoren haben keine Langzeitstatistik: Ein Standby-Signal bräuchte Listener und Speicherdatei (zurückgestellt, Entscheidung 2026-10-30).

## 6. Entscheidungen

Vom Inhaber am 2026-10-30:

- Name „Speicherwacht“, Domain `speicherwacht`, Repo `github.com/speicherwacht/integration` (Organisation legt der Inhaber an), `codeowners` `@n42net`, MIT.
- Heim- und Balkonspeicher gleich, Kern herstellerneutral; erste Vorlage Fronius, dazu Huawei Solar, solarman, Anker SOLIX als Beta aus dem Quellcode; mit 0.1.0b3 GoodWe, Victron GX, SolarEdge, SolaX, Sungrow (YAML), Sigenergy (nur Anlage), Zendure (mit Hinweis auf die gerechneten Zähler) und Marstek Venus E (die nächsten nach HA-Analytics).
- **Nur Langzeitstatistik**: stündlich neu rechnen, keine eigene Speicherdatei, keine Schreiblast; Live und Rückblick rechnen gleich. Reparaturhinweise schauen trotzdem auf die aktuellen Zustände.
- Zähler Pflicht; wer nur Leistung hat, legt einen Helfer „Integral“ an (README).
- Bilanzgrenze je Eintrag wählbar (Akku/System).
- Kapazität als Zahl in der Einrichtung, Vorlage füllt vor; die Schätzung ersetzt sie nie.
- Zeiträume Monat, Jahr (Kalenderjahr), gesamt; Tag vorhanden, aber deaktiviert.
- Ruhetage erkennen und getrennt ausweisen; Standby-Signal später.
- SoC-Korrektur behalten, als eigene Näherung kennzeichnen.
- Gesundheits-Check im MVP nur als Reparaturhinweise für Datenfehler.
- Wirtschaftlichkeit später.
- Kein `country` in `hacs.json` (Speicher sind nicht deutschlandspezifisch); Texte Deutsch und Englisch.
- Marke (Farbe, Motiv) später.
- HACS-Antrag erst, wenn weniger als drei eigene Anträge offen sind (oberste `NOTES.md`); bis dahin benutzerdefiniertes Repository.

## 7. Architektur

| Datei | Inhalt (ohne HA-Importe, lokal getestet) |
| --- | --- |
| `model.py` | `Signal`, `Boundary`, `Hour` |
| `counter.py` | Zählerbaustein, unverändert aus Wärmewacht (ein Fehler dort kann auch hier stecken) |
| `hours.py` | Stundenzeilen der Statistik → bereinigte Stunden; Zählerstand statt `change`; Lücken; abgewiesene Werte |
| `days.py` | lokale Tage (23/25 h), SoC an Stundengrenzen, Perioden |
| `analysis.py` | Wirkungsgrad, Ruhetage, Ruheverlust, Kapazität, Vollzyklen |
| `profiles.py` | Vorlagen als Daten, Gruppierung nach Präfix oder Config-Entry |
| `health.py` | Gesundheits-Check (`docs/GESUNDHEITSCHECK.md`) |
| `rename.py` | umbenannte Quell-Entität in `entities` und `unique_id` ersetzen |

HA-Schicht: `runtime.py` (Statistik lesen: beim Start alles seit 2000, dann stündlich um :12 ab drei Stunden vor der letzten Zeile; Reparaturhinweise alle 5 min nach 10 min Laufzeit), `config_flow.py` (erkannte Speicher, eigene Zuordnung mit Vorbelegung aus den Energie-Einstellungen, Neu konfigurieren), `sensor.py`, `binary_sensor.py` (Problem-Sensoren), `diagnostics.py`. Texte und Icons erzeugt `tools/make_strings.py` (danach `ruff format`).

- **Schreiblast:** keine Speicherdatei. Sensoren ändern sich höchstens stündlich; Werte gerundet (Prozent 0,1, Zyklen 0,1, kWh 0,01, W 1), die Liste `samples_kwh` nicht aufgezeichnet.
- **Umbenannte Quellen (seit 0.1.1, gleiche Lösung wie Wärmewacht):** Ein Listener auf `entity_registry_updated` für alle Einträge (in `async_setup`), nur `action == "update"` mit `old_entity_id`. HAs eigene Helfer hören je Eintrag (`helpers/helper_integration.py`, `async_handle_source_entity_changes`; bei mehreren Quellen wie `mold_indicator` ein Listener je Quelle); ein gemeinsamer sieht auch Einträge, die gerade neu laden oder nicht starten konnten, und eine ID, die vor dem Neuladen noch einmal umbenannt wird. `entry.data` und die `unique_id` (Ladezähler; nicht, wenn ein anderer Eintrag sie schon trägt) ändern sich sofort; neu geladen wird einmal, 3 s nach der letzten Umbenennung (`RENAME_RELOAD_DELAY`). Bis dahin überspringt der Update-Listener. Wäre die neue ID schon eine andere Quelle des Eintrags, bleibt alles, wie es war (Warnung im Log, Reparaturhinweis `missing_entity`). Gelöschte Entitäten: nichts umschreiben, der Reparaturhinweis bleibt zuständig. Anders als Wärmewacht ist im laufenden Betrieb nichts nachzuziehen (keine Speicherdatei). Neu konfigurieren mit einem anderen Ladezähler setzt die `unique_id` mit.
- **Speicher:** Die Stundenstände aller drei Quellen bleiben im Arbeitsspeicher (drei Zahlen je Stunde, ~26.000 je Jahr).

## 8. Offene Fragen

- Kalibrierladungen (BYD an Fronius: frühestens 30 Tage nach der letzten auf 100 % und nachts unter 5 %; GEN24-Intervall nicht gefunden) erzeugen SoC-Sprünge: an der Anlage des Inhabers beobachten.
- Erste Beta an der Testanlage gegen die eigenen Riemann-Helfer prüfen (Werte nur in `CLAUDE.local.md`).
- Normtexte (IEC 62933-2-1, DIN VDE V 0510-200) nicht gelesen (kostenpflichtig).
- Anker: DC oder AC? An einer echten Anlage klären, dann Bilanzgrenze der Vorlage festlegen.
