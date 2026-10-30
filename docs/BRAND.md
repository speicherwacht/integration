# Speicherwacht – Marke & Bilddateien

## Idee

Ein stehender Akku mit vier Ladebalken; das Wachlicht mit Halo ist sein Pluspol und sitzt an derselben Stelle wie bei Streckenwacht und Wärmewacht. Der oberste Balken ist nur umrissen: Wie viel wirklich hineinpasst, ist das, worüber Speicherwacht wacht. Kachel, Schutzzone, Amber-Wachlicht, Off-White und Schrift sind dieselben wie bei Streckenwacht, Eilwacht, Einspeisewacht, Tarifwacht und Wärmewacht – so bleiben die Integrationen als Geschwister erkennbar. Die Kachelfarbe ist **RAL 5021 Wasserblau**.

**Slogan:** „Jede Ladung. Jeder Zyklus.“ (englisch „Every charge. Every cycle.“)

## Farben

| Rolle | Hex | Hinweis |
| --- | --- | --- |
| Kachel, Wortmarke | `#007D7F` | RAL 5021 Wasserblau, umgerechnet aus CIE L\*a\*b\* 47,15 / −29,26 / −9,32 (D65, Quelle: de.wikipedia.org, Artikel „RAL-Farbe“) |
| Wachlicht | `#F5A623` | Amber, wie bei den Geschwistern |
| Motiv, Rand um das Wachlicht | `#FBF7EE` | warmes Off-White |
| Heller Hintergrund | `#FAF7F2` | README-Kopf, Social Preview |
| Dunkler Hintergrund | `#14181D` | README-Kopf (Dark Mode) |
| Tagline hell / dunkel | `#6B6357` / `#B9B2A6` | |

Halo: Amber-Ring mit 35 % Deckkraft. Kontrast Kachel zu Off-White 4,6 : 1 (für Grafik ≥ 3 : 1), zu Amber nur 2,4 : 1 – deshalb sitzt das Wachlicht auf einem schmalen Off-White-Rand. Umrechnung wie bei Tarifwacht und Wärmewacht (D65 → XYZ → sRGB); dieselbe Rechnung ergibt für RAL 2009, 4006 und 5017 genau die Werte von Wärmewacht, Tarifwacht und Streckenwacht.

## Schrift

**Space Grotesk** (Google Fonts, SIL Open Font License), Bold 700 für die Wortmarke, Medium 500 für Tagline und Zusatzzeilen. In allen SVGs ist der Text in Pfade umgewandelt.

## Dateien

| Ort | Inhalt |
| --- | --- |
| `custom_components/speicherwacht/brand/` | `icon(@2x)`, `dark_icon(@2x)`, `logo(@2x)`, `dark_logo(@2x)` – lädt Home Assistant ab 2026.3 aus der Integration |
| `assets/github/` | README-Kopf hell/dunkel (960×220, @2x), Social Preview 1280×640, Profilbild der Organisation 500/1024 |
| `assets/brand/svg/` | Vektor-Master: Icon, Mini-Icon, vollflächiges Icon, Motiv, Logo, README-Kopf, Social Preview |
| `assets/brand/png/` | Icon 16–2048 px, Motiv ohne Kachel, Logo hell/dunkel |
| `assets/brand/favicon/` | `favicon.ico` (16/32/48), `favicon.svg`, PNG, Apple-Touch- und Android-Icons |

Profilbild der Organisation und Social Preview lassen sich nicht per API setzen: von Hand hochladen (Organisation → Settings → Profile; Repo → Settings → General → Social preview).

## Regeln

- **≤ 32 px immer die Mini-Variante**: dickerer Akku-Rand, ein voller Block statt der Balken, größeres Wachlicht auf Off-White-Rand, kein Pol und kein Halo.
- Motiv ohne Kachel: auf hellem Grund in Wasserblau (`mark-on-light`), auf dunklem in Off-White (`mark-on-dark`).
- Farben nicht verändern, Motiv nicht verzerren, keine Schatten oder Verläufe.
- Um Logo und Icon mindestens ¼ der Kachelbreite frei lassen.

## Neu erzeugen

```bash
cd tools/brand
npm install
node build.mjs
```

Das Skript (von Wärmewacht übernommen, dort von Tarifwacht) schreibt direkt an die Plätze oben; vorher werden diese Ordner geleert. Farben, Name, Slogan und Unterzeile stehen als Konstanten oben in `build.mjs`.

## Entstehung

Verglichen auf einer Design-Fläche (privat, für Eingeladene: `https://claude.ai/artifact/CdX36F6sF6g7yrP47LXDVN`): Motive A „Pluspol“ (stehender Akku), B „Zyklus“ (liegender Akku mit Kreispfeilen), C „Restkapazität“ (liegender Akku, letzte Zelle kürzer, Wachlicht darüber); Farben RAL 5021 Wasserblau, RAL 7043 Verkehrsgrau B, RAL 6033 Minttürkis. Verworfen: RAL 6018 Gelbgrün (2,7 : 1 zum Off-White) und RAL 1023 Verkehrsgelb (1,5 : 1). Wasserblau liegt am nächsten am Verkehrsgrün der Einspeisewacht, bleibt neben ihr aber unterscheidbar. Gewählt am 2026-10-30: A in Wasserblau mit „Jede Ladung. Jeder Zyklus.“
