# Changelog

## Unveröffentlicht

### Neu

- **Blueprint „Befund melden“.** Meldet, wenn eine Prüfung des Gesundheits-Checks auffällig wird – in der Glocke und auf Wunsch aufs Handy (oder an einen anderen Benachrichtigungsdienst), mit dem Befund in Worten, etwa „Kapazität gesunken: geschätzt 7,6 kWh, 76 % des Datenblatts (Grenze 80 %)“, auf Deutsch oder Englisch. Aufs Handy geht nur ein Wechsel von „in Ordnung“ auf „auffällig“ nach mindestens einem Tag in Ordnung, damit ein Wert an der Schwelle keine Meldung je Stunde auslöst. Import über den Knopf im README unter [Benachrichtigen](README.md#benachrichtigen).

## 0.2.1 – 2026-11-10

### Geändert

- **Karte: Monatsdiagramm auf dem Handy lesbar.** Das Diagramm wurde immer 560 Punkte breit gezeichnet und verkleinert; auf dem Handy schrumpfte die Schrift so auf etwa 6 px. Jetzt zeichnet die Karte es in ihrer eigenen Breite und neu, wenn sich die Breite ändert, etwa beim Drehen des Handys. Auf breiten Bildschirmen bleibt alles, wie es war.

## 0.2.0 – 2026-11-09

- **Neu: eigene Dashboard-Karte** (`custom:speicherwacht-card`), ohne Zusatzkarten aus HACS: *Dashboard bearbeiten → Karte hinzufügen* → „Speicherwacht“. Speicherwacht trägt die Dashboard-Ressource selbst ein. Die Karte zeigt
  - **Befund:** die drei Prüfungen des Gesundheits-Checks mit Punkt und der entscheidenden Zahl; kann eine Prüfung noch nicht urteilen, was fehlt („erst 1 von 3 Entladungen von voll bis leer in 90 Tagen“, „Vergleich mit dem Vorjahr frühestens ab Nov. 2027“). Offene Reparaturhinweise stehen darüber, ein Klick führt zu *Reparaturen*.
  - **Kennzahlen:** Wirkungsgrad im Jahr groß, Monat und gesamt daneben, geschätzte Kapazität mit Balken gegen das Datenblatt, Ruheverlust, Vollzyklen, Garantie-Durchsatz.
  - **Monate:** geladen und entladen in den letzten zwölf Monaten mit dem Wirkungsgrad je Monat, gerechnet wie die Aktion „Bericht“. Speicherwacht rechnet sie aus den Stundenwerten, die es ohnehin liest, erst wenn eine Karte fragt und höchstens einmal je Stunde – keine zusätzliche Abfrage der Statistik, nichts wird geschrieben.

  Die Karte findet ihre Entitäten selbst (unabhängig von Sprache und Entity-IDs); bei mehreren Speichern wählst du einen im Editor, mit `sections` zeigt sie nur einzelne Abschnitte. Die Demo zeigt jetzt diese Karte. Anlass: eigene Prüfung, welche Wachten eine Karte brauchen.
- Bericht für Fehlermeldung: neue Zeile `card`, wie die Karte ins Frontend kommt.

## 0.1.7 – 2026-11-08

- **Neu: Zusammenfassung oben in *Neu konfigurieren*.** Das Formular zeigt zuerst in ein paar Zeilen, was der Eintrag liest und auswertet: Vorlage oder eigene Zuordnung (mit „Zähler wie im Energie-Dashboard“ bzw. „wie in Tarifwacht …“, wenn sie dort gleich sind), Gesamtzähler und Einheit, was die Zähler messen, Ladezustand jetzt, Kapazität laut Datenblatt und geschätzt (oder was der Schätzung noch fehlt), was ausgewertet wird und seit wann Daten da sind. Darunter steht unter „Was fehlt“ nur, was eine Folge hat, etwa „Als Ladezustand ist ein Sensor von Speicherwacht selbst gewählt, er wird nicht gelesen: kein Wirkungsgrad, kein Ruheverlust, keine geschätzte Kapazität“, ein fehlender Zähler, ein Zähler, der jeden Tag neu beginnt, oder ein fehlender Garantie-Durchsatz. Die Zusammenfassung ist deutsch oder englisch nach der Sprache von Home Assistant; keine neuen Felder, nichts wird dafür aus der Statistik gelesen. Anlass: eigene Prüfung.
- **Formular aufgeräumt:** In der Einrichtung und unter *Neu konfigurieren* stehen oben nur noch die drei Entitäten und die Kapazität. „Die Zähler messen“ und „Garantie-Durchsatz“ stehen im Abschnitt „Weitere Angaben“, der eingeklappt beginnt (aufgeklappt, wenn ein Garantie-Durchsatz eingetragen ist oder die Zähler anders messen, als die Vorlage vorgibt). Speichern, ohne ihn aufzuklappen, lässt seine Werte, wie sie sind; gespeichert wird alles wie bisher, bestehende Einträge gelten unverändert. Die Beschreibung des Formulars ist kürzer (die Zustandsklassen nennen weiter die Fehlermeldungen). Anlass: eigene Prüfung.
- **Kurzer Zählerfehler kostet keine Energie mehr.** Fällt ein Zähler nach dem falschen Wert auf mindestens den Stand davor zurück (107 → 109.851,5 → 110,131 kWh), bucht Speicherwacht den echten Zuwachs (3,131 kWh) in der Stunde des Rückfalls, statt ihn zu verlieren – wenn er für die vergangene Zeit plausibel ist. Der Tag zählt damit wieder voll in den Wirkungsgrad und in die Vollzyklen; nur die Stunden des Ausreißers fehlen weiter in Ruheverlust, Kapazitätsschätzung und dem Abgleich von Zählern und Ladezustand (die Energie einer einzelnen Stunde ist nicht bekannt). Unplausibel bleiben Stunden nur noch, wenn der Zähler danach unter den alten Stand fällt (Neustart) oder nicht innerhalb eines Tages zurückkommt. Die Regel stammt aus dem Zählerbaustein von Wärmewacht. Anlass: Fund an einem Zähler in Tarifwacht.
- **Unplausible Zählerstunden aus allen Kennzahlen:** Meldet eine Quelle kurz Wh als kWh (Muster aus einem echten Zähler: 107 → 109.851,5 → 110,1 kWh je Stunde), verwarf Speicherwacht den Sprung schon bisher, buchte die beiden Stunden aber mit 0 kWh. Der Tag zählte so mit fehlender Ladung oder Entladung in den Wirkungsgrad (im Test rund ein Prozentpunkt im Monat). Jetzt ist die Energie solcher Stunden unbekannt: Wirkungsgrad lässt ihren Tag weg (neues Attribut `implausible_days`), Ruheverlust, Kapazitätsschätzung und der Abgleich von Zählern und Ladezustand die Stunden. Die Aktion „Bericht“ nennt sie unter `hours_implausible` (Anzahl und die ersten fünf Stunden), ebenso die Diagnose-Datei; der Bericht für Fehlermeldung zählt die Tage. Dasselbe gilt für den Neustart eines Gesamtzählers. Anlass: derselbe Fund in der Schwester Tarifwacht.

## 0.1.6 – 2026-11-08

- **README: Maxxisun-Einzelakkus summieren.** Die Gesamtwerte der Maxxisun-Integration für Laden und Entladen sind gerechnet (PV minus CCU) und lagen in einem geprüften Fall 15–30 % daneben. Der neue Abschnitt zeigt den genaueren Weg: Template-Sensoren mit der Summe der Lade- und Entladeleistungen der einzelnen Akkus, darauf zwei Integral-Helfer als Zähler, den Ladezustand aus der gespeicherten Energie.
- **Zähler aus Tarifwacht:** Hast du in der Schwester [Tarifwacht](https://github.com/tarifwacht/integration) unter „PV und Speicher“ Lade- und Entladezähler eingetragen, schlägt die eigene Zuordnung sie vor, wenn das Energie-Dashboard keine liefert. Ein Satz unter der Beschreibung sagt, aus welchem Eintrag sie stammen; ohne Tarifwacht-Speicher steht dort ein kurzer Tipp. Nur ein Vorschlag beim Einrichten, Speicherwacht hängt danach nicht von Tarifwacht ab. Erkannte Speicher (Vorlagen) und Neu konfigurieren bleiben, wie sie sind.
- **Bericht für Fehlermeldung lesbarer:** Einstellungen ohne Python-Schreibweise – `yes`/`no` statt `True`/`False`, `none` statt `None`, Listen ohne Klammern, Zeitpunkte als `2026-11-07 12:39 UTC`. Auch „beta template“ und „day values“.

## 0.1.5 – 2026-11-07

- **Neu: Schaltfläche „Bericht für Fehlermeldung“** am Gerät (unter *Diagnose*). Sie zeigt einen kurzen Bericht als Benachrichtigung zum Kopieren in ein Issue: Versionen, die Zuordnung nach Rolle (Integration, Einheit, Klassen, Zustand von Lade-, Entladezähler und Ladezustand), Kapazität, Bilanzgrenze und Garantie-Durchsatz, Vorlage, Stunden der Statistik und verworfene Zählerwerte, unbekannte Sensoren mit Grund und offene Reparaturhinweise – ohne Entity-IDs, Namen und Bereiche. Viele wollen die Diagnose-Datei nicht öffentlich teilen, weil Home Assistant ihr unter anderem die Liste aller installierten Integrationen voranstellt (so in allen Wachten). Die README erklärt jetzt unter „Fehler melden“, was in der Diagnose-Datei steht und welche Teile man vor dem Teilen löschen darf.

## 0.1.4 – 2026-11-05

- **Demo zum Ausprobieren ohne Installation:** [speicherwacht.github.io/integration](https://speicherwacht.github.io/integration/) zeigt Dashboard, Geräteseite, Gesundheits-Check und die Aktion „Bericht“ für vier Speicher (gesund, gealtert, Balkonspeicher, frisch eingerichtet). Alle Werte sind erfunden und so gekennzeichnet; gerechnet werden sie vom Code der Integration.
- **Eigene Sensoren sind als Quelle gesperrt:** Einrichtung und Neu konfigurieren lehnen Entitäten von Speicherwacht selbst ab. Ein Wirkungsgrad-Sensor (in %, Zustandsklasse measurement) ging bisher als Ladezustand durch; der Eintrag hätte dann seine eigenen Ergebnisse gelesen. Anlass war eine Rückmeldung aus der Schwester Wärmewacht, wo genau das passiert ist. Bestehende Einträge mit einem eigenen Sensor als Ladezustand lesen ihn nicht mehr: Wirkungsgrad, Ruheverlust und geschätzte Kapazität sind dann unbekannt (Grund `no_soc` bzw. zu wenige Stunden), und ein Reparaturhinweis bittet, unter „Neu konfigurieren“ den Ladezustand des Speichers zu wählen. Danach rechnet Speicherwacht alles neu aus der Langzeitstatistik; was bisher aufgezeichnet wurde, bleibt im Verlauf. Ein eigener Sensor als Zähler wird weiter gelesen, weil die Zähler Pflicht sind, und ebenfalls gemeldet (praktisch kaum möglich, kein eigener Sensor ist ein Energiezähler).
- Kategorien im Manifest für die neue Integrationsübersicht von Home Assistant 2026.11.
- README: Hinweis „Neu“ auf die Angabe zu den Vorlagen gekürzt.
- Intern: `tools/make_demo.py` erzeugt die Daten der Demo, der Workflow „Demo“ veröffentlicht sie über GitHub Pages.

## 0.1.3 – 2026-11-03

- **Aktion „Bericht“** (`speicherwacht.report`): Energie, Wirkungsgrad mit Korrektur über den Ladezustand, Vollzyklen, Ruheverlust und geschätzte Kapazität für einen beliebigen Zeitraum, je Monat aufgeschlüsselt, auch vor der Einrichtung. Ohne Angaben: 1. Januar bis jetzt, also die Werte der Jahressensoren. Gerechnet wird wie bei den Sensoren, über ganze Tage.
- **Neue Vorlage (Beta, aus dem Quellcode):** SolarEdge über die Core-Integration `solaredge_modbus` (ab HA 2026.10), ein Speicher je Batterie. Die bisherige Vorlage für die HACS-Integration `solaredge_modbus_multi` bleibt.

## 0.1.2 – 2026-10-30

- **Ruheverlust nie mehr negativ:** Steigt der Ladezustand in Ruhephasen (Laden am Ladezähler vorbei, etwa PV direkt in den Akku bei DC-gekoppelten Balkonspeichern, oder Drift des Ladezustands), zeigte der Ruheverlust einen negativen Wert (gemeldet: −3 W). Jetzt ist er dann unbekannt mit dem Grund `soc_rose_at_rest`; der errechnete Wert steht im Attribut `raw_watts`. Ein Anstieg bis zu einer Stufe des Ladezustands (1 %) über alle Ruhestunden gilt als Rundung und zeigt 0 W. „Ruheverlust hoch“ bleibt dann unbekannt (Rückmeldung im simon42-Forum).
- **Tageszähler-Erkennung genauer:** Als Tageszähler („Energie heute“) gilt ein Zähler jetzt nur, wenn er an verschiedenen Tagen zur selben Uhrzeit zurückfällt. Bisher zählte jeder Rückfall, sodass ein Gesamtzähler, der nach einem Neustart des Geräts bei 0 beginnt, nach zwei Neustarts abgelehnt wurde. Die Einrichtung warnt nur noch; wer sicher einen Gesamtzähler gewählt hat, sendet unverändert noch einmal ab. Beim Neu konfigurieren werden nur neu gewählte Zähler geprüft, und ein Fehler beim Lesen der Statistik hält die Einrichtung nicht mehr auf. Der Reparaturhinweis „Zähler beginnt jeden Tag neu“ folgt derselben Regel und erkennt jetzt auch kleine Tageszähler unter 1 kWh.
- **Fehlerhilfe:** Wirkungsgrad über 100 % kann auch heißen, dass Energie am Ladezähler vorbei in den Akku fließt.
- **Einrichtung klarer:** Die Hilfetexte zu „Energie geladen“ und „Energie entladen“ sagen jetzt, was nicht gemeint ist: nicht die PV-Erzeugung und nicht die Abgabe der ganzen Anlage ins Haus (Rückmeldung im simon42-Forum).

## 0.1.1 – 2026-10-30

Erste finale Version: Stand von 0.1.0b3 und zwei Korrekturen.

- **Umbenannte Quellen werden nachgezogen:** Ändert sich die Entity-ID eines Zählers oder des Ladezustands (Entitäts-Einstellungen, „Entity-IDs neu erstellen“ am Gerät), übernimmt Speicherwacht die neue ID selbst und lädt den Eintrag einmal neu, auch wenn mehrere Quellen kurz nacheinander umbenannt werden. Bisher fehlten die Quellen danach („Entität fehlt“), bis man neu konfiguriert hat. Eine gelöschte Entität bleibt ein Fall für „Neu konfigurieren“.
- **Neu konfigurieren mit einem anderen Ladezähler:** Der Eintrag gilt jetzt als der Speicher dieses Zählers. Bisher blieb er beim alten Zähler; ein neuer Eintrag mit dem alten Zähler wurde dann als „schon eingerichtet“ abgelehnt.
- README mit Bildern von Gerät und Dashboard.

Was Speicherwacht seit den Betas kann: Wirkungsgrad je Monat, Jahr und gesamt mit Korrektur über den Ladezustand, Ruhetage getrennt; Vollzyklen und Garantie-Durchsatz; Ruheverlust; geschätzte Kapazität; Gesundheits-Check mit drei Problem-Sensoren; Vorlagen für Fronius (erprobt) und 13 weitere Quellen (Beta); alles aus der Langzeitstatistik, auch rückwirkend.

## 0.1.0b3 – 2026-10-30

- **Gesundheits-Check:** drei Problem-Sensoren – „Wirkungsgrad unter Vorjahr“ (letzte 30 Tage mindestens 3 Punkte unter denselben Tagen des Vorjahres), „Kapazität gesunken“ (unter 80 % des Datenblatts oder 10 Punkte unter dem Vorjahr), „Ruheverlust hoch“ (über 64 W oder deutlich über dem Vorjahr) – und der Reparaturhinweis „Zähler und Ladezustand passen nicht zusammen“. Regeln und Quellen in `docs/GESUNDHEITSCHECK.md`.
- **Neue Vorlagen (Beta, aus dem Quellcode):** GoodWe ET/EH/BT/BH (Core), Victron GX mit Batteriewächter (Core), SolarEdge StorEdge (`solaredge_modbus_multi`, ein Speicher je Batterie), SolaX/Sofar (`solax_modbus`), Sungrow SH (Modbus-YAML von mkaiser), Sigenergy (`sigen`, Zähler der Anlage), Zendure (`zendure_ha`) und Marstek Venus E (`marstek_modbus`, beide Integrationen; Venus A/D werden nicht erkannt). Bei GoodWe ES/EM/BP, Victron ohne Batteriewächter, SolaX mit ausgeschalteten Zählern und Sigenergy mit älterer Firmware zeigt die Einrichtung einen Hinweis; bei Sungrow (Ladezustand im Fenster) und Zendure (Zähler von der Integration gerechnet) erklärt der Zuordnungsschritt die Grenze.

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
