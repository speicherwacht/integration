# Speicherwacht – Projektkontext für Claude

Home-Assistant-Custom-Integration (HACS), Domain `speicherwacht`, Anzeigename „Speicherwacht“. Wertet aus vorhandenen Entitäten aus, wie gut ein Batteriespeicher (Heim- oder Balkonspeicher) arbeitet: Wirkungsgrad je Monat/Jahr/gesamt mit Korrektur über den Ladezustand, Ruhetage, Vollzyklen und Garantie-Durchsatz, Ruheverlust, geschätzte Kapazität. Alles aus der Langzeitstatistik von Ladezähler, Entladezähler und Ladezustand. Vorlagen für Fronius (erprobt) sowie als Beta für Huawei Solar, solarman und Anker SOLIX (Cloud und offiziell). **Nur lesen, nie steuern.** Schwesterprojekt von Wärmewacht (`../waermewacht`, nächstes Vorbild), Streckenwacht, Eilwacht, Einspeisewacht und Tarifwacht – deren Muster übernehmen, wo es passt.

Stand: Projektstart 2026-10-30, noch kein Release. Arbeitsstand in `NOTES.md`.

## Dokumentation

- **`docs/ENTWICKLUNG.md`** – Umfang, Abgrenzung, Fachregeln mit Quellen, verifizierte Eigenheiten der Datenquellen, Entscheidungen, Architektur, offene Fragen. Vor größeren Arbeiten lesen.
- **`NOTES.md`** (lokal, in `.git/info/exclude`) – Arbeitsstand, offene Punkte, Beobachtungen. Nach jeder Sitzung fortschreiben.
- **`CLAUDE.local.md`** (lokal, in `.git/info/exclude`) – Rechner und Testanlage des Inhabers (echte Entitäten, Werte, Eigenbau zum Vergleich).
- **`CHANGELOG.md`** – Versionsgeschichte und „Unveröffentlicht“.
- **`docs/BRAND.md`** – Farben, Schrift, Bilddateien, Regenerierung (`tools/brand/`). Brand-Bilder nicht verändern oder neu erzeugen, außer auf ausdrücklichen Wunsch.

## Verbindliche Entscheidungen (2026-10-30)

- **Eigene Integration**, herstellerneutral. Konkurrenz im README fair nennen (`docs/ENTWICKLUNG.md` §2), besonders den Marstek Capacity Monitor.
- `integration_type: service`, `iot_class: calculated`, keine `requirements`, **keine Netzabfragen**. Eigenes Gerät je Speicher, ein Config-Entry je Speicher.
- **Nur Langzeitstatistik:** stündlich aus den Stundenwerten rechnen, keine eigene Speicherdatei, keine Zustands-Listener für die Rechnung. Live und Rückblick rechnen gleich. Reparaturhinweise schauen auf die aktuellen Zustände.
- **Herstellerneutraler Kern ohne HA-Importe.** Quellen über **Vorlagen als Daten** (`profiles.py`), Erkennung über die Entitäten-Registry (Plattform + `unique_id`), nie über Entity-IDs.
- **Zähler Pflicht** (Lebenszeit, Wh/kWh/MWh, `total` oder `total_increasing`), dazu SoC in % mit `measurement`. Nur Leistung → Helfer „Integral“ (README).
- **Zählerstand statt `change`:** Speicherwacht liest den Stand je Stunde und lässt den Zählerbaustein aus Wärmewacht darüberlaufen (Rücksprünge, Resets, Ausreißer).
- **Bilanzgrenze** „Akku“ (DC) oder „System“ (AC) je Eintrag, Attribut `boundary`, nie gemischt.
- **Wirkungsgrad** = (Entladung + ΔSoC × Kapazität) / Ladung über die Betriebstage; **eigene Näherung**, so in README und Doku benannt. Ohne genug Ladung `unknown`, nie 0. Ruhetage zählen getrennt.
- **Kapazität** als Zahl in der Einrichtung (Vorlage füllt vor); die Schätzung ersetzt sie nie. Schätzung nur aus Entladungen voll → leer.
- **Vollzyklen** = Entladung / Kapazität; gesamt aus dem Zählerstand (seit Inbetriebnahme).
- Zeiträume: Monat, Jahr (Kalenderjahr), gesamt; Tag deaktiviert.
- Kein CO₂, keine Wirtschaftlichkeit im MVP; Standby-Signal später.
- **Mindestversion HA 2026.4.** Kein `country` in `hacs.json`.
- Lizenz MIT. Repo: `github.com/speicherwacht/integration` (Organisation legt der Inhaber an). `codeowners`: `@n42net`.

