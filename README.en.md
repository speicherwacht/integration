<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/github/readme-header-dark@2x.png">
  <img alt="Speicherwacht – Every charge. Every cycle." src="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/github/readme-header-light@2x.png" width="640">
</picture>

[![Release](https://img.shields.io/github/v/release/speicherwacht/integration?color=007D7F)](https://github.com/speicherwacht/integration/releases)
[![CI](https://github.com/speicherwacht/integration/actions/workflows/ci.yml/badge.svg)](https://github.com/speicherwacht/integration/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623.svg)](LICENSE)

[Deutsch](https://github.com/speicherwacht/integration/blob/main/README.md) · **English**

**How well does my battery storage really work?** Speicherwacht is a Home Assistant integration that turns the existing counters of your home or balcony battery into its efficiency per month and year, full cycles, rest loss and the capacity you can actually take out – vendor-neutral, read-only, no cloud.

> **New.** Speicherwacht is a young integration. The Fronius template is tested on a real installation, the others were built from the source code of the respective integration. Feedback is welcome.

## Contents

- [What Speicherwacht does](#what-speicherwacht-does) · [Requirements](#requirements) · [Installation](#installation) · [Setup](#setup)
- [Entities](#entities) · [Health check](#health-check) · [How it calculates](#how-it-calculates) · [Limits](#limits)
- [Troubleshooting](#troubleshooting) · [Privacy](#privacy) · [Removal](#removal) · [Related projects](#related-projects)

## What Speicherwacht does

- **Efficiency** per month, year and total (per day, disabled by default): discharge against charge, corrected by the change of the state of charge. Without this correction a monthly value swings with the level at the end of the month.
- **Rest days apart:** days on which the battery hardly works (winter, emergency reserve, maintenance) do not count into the efficiency; their losses are shown as a separate attribute.
- **Full cycles** since commissioning and in the current year, optionally **warranted throughput used** in %.
- **Rest loss:** mean power the resting battery loses (mostly the battery management's own consumption).
- **Capacity (estimated):** energy taken out in discharges from full to empty, compared with the data sheet.
- **Look-back from day one:** Speicherwacht works from Home Assistant's long-term statistics, so the time before the setup counts too.
- **Repair issues** when a source is missing, unavailable for long or has a wrong unit.
- No storage file of its own, no extra write load on SD cards.

<img src="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/screenshots/geraet.png" alt="Device of a battery storage with efficiency per month, year and overall, rest loss, estimated capacity, full cycles and the three checks of the health check (German UI)" width="720">

## Requirements

- Home Assistant **2026.4** or newer, with the recorder.
- Three entities of your battery, each **with long-term statistics**:
  - **energy charged** and **energy discharged** as lifetime counters (Wh, kWh or MWh; state class `total` or `total_increasing`),
  - **state of charge** in % (state class `measurement`).
- The **usable capacity** from the data sheet.
- **Only power (W), no counters?** Create one counter for charging and one for discharging with the *Integral* helper (Settings → Devices & services → Helpers → Integral, method "Left"). The look-back then starts when the helpers were created.

## Installation

Speicherwacht is installed through HACS as a custom repository. Every version is a regular GitHub release.

1. HACS → ⋮ → *Custom repositories* → `https://github.com/speicherwacht/integration`, type *Integration*.
2. Search for Speicherwacht and download it. Restart Home Assistant.
3. *Settings → Devices & services → Add integration → Speicherwacht*.

## Setup

The first step lists the storages Speicherwacht detected plus "Map entities myself". In the second step you check the entities, enter the usable capacity and choose what the counters measure.

| Source | Integration | Status |
| --- | --- | --- |
| Fronius GEN24 with battery | core `fronius` with Modbus TCP (HA 2026.9+) | tested |
| Huawei SUN2000 with LUNA2000 | [huawei_solar](https://github.com/wlcrs/huawei_solar) | experimental (beta) |
| Deye and others via Solarman logger | [solarman](https://github.com/davidrapan/ha-solarman) | experimental (beta) |
| Anker SOLIX Solarbank 1–4 | [anker_solix](https://github.com/thomluther/ha-anker-solix) | experimental (beta) |
| Anker SOLIX Solarbank 4, Max, XE | [anker_solix_official](https://github.com/anker-charging/ha-anker-solix-official) | experimental (beta) |
| GoodWe ET, EH, BT, BH | core `goodwe` | experimental (beta) |
| Victron with BMV, SmartShunt or Lynx | core `victron_gx` | experimental (beta) |
| SolarEdge StorEdge | [solaredge_modbus_multi](https://github.com/WillCodeForCats/solaredge-modbus-multi) | experimental (beta) |
| SolaX, Sofar | [solax_modbus](https://github.com/wills106/homeassistant-solax-modbus) | experimental (beta) |
| Sungrow SH | [Modbus YAML by mkaiser](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) | experimental (beta) |
| Sigenergy SigenStor | [sigen](https://github.com/TypQxQ/Sigenergy-Local-Modbus) | experimental (beta) |
| Zendure SolarFlow, Hyper, Hub | [zendure_ha](https://github.com/Zendure/Zendure-HA) | experimental (beta) |
| Marstek Venus E | [marstek_modbus](https://github.com/ViperRNMC/marstek_venus_modbus) or [Marstek Modbus Suite](https://github.com/sphings79/marstek-modbus-suite) | experimental (beta) |
| all others | map entities yourself | – |

- **Own mapping:** if your battery is set up in the energy dashboard, Speicherwacht proposes its counters, state of charge and capacity from there.
- **Fronius:** without Modbus TCP the integration has no battery counters; then map them yourself (e.g. with Integral helpers).
- **Anker SOLIX (cloud):** the lifetime counters come only by MQTT with the owner account, and the integration creates them only once you no longer exclude the category `solarbank_energy` in its options. The setup points this out.
- **GoodWe:** only ET, EH, BT and BH have battery counters; ES, EM and BP report the state of charge only.
- **Victron:** the counters come from the battery monitor (BMV, SmartShunt, Lynx). A battery connected by CAN-BMS only has none. The system's "DC battery charge/discharge energy" start at 0 after every restart and are not usable.
- **SolarEdge:** battery entities exist only with the option "Auto-Detect Batteries". With LG and BYD batteries the counters sometimes drop to 0; the integration then holds the old value and Speicherwacht reports "counters and state of charge disagree".
- **SolaX:** "Battery Input Energy Total" and "Battery Output Energy Total" are disabled; enable them and reload the integration. The setup points this out.
- **Sungrow:** according to the package, "Battery level" runs from 0 to 100 % between the inverter's minimum and maximum state of charge. The estimated capacity then shows only that window; if it is much narrower than the whole battery, enter its capacity.
- **Sigenergy:** Speicherwacht takes the plant's counters (Modbus protocol v2.7 and later). Older firmware lacks them; then map the inverter's counters yourself.
- **Zendure:** the integration sums up the counters from the battery power; the device has none. Speicherwacht can then only check that these values are consistent. After renaming the device in the Zendure app, choose the entities again under *Reconfigure*.
- **Marstek:** Venus E only. On Venus A and D the solar power passes through the discharge counter; they are not detected. The counters measure at the socket, i.e. the whole storage.
- **The counters measure:** *the battery* (DC, e.g. the inverter's battery counters) or *the whole storage* (AC, e.g. a plug meter in front of a balcony battery). Values of the two boundaries are not comparable; AC includes the inverter losses.
- **Warranted throughput (optional):** the energy in MWh your warranty covers. Adds the sensor "Warranted throughput used".
- **Reconfigure:** Devices & services → Speicherwacht → ⋮ → *Reconfigure*.

After the setup Speicherwacht calculates after about a minute and then every hour (shortly after :12, once Home Assistant has written the hourly statistics).

## Entities

| Entity | Meaning |
| --- | --- |
| Efficiency month / year / total | discharge plus change of the stored energy, divided by charge, over the operating days. "total" starts with the counters' long-term statistics. |
| Efficiency today | as above for the current day; disabled by default because a single day depends strongly on the state of charge at its boundaries |
| Full cycles total | discharge since commissioning (counter reading) divided by the capacity |
| Full cycles year | discharge in the calendar year divided by the capacity |
| Warranted throughput used | discharge since commissioning in % of the warranted throughput (only if entered) |
| Rest loss | mean power lost while resting over the last 30 days, in W |
| Capacity (estimated) | median energy per 100 % state of charge from discharges from full to empty (90 days) |

Attributes show what a value is made of: charged, discharged, change of stored energy, operating and rest days, loss on rest days, boundary, period. If a value is unknown, `reason` says why:

| `reason` | Meaning |
| --- | --- |
| `not_analysed_yet` | not calculated yet (about a minute after the start) |
| `no_recorder` | recorder not active |
| `no_data` | no counter values in the period |
| `too_little_charge` | less charged than one capacity (day: half) |
| `no_soc` | no state of charge at the day boundaries |
| `too_few_rest_hours` | fewer than 24 rest hours in 30 days |
| `soc_rose_at_rest` | state of charge rose while resting – charging past the counters or a drifting state of charge; the computed value is in the attribute `raw_watts` |
| `too_few_discharges` | fewer than three discharges from full to empty in 90 days |

The sensors can go on a dashboard like any other, for example as tiles with a statistics graph of the charge and discharge counters:

<img src="https://raw.githubusercontent.com/speicherwacht/integration/main/assets/screenshots/dashboard_energie.png" alt="Dashboard section with efficiency per month, year and overall, rest loss, capacity, state of charge, full cycles and a bar chart of the energy charged and discharged per month (German UI)" width="720">

## Health check

Three problem sensors (on = conspicuous, unknown = not enough data yet, reason in the attribute `reason`) and one repair issue. They tell *what* stands out, not *why* – no expert diagnosis.

| Entity | On when … |
| --- | --- |
| Efficiency below last year | the efficiency of the last 30 days is at least 3 percentage points below the same 30 days a year before (compared with last year because efficiency follows the season) |
| Capacity low | the estimated capacity is below 80 % of the data sheet (end of life in the field) or 10 points below the estimate a year ago (2–3 points a year are normal) |
| Rest loss high | the rest loss is above 64 W (highest standby in the HTW Berlin lab test) or at least 50 % and 10 W above the same days a year before |

**Repair issue "Counters and state of charge disagree":** over the last day the state of charge moved a lot and the counters did not – or the other way round. Usually a counter is stuck, the state of charge is frozen or an entity is mapped wrongly.

The comparisons with last year need a year of long-term statistics; until then these checks are unknown. Rules, sources and thresholds: [docs/GESUNDHEITSCHECK.md](docs/GESUNDHEITSCHECK.md) (German).

## How it calculates

- **Basis** are the hourly values of the long-term statistics. Speicherwacht reads the counter reading per hour and handles steps back, counter restarts and outliers itself (some integrations report counters without a reset marker or briefly a wrong value).
- **Correction by the state of charge:** efficiency = (discharge + Δstate of charge × capacity) / charge. This is **an approximation of its own**: test benches such as the HTW Berlin storage inspection measure only between equal states of charge (full → empty → full). Over a month or a year the difference stays small (below 1 %) because the throughput is many capacities; single days vary more.
- **Rest day:** charge and discharge each below 5 % of the capacity.
- **Rest loss:** drop of the state of charge in hours without noteworthy charging or discharging, at least three hours in a row.
- **Capacity (estimated):** only from discharges from at least 90 % to at most 15 % state of charge without charging in between. Smaller swings do not count: the state of charge is calculated by the battery management, and they would only return its own assumption.
- **Full cycles** count the energy discharged, as warranties do.

Sources and reasons: [docs/ENTWICKLUNG.md](docs/ENTWICKLUNG.md) (German), section 3.

## Limits

- Speicherwacht is **an orientation, not an expert diagnosis**. It works with the counters of your inverter or battery – if they are inaccurate, so are the results.
- The state of charge of LFP batteries is a calculated value and may jump (e.g. during a calibration charge). A jump at a month boundary shifts that month's efficiency a little.
- A lab battery efficiency (DC) of current home batteries is around 95–97 %. In daily use values are lower: partial load, the battery management's own consumption and rest phases cost energy. AC values ("whole storage") also include the conversion losses.
- The estimated capacity scatters. For LFP batteries a field study of RWTH Aachen (Figgener et al. 2024) reports about ±8 percentage points for a more refined method. Watch the trend over months, not a single value.

## Troubleshooting

- **Repair issue "entity missing", "source not available" or "unexpected unit":** check the source integration or choose other entities under *Reconfigure*. The issues disappear by themselves.
- **Source renamed** (entity ID changed, also via "Recreate entity IDs"): since 0.1.1 Speicherwacht follows the new ID itself and reloads the entry shortly after; no need to *Reconfigure*. The history is kept because Home Assistant renames the statistics too. Only a deleted entity reports "entity missing".
- **Repair issue "Counter starts anew every day" or the "day counter" warning in the setup:** a counter fell back at the same time of day on several days, like an "energy today" counter. Speicherwacht needs total (lifetime) counters; choose the matching one under *Reconfigure*. If it is a total counter after all, ignore the notice or submit the setup again unchanged.
- **All values stay unknown:** do the counters and the state of charge have long-term statistics? *Tools → Statistics* (before 2026.8: Developer tools) shows it. Without a state class there are none.
- **Efficiency above 100 %:** usually the charge and discharge counters measure at different places, energy enters the battery past the charge counter (say PV straight into the battery of a DC-coupled balcony storage), or the state of charge is mapped wrongly.
- **Rest loss unknown with `soc_rose_at_rest`:** in hours without charging and discharging the state of charge rose. Then something charges past the charge counter (see above) or the state of charge drifts. Up to one step of the state of charge (1 %) over all rest hours Speicherwacht shows 0 W, as that can be rounding. The health check "Rest loss high" stays unknown then.
- **Diagnostics file:** Devices & services → Speicherwacht → ⋮ → *Download diagnostics*; it also lists the values the counter module rejected.

## Privacy

Speicherwacht fetches nothing from the internet and sends nothing. The diagnostics file contains energy sums and the states of your source entities – check it before sharing.

## Removal

Devices & services → Speicherwacht → ⋮ → *Delete*. Speicherwacht creates no files; the long-term statistics of its own sensors stay in the recorder until you delete them under *Tools → Statistics*. Then uninstall it in HACS.

## Reporting issues

[Open an issue](https://github.com/speicherwacht/integration/issues/new/choose), ideally with the diagnostics file, battery model and integration.

## Related projects

- [Marstek Capacity Monitor](https://github.com/satscan1/marstek-capacity-monitor): capacity measurement, cycles and SoC drift for Marstek batteries. For Marstek it goes deeper than Speicherwacht.
- [battery_sim](https://github.com/hif2k1/battery_sim): simulates what a battery would bring – for the time before buying one.
- Many vendor integrations (Zendure, Anker SOLIX, Marstek) show their own efficiencies, mostly discharge / charge without a correction by the state of charge.

## License

MIT, see [LICENSE](LICENSE).
