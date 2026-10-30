# Speicherwacht – Gesundheits-Check

Stand: 2026-10-30 (für 0.1.0b3). Ergänzt `docs/ENTWICKLUNG.md` §3; Quellen, die dort stehen, werden hier nur verwiesen. Muster ist Wärmewacht (`../waermewacht/docs/GESUNDHEITSCHECK.md`).

## Grundsätze

- **Unbekannt statt falscher Alarm.** Reichen die Daten nicht, ist eine Prüfung `unknown` und nennt im Attribut `reason` den Grund.
- **Gleiches mit Gleichem vergleichen.** Wirkungsgrad und Ruheverlust hängen an der Jahreszeit (Teillast, Ruhe bei leerem oder vollem Akku). Verglichen wird deshalb mit denselben 30 Tagen des Vorjahres, nicht mit dem Vormonat.
- **Nur lesen.** Die Prüfungen sagen, was auffällt, nicht warum.
- **Anzeige wie bei Wärmewacht:** Befund am Speicher = Binärsensor mit `device_class: problem`; Datenfehler, die der Nutzer beheben kann = Reparaturhinweis.
- Kern ohne HA-Importe: `health.py`, getestet mit dem Simulator (`tests/test_health.py`).

## Prüfungen

| Prüfung | Anzeige | Regel | Quelle / Annahme |
| --- | --- | --- | --- |
| Wirkungsgrad unter Vorjahr (`efficiency_drop`) | Binärsensor | Wirkungsgrad (korrigiert, ohne Ruhetage) der letzten 30 vollen Tage mindestens **3 Prozentpunkte** unter denselben 30 Tagen des Vorjahres; je Seite mindestens 15 Betriebstage und 2 Kapazitäten Ladung | **eigene Annahme**; an der Testanlage liegen die korrigierten Sommermonate in einem Band von gut einem Punkt, der Vorjahresvergleich schwankte über zehn Wochen zwischen −1,4 und +0,1 Punkten |
| Kapazität gesunken (`capacity_low`) | Binärsensor | geschätzte Kapazität unter **80 %** des Datenblatts, oder **10 Punkte** (bezogen auf das Datenblatt) unter der Schätzung vor einem Jahr | 80 %: Lebensende im Feld (Figgener et al. 2024, ENTWICKLUNG §3); Alterung im Feld 2–3 Punkte pro Jahr, 10 Punkte **eigene Annahme** |
| Ruheverlust hoch (`rest_loss_high`) | Binärsensor | Ruheverlust (30 Tage) über **64 W**, oder mindestens **+50 % und +10 W** gegenüber denselben 30 Tagen des Vorjahres | 64 W: höchster Stand-by-Wert der HTW-Stromspeicher-Inspektion 2026 (SSI26 Bild 24); Anstieg **eigene Annahme** (wie Wärmewacht 4.8) |
| Zähler und Ladezustand passen nicht (`counter_soc_mismatch`) | Reparaturhinweis | in den letzten 24 vollständigen Stunden: Ladezustand bewegt sich um mindestens 30 Punkte, die Zähler um weniger als 5 % der Kapazität – oder die Zähler bewegen mindestens eine halbe Kapazität, der Ladezustand bleibt innerhalb von 2 Punkten | **eigene Annahme** (Physik: Ladung ohne Bewegung des Ladezustands ist unmöglich) |

Dazu bestehen die Reparaturhinweise `missing_entity`, `source_unavailable`, `source_unit` und `counter_resets` (ENTWICKLUNG §7).

## Warum nicht gegen den Vormonat

Erster Entwurf für den Ruheverlust: +50 % und +10 W gegenüber den 30 Tagen davor. An der Testanlage stieg der Ruheverlust im Mai 2026 von 18 auf 30 W, ohne Fehler – im Frühjahr ruht der Akku öfter voll, im Winter leer, und beides verbraucht unterschiedlich viel (HTW: Fronius + BYD leer 9–12 W, voll 1–2 W, SSI25 Bild 42/43). Der Vergleich mit dem Vorjahr vermeidet das. Wochenweise über ein Jahr nachgerechnet: kein Alarm an 61 Stichtagen.

## Gründe für „unbekannt“ (`reason`)

| Schlüssel | Bedeutung |
| --- | --- |
| `not_analysed_yet` | noch nicht gerechnet |
| `no_previous_year` | keine ausreichenden Daten für dieselben Tage des Vorjahres |
| `too_few_days` | zu wenige Betriebstage in den letzten 30 Tagen |
| `no_estimate` | keine Kapazitätsschätzung (weniger als drei Entladungen von voll bis leer in 90 Tagen) |
| `no_rest_loss` | zu wenige Ruhestunden in den letzten 30 Tagen |

## Offen

- Hysterese: Die Prüfungen sind zustandslos und können an einer Schwelle hin und her springen. Bisher nicht beobachtet; sonst Rückstellung erst unter einer zweiten Schwelle.
- Schwellen nach dem ersten Winter an der Testanlage prüfen.