## Arbeitsregeln

1. **Formate nie raten.** Die Dateien in `tests/fixtures/` sind die Wahrheit über Entitäten, Attribute und Zustandswerte der Quellen (Herkunft in `tests/fixtures/_index.json`). Neue Hersteller nur mit Fixture; nur aus Quellcode abgeleitete Vorlagen stehen im README als „experimentell“ und in der Einrichtung als „(beta)“.
2. **Fachwerte nie aus dem Gedächtnis.** Definitionen, Feldwerte, Schwellen nur mit Quelle in `docs/ENTWICKLUNG.md`; eigene Annahmen als solche kennzeichnen.
3. **Keine personenbezogenen Daten ins Repo:** keine Zählerstände, Verläufe, Wirkungsgrade oder Anlagendaten des Inhabers – auch nicht als Testwerte. Fixtures haben echtes Format und erfundene Werte. Rohdaten nur in `raw/`.
4. Entwickelt wird gegen eine produktive Home-Assistant-Instanz. Logik erst als reines Python ohne HA-Importe testen (`tests/sim.py` simuliert einen Speicher). Ein Fehler (Quelle `unavailable`, Zähler springt) darf nie die Integration oder HA blockieren und nie still falsch rechnen.
5. Code, Kommentare, Entity-IDs auf Englisch; UI-Texte nur über `tools/make_strings.py` (erzeugt `strings.json`, `translations/de.json` und `en.json`, `icons.json`), nie direkt in den JSON-Dateien ändern. Doku auf Deutsch.
6. Tests gegen Fixtures. HA-Tests (`tests/ha/`, `pytest-homeassistant-custom-component`) nur in GitHub Actions.
7. **Branches:** Entwickelt wird auf `dev`; `main` erhält nur freigegebene Stände (Ablauf unter „Release“). Ein Ruleset erzwingt grüne CI (`test`, `hassfest`, `compat`) für `main`. Kein Force-Push, Tags `v*` sind unveränderlich.
8. **Fehler in Quell-Integrationen** dort melden (nach Rückfrage beim Inhaber, Text vorher zeigen), nicht in Speicherwacht wegtricksen; bis zur Behebung ein dokumentierter Umweg mit Verweis auf das Issue.
9. **Werkzeuge:** `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run python tools/make_strings.py .`. `homeassistant` (dev) und `pytest-homeassistant-custom-component` (ha-tests) immer gemeinsam anheben. Rechnerspezifisches und die Testanlage stehen in `CLAUDE.local.md`.

## Release

Gleicher Ablauf in allen Schwesterprojekten (Eilwacht, Einspeisewacht, Speicherwacht, Streckenwacht, Tarifwacht, Wärmewacht). Neue Erkenntnisse zum Ablauf hier eintragen und für die Schwestern melden.

**Versionsnummer** (seit 2026-11-13, Andys Ja, gleich in allen sechs Wachten): die zweite Ziffer (0.x.0) bei neuen Sensoren, Blueprints oder Funktionen und bei allem mit „Bitte prüfen“; die dritte (0.x.y) nur bei Fehlerbehebungen und geänderten Texten. Nach Vorabversionen gilt zusätzlich Schritt 6.

**Version 1.0** (seit 2026-11-13, Andys Ja, gleich in allen sechs Wachten): 1.0.0 erst, wenn (1) ein paar Wochen kein Eintrag „Bitte prüfen“, keine umgezogenen Attribute und keine geänderte Bedeutung von Werten kamen, (2) der Kern fertig ist und die wichtigen Vorlagen bzw. Quellen von echten Nutzern bestätigt sind, (3) keine Fehlerberichte offen sind und die CI dauerhaft grün ist. Ab 1.0 bekommt alles, was bestehende Automationen, Dashboards oder Einstellungen bricht, eine neue erste Ziffer (2.0.0) und einen Eintrag „Bitte prüfen“. Stand 13.11.: erster Kandidat Streckenwacht (nach 0.10.0 und 2–3 Wochen ohne Fehler), Einspeisewacht zusammen mit dem EEG-2027-Update, Wärmewacht frühestens nach dem Winter.

1. Version in `manifest.json`, `const.py` und `pyproject.toml` anheben, `uv lock`; `tests/test_manifest.py` prüft die Gleichheit. „Unveröffentlicht“ in `CHANGELOG.md` zur Version machen. Danach `uv run tools/make_demo.py` laufen lassen und geänderte Dateien unter `docs/demo/` in den Versions-Commit nehmen: Die Demo zeigt die Version und rechnet mit dem Code der Integration, Pages baut nur `main` (Eilwacht 0.3.2 zeigte so noch 0.3.1).
2. `dev` pushen und auf den CI-Lauf **genau dieses Commits** warten (`gh run list --commit <sha>` mit vollem SHA aus `git rev-parse HEAD`, ein Kurz-SHA findet nichts): Push-CI startet manchmal Minuten verspätet, ein älterer grüner Lauf täuscht.
3. `main` vorspulen mit `git push origin dev:main` – **ohne Branch-Wechsel** im Arbeitsverzeichnis (auf dem Netzlaufwerk hat `git switch` schon Dateien verloren, ein Release entstand so auf altem Stand). Danach prüfen, dass `origin/main` auf dem Versions-Commit steht.
4. `gh release create vX --target main --latest --notes-file …` (Text nach „Release-Notes“ unten). Ziel `main`, kein Kurz-SHA (gibt 422). Immer ein **reguläres** Release, auch für Betas, nie `--prerelease`: Sonst nimmt HACS den letzten Commit und sucht dort vergeblich die ZIP. Blockiert der Auto-Modus das Veröffentlichen: Befehl nennen, der Inhaber führt ihn aus – nie umgehen.
5. Workflow „Release-ZIP“ prüfen: `speicherwacht.zip` muss am Release hängen. Der Workflow bricht ab, wenn Tag und `manifest.json` nicht passen; fehlt die ZIP, ihn per Hand mit dem Tag starten. Ohne ZIP scheitern HACS-Installationen.
6. Prüfen, dass HACS die neue Version sieht: `gh api repos/speicherwacht/integration/releases --jq '.[0].tag_name'` muss das neue Tag sein – HACS nimmt den **ersten** Eintrag dieser Liste, nicht „Latest“. GitHub sortiert sie offenbar nach der Basisversion; innerhalb derselben Basis (`0.1.0b1` … `0.1.0b10`, `0.1.0`) ist die Reihenfolge willkürlich (Tarifwacht 2026-10-27: b10 und 0.1.0 landeten hinter b6, HACS bot keine von beiden an). **Regel:** Nach Vorabversionen die nächste Version mit **höherer Basis** veröffentlichen (`0.1.1` statt `0.1.0` nach `0.1.0b…`), und Vorabnummern zweistellig gar nicht erst erreichen.
7. Bricht eine Sitzung mitten im Release ab: erst den Stand prüfen (`git log origin/dev origin/main`, CI des Commits, `gh release list`), dann weitermachen.

### Release-Notes (seit 2026-11-11, Anlass Wärmewacht-Issue #5)

HACS zeigt den Release-Text in der Update-Entität von HA. Deshalb **Englisch zuerst, Deutsch darunter** (gleich in allen sechs Wachten):

- Erste Zeile `*(German version below · Deutsche Fassung weiter unten)*`, dann `## English` mit der englischen Fassung, dann `## Deutsch` mit dem Abschnitt aus dem `CHANGELOG.md` wörtlich. **Kein eigenes `---`:** HACS hängt die Texte aller Releases zwischen installierter und neuester Version aneinander (höchstens fünf, Einstellung `release_limit`), je mit `# vX` davor und `---` danach (`update.py`, `async_release_notes`, geprüft 11.11.). Deshalb zählen auch die Texte der letzten fünf Releases, nicht nur der neueste.
- Gruppen, nur wenn belegt, in dieser Reihenfolge: **Action needed / Bitte prüfen** (Breaking Changes, alles, was man nach dem Update selbst tun muss), **New / Neu**, **Fixed / Behoben**, **Changed / Geändert**. Das `CHANGELOG.md` hat dieselben Gruppen als `###`.
- Jeder Eintrag: fette Überschrift, dann ein bis drei Sätze (was ändert sich, wen betrifft es, was ist zu tun). Hintergrund (Rechenweg, Quellen, Messwerte) gehört in README oder `docs/ENTWICKLUNG.md`, im Eintrag höchstens ein Link.
- Statt „Anlass: …“ am Ende des Eintrags „(thanks to … / danke an …)“. GitHub-Nutzer mit `@login` (GitHub benachrichtigt sie und zeigt sie als Beitragende am Release), Forum-Nutzer mit ihrem öffentlichen Namen und dem Forum, z. B. „(thanks to suedschwede, simon42 forum)“. Eigene Prüfung: nichts dazuschreiben.
- Im englischen Teil die Begriffe aus `translations/en.json` verwenden, keine eigene Übersetzung von Feldnamen.

„Unveränderliche Releases“ bleibt in GitHub aus, weil der Workflow die ZIP erst nach dem Veröffentlichen anhängt; die Tags `v*` schützt das Ruleset.

## Fallstricke (dauerhaft)

- **Zeitrechnung intern in UTC.** Tage als `[local_midnight(d), local_midnight(d+1))`, nie als +24 h (Umstellungstage haben 23 bzw. 25 Stunden).
- **Statistik:** Zählerstand (`state`) je Stunde lesen, nicht `change` (siehe Entscheidungen). SoC nur als Stundenmittel/-min/-max – Grenzwerte sind Schätzungen (`days.soc_at`).
- **Binärsensoren haben keine Langzeitstatistik.** Ein Signal wie Fronius „Akku-Standby“ bräuchte einen Listener und eine Speicherdatei.
- **Schreiblast:** keine Speicherdatei; Werte auf Anzeigegenauigkeit runden, große Listen in `_unrecorded_attributes`.
- HA-Tests: Zeitzone ist US/Pacific → `hass.config.async_set_time_zone("Europe/Berlin")`. Recorder-Tests: `recorder_mock` vor `hass`/`enable_custom_integrations` anfordern. Vor `async_fire_time_changed` immer `await hass.async_block_till_done()`. Timer mit `cancel_on_shutdown=True`.
- Git auf dem Netzlaufwerk: Gearbeitet wird auf dem ausgecheckten Branch `dev`, nie `git switch`/Checkout zwischen Branches. Vor jedem Commit `git status -sb`.
- Home Assistant läuft auf diesem Windows-Rechner nicht (`fcntl`). HA-MCP ist nur lesend; der gesteuerte Browser braucht die Anmeldung des Inhabers.
- Shell-Heredocs mit Anführungszeichen scheitern: Bearbeitungsskripte als Datei in den Scratchpad schreiben. Python schreibt unter Windows mit `write_text` CRLF: `write_bytes(text.encode())` oder `newline="\n"`.
- **Nie committen, wenn ein Test rot ist.** Ergebnis in eine Datei schreiben, auf „ failed“ prüfen, erst dann committen.
- Release-Titel ohne „v“ (`0.2.0`), Tag mit (`v0.2.0`).
- Config-Flow: `NumberSelector` lehnt `step` unter 0,001 ab (dann `"any"`).
