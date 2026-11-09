/*
 * Speicherwacht card: the health of one battery storage at a glance –
 * findings of the health check, the figures and the last twelve months –
 * without extra cards from HACS. Served and registered by the integration
 * itself (cards.py, frontend_resource.py).
 *
 *   type: custom:speicherwacht-card
 *   device_id: <optional: the only Speicherwacht device otherwise>
 *   sections: [health, figures, months]   (optional; default: all)
 *   title: …                              (optional; a single space hides the heading)
 *
 * The card finds its entities by device and translation key (entity
 * registry), so the language of Home Assistant and renamed entity ids do
 * not matter; states are formatted by Home Assistant. Months and repair
 * issues come from the websocket command "speicherwacht/card": the
 * integration computes them from the hours it has read anyway, no recorder
 * query. Figures above are the calendar year, the chart shows the last
 * twelve months (rule of all Wacht cards).
 */

// The integration loads the file with "?v=<version>" (cards.py).
const CARD_VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const DOMAIN = "speicherwacht";
const SECTIONS = ["health", "figures", "months"];
const CHECKS = ["efficiency_drop", "capacity_low", "rest_loss_high"];
// Repair issues of an entry (runtime.ISSUES).
const ISSUES = ["missing_entity", "source_unavailable", "source_unit", "counter_resets", "counter_soc_mismatch", "own_entity"];
// Thresholds the texts name (analysis.py, health.py).
const NEEDS = { discharges: 3, rest_hours: 24, operating_days: 15, end_of_life: 80 };
const DOCS = "https://github.com/speicherwacht/integration#karte";

const TEXT = {
  de: {
    title: "Batteriespeicher",
    describe: "Gesundheits-Check, Wirkungsgrad, Kapazität, Ruheverlust und Vollzyklen eines Speichers, dazu die letzten 12 Monate.",
    noDevice: "Kein Speicherwacht-Gerät gefunden.",
    nothing: "Keine Daten für diese Karte.",
    sections: { health: "Befund", figures: "Kennzahlen", months: "Monate" },
    checks: {
      efficiency_drop: "Wirkungsgrad gegen Vorjahr",
      capacity_low: "Kapazität",
      rest_loss_high: "Ruheverlust",
    },
    issues: {
      missing_entity: "Entität fehlt",
      source_unavailable: "Quelle nicht erreichbar",
      source_unit: "Unerwartete Einheit",
      counter_resets: "Zähler beginnt jeden Tag neu",
      counter_soc_mismatch: "Zähler und Ladezustand passen nicht zusammen",
      own_entity: "Eigener Sensor als Quelle",
    },
    issueText: "Hinweis unter Einstellungen → Reparaturen",
    fine: "unauffällig",
    unknown: "noch nicht beurteilbar",
    detail: {
      efficiency_drop: {
        ok: (a, n) => `${n(a.current_percent, 1)} %, Vorjahr ${n(a.previous_year_percent, 1)} %`,
        problem: (a, n) => `${n(a.drop_points, 1)} Punkte unter Vorjahr: ${n(a.current_percent, 1)} % statt ${n(a.previous_year_percent, 1)} %`,
      },
      capacity_low: {
        ok: (a, n) => `${n(a.share_percent, 0)} % des Datenblatts`,
        low: (a, n) => `unter ${n(a.end_of_life_percent, 0)} % des Datenblatts: ${n(a.share_percent, 0)} %`,
        drop: (a, n) => `${n(a.drop_points, 0)} Punkte weniger als vor einem Jahr: ${n(a.share_percent, 0)} % des Datenblatts`,
      },
      rest_loss_high: {
        ok: (a, n) => (a.previous_year_watts !== null && a.previous_year_watts !== undefined
          ? `${n(a.watts, 0)} W, Vorjahr ${n(a.previous_year_watts, 0)} W` : `${n(a.watts, 0)} W`),
        high: (a, n) => `über ${n(a.max_watts, 0)} W: ${n(a.watts, 0)} W`,
        rise: (a, n) => `deutlich über Vorjahr: ${n(a.watts, 0)} W statt ${n(a.previous_year_watts, 0)} W`,
      },
    },
    reasons: {
      not_analysed_yet: "wird gerade gerechnet …",
      no_recorder: "Recorder nicht aktiv",
      no_data: "keine Zählerwerte im Zeitraum",
      no_soc: "kein Ladezustand an den Tagesgrenzen",
      too_little_charge: "noch weniger als eine Kapazität geladen",
      too_few_rest_hours: (h) => `erst ${h} von ${NEEDS.rest_hours} Ruhestunden in 30 Tagen`,
      soc_rose_at_rest: "Ladezustand stieg in Ruhephasen – Laden außerhalb der Zähler?",
      too_few_discharges: (k) => `erst ${k} von ${NEEDS.discharges} Entladungen von voll bis leer in 90 Tagen`,
      no_previous_year: (when) => (when ? `Vergleich mit dem Vorjahr frühestens ab ${when}` : "noch kein Vorjahr zum Vergleich"),
      too_few_days: (d) => `erst ${d} von ${NEEDS.operating_days} Betriebstagen in 30 Tagen`,
    },
    efficiency: "Wirkungsgrad",
    year: "Jahr",
    month: "Monat",
    total: "gesamt",
    boundary: { battery: "gemessen am Akku (DC)", system: "gemessen am ganzen Speicher (AC)" },
    capacity: "Kapazität (geschätzt)",
    ofDataSheet: (p, kwh) => `${p} % von ${kwh} kWh laut Datenblatt`,
    restLoss: "Ruheverlust",
    restHours: (h) => `aus ${h} Ruhestunden`,
    cyclesYear: "Vollzyklen Jahr",
    cyclesTotal: "Vollzyklen gesamt",
    warranty: "Garantie-Durchsatz",
    warrantyOf: (mwh) => `von ${mwh} MWh`,
    charged: "Geladen",
    discharged: "Entladen",
    monthsCaption: "kWh je Monat · Wirkungsgrad in % (letzte 12 Monate)",
    noMonths: "Noch keine Monatswerte.",
    editor: { device_id: "Speicher", title: "Titel (ein Leerzeichen blendet ihn aus)", sections: "Abschnitte (leer: alle)" },
  },
  en: {
    title: "Battery storage",
    describe: "Health check, efficiency, capacity, rest loss and full cycles of a battery storage, plus the last 12 months.",
    noDevice: "No Speicherwacht device found.",
    nothing: "No data for this card.",
    sections: { health: "Findings", figures: "Figures", months: "Months" },
    checks: {
      efficiency_drop: "Efficiency against last year",
      capacity_low: "Capacity",
      rest_loss_high: "Rest loss",
    },
    issues: {
      missing_entity: "Entity missing",
      source_unavailable: "Source not available",
      source_unit: "Unexpected unit",
      counter_resets: "Counter starts anew every day",
      counter_soc_mismatch: "Counters and state of charge disagree",
      own_entity: "Own sensor as source",
    },
    issueText: "See Settings → Repairs",
    fine: "fine",
    unknown: "not yet judged",
    detail: {
      efficiency_drop: {
        ok: (a, n) => `${n(a.current_percent, 1)} %, last year ${n(a.previous_year_percent, 1)} %`,
        problem: (a, n) => `${n(a.drop_points, 1)} points below last year: ${n(a.current_percent, 1)} % instead of ${n(a.previous_year_percent, 1)} %`,
      },
      capacity_low: {
        ok: (a, n) => `${n(a.share_percent, 0)} % of the data sheet`,
        low: (a, n) => `below ${n(a.end_of_life_percent, 0)} % of the data sheet: ${n(a.share_percent, 0)} %`,
        drop: (a, n) => `${n(a.drop_points, 0)} points less than a year ago: ${n(a.share_percent, 0)} % of the data sheet`,
      },
      rest_loss_high: {
        ok: (a, n) => (a.previous_year_watts !== null && a.previous_year_watts !== undefined
          ? `${n(a.watts, 0)} W, last year ${n(a.previous_year_watts, 0)} W` : `${n(a.watts, 0)} W`),
        high: (a, n) => `above ${n(a.max_watts, 0)} W: ${n(a.watts, 0)} W`,
        rise: (a, n) => `clearly above last year: ${n(a.watts, 0)} W instead of ${n(a.previous_year_watts, 0)} W`,
      },
    },
    reasons: {
      not_analysed_yet: "being calculated …",
      no_recorder: "recorder not active",
      no_data: "no counter readings in the period",
      no_soc: "no state of charge at the day boundaries",
      too_little_charge: "less than one capacity charged so far",
      too_few_rest_hours: (h) => `only ${h} of ${NEEDS.rest_hours} rest hours in 30 days`,
      soc_rose_at_rest: "state of charge rose at rest – charging past the counters?",
      too_few_discharges: (k) => `only ${k} of ${NEEDS.discharges} discharges from full to empty in 90 days`,
      no_previous_year: (when) => (when ? `comparison with last year from ${when} at the earliest` : "no previous year to compare yet"),
      too_few_days: (d) => `only ${d} of ${NEEDS.operating_days} operating days in 30 days`,
    },
    efficiency: "Efficiency",
    year: "Year",
    month: "Month",
    total: "total",
    boundary: { battery: "measured at the battery (DC)", system: "measured at the whole storage (AC)" },
    capacity: "Capacity (estimated)",
    ofDataSheet: (p, kwh) => `${p} % of ${kwh} kWh on the data sheet`,
    restLoss: "Rest loss",
    restHours: (h) => `from ${h} rest hours`,
    cyclesYear: "Full cycles year",
    cyclesTotal: "Full cycles total",
    warranty: "Warranted throughput",
    warrantyOf: (mwh) => `of ${mwh} MWh`,
    charged: "Charged",
    discharged: "Discharged",
    monthsCaption: "kWh per month · efficiency in % (last 12 months)",
    noMonths: "No monthly figures yet.",
    editor: { device_id: "Storage", title: "Title (a single space hides it)", sections: "Sections (empty: all)" },
  },
};

const ICON = "mdi:home-battery";
// Month chart: drawing width in SVG units on wide cards, and the least on
// narrow ones (card width in between: drawn at that width, see _chartWidth).
const CHART_WIDTH = 560;
const CHART_MIN_WIDTH = 280;
const COLORS = { charged: "#007D7F", discharged: "#F5A623" };

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; height: 100%; box-sizing: border-box; }
  .head { display: flex; align-items: center; gap: 8px; margin: 0 0 12px; font-size: 16px; font-weight: 500;
    color: var(--primary-text-color); }
  .head ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  section + section { margin-top: 16px; }
  .sub { font-size: 13px; font-weight: 500; color: var(--secondary-text-color); margin: 0 0 6px; }
  .row { display: flex; align-items: center; gap: 12px; padding: 6px 4px; border-radius: 8px; cursor: pointer; }
  .row:hover, .tile:hover, .hero .link:hover, .chart:hover { background: var(--secondary-background-color); }
  .dot { flex: none; width: 12px; height: 12px; border-radius: 50%; background: var(--disabled-color, #bdbdbd); }
  .dot.ok { background: var(--success-color, #43a047); }
  .dot.problem { background: var(--error-color, #db4437); }
  .dot.issue { background: var(--warning-color, #ff9800); }
  .row .name { font-weight: 500; color: var(--primary-text-color); }
  .row .text { font-size: 13px; color: var(--secondary-text-color); }
  .hero { border: 1px solid var(--divider-color); border-radius: 12px; padding: 8px 12px; margin-bottom: 8px; }
  .hero .label { font-size: 12px; color: var(--secondary-text-color); }
  .hero .line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px; }
  .hero .link { cursor: pointer; border-radius: 6px; padding: 0 4px; margin: 0 -4px; }
  .hero .big { font-size: 28px; font-weight: 500; color: var(--primary-text-color); }
  .hero .small { font-size: 14px; color: var(--primary-text-color); }
  .hero .small b { font-weight: 400; color: var(--secondary-text-color); }
  .hero .extra { font-size: 12px; color: var(--secondary-text-color); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
  .tile { border: 1px solid var(--divider-color); border-radius: 12px; padding: 8px 12px; cursor: pointer; min-width: 0; }
  .tile .label { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; }
  .tile .value { font-size: 16px; font-weight: 500; color: var(--primary-text-color); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .tile .extra { font-size: 12px; color: var(--secondary-text-color); }
  .bar { position: relative; height: 6px; border-radius: 3px; background: var(--divider-color); margin: 6px 0 2px; }
  .bar .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: ${COLORS.charged}; }
  .bar .fill.low { background: var(--error-color, #db4437); }
  .bar .mark { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--secondary-text-color); }
  .chart { border-radius: 8px; cursor: pointer; min-width: 0; }
  .chart svg { max-width: 900px; margin: 0 auto; }
  .chart .caption { font-size: 13px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 4px; }
  svg { width: 100%; height: auto; display: block; overflow: visible; }
  svg text { font-size: 10px; fill: var(--secondary-text-color); }
  svg .axis { stroke: var(--divider-color); stroke-width: 1; }
  svg .year { stroke: var(--secondary-text-color); stroke-width: 1; }
  svg rect.before { opacity: 0.4; }
  .legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--secondary-text-color); margin-top: 4px; }
  .legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 4px; vertical-align: -1px; background: var(--c); }
  .empty { color: var(--secondary-text-color); font-size: 14px; }
`;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** A round axis step (1, 2 or 5 times a power of ten) of at least `raw`. */
function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * p).find((s) => s >= raw - 1e-9);
}

/** Decimals that show an axis step exactly. */
function stepDigits(step) {
  return Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
}

// {device id: {translation key: entity id}} of Speicherwacht's storages,
// computed once per registry object.
const INDEX = new WeakMap();
function index(hass) {
  const entities = hass.entities || {};
  let found = INDEX.get(entities);
  if (!found) {
    found = {};
    for (const entry of Object.values(entities)) {
      if (entry.platform === DOMAIN && entry.device_id && entry.translation_key) {
        (found[entry.device_id] ||= {})[entry.translation_key] = entry.entity_id;
      }
    }
    INDEX.set(entities, found);
  }
  return found;
}

function storages(hass) {
  return Object.keys(index(hass));
}

// Cards on the page: re-rendered when data they wait for arrive.
const CARDS = new Set();
function renderAll() {
  for (const card of CARDS) {
    card._states = null;
    card._render();
  }
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") renderAll();
});

// Months and repair issues per device, shared by all cards on the page.
// Asked again when the monthly efficiency changed (a new analysis, hourly),
// after STALE_MS (repair issues) and after RETRY_MS on an error; never while
// the page is hidden.
const DATA = new Map();
const STALE_MS = 10 * 60 * 1000;
const RETRY_MS = 30 * 1000;
function cardData(hass, deviceId, stamp) {
  const known = DATA.get(deviceId);
  const age = known ? Date.now() - known.at : Infinity;
  const fresh = known && (known.failed ? age < RETRY_MS : known.stamp === stamp && age < STALE_MS);
  if (!fresh && !known?.loading && document.visibilityState !== "hidden") {
    DATA.set(deviceId, { ...known, loading: true });
    hass.callWS({ type: `${DOMAIN}/card`, device_id: deviceId })
      .then((result) => DATA.set(deviceId, { value: result, stamp, at: Date.now() }))
      .catch(() => DATA.set(deviceId, { value: known?.value, failed: true, stamp, at: Date.now() }))
      .finally(renderAll);
  }
  return DATA.get(deviceId)?.value;
}

class SpeicherwachtCard extends HTMLElement {
  connectedCallback() {
    CARDS.add(this);
    // The month chart is drawn in the card's width: redraw when it changes
    // (phone turned, sidebar opened, section resized).
    this._resize ||= new ResizeObserver(() => {
      if (this._drawnWidth !== undefined && this._chartWidth() !== this._drawnWidth) {
        this._states = null;
        this._render();
      }
    });
    this._resize.observe(this);
  }

  disconnectedCallback() {
    CARDS.delete(this);
    this._resize?.disconnect();
  }

  /** Width of the month chart in SVG units: the card's inner width, at most
   * CHART_WIDTH. Drawn in about real pixels, its 10 px text stays readable
   * on a phone instead of shrinking with a scaled-down drawing. */
  _chartWidth() {
    const inner = this.clientWidth - 32; // ha-card padding
    if (!(inner > 0)) return CHART_WIDTH;
    return Math.max(CHART_MIN_WIDTH, Math.min(CHART_WIDTH, Math.round(inner / 10) * 10));
  }

  setConfig(config) {
    if (config.sections !== undefined && !Array.isArray(config.sections)) {
      throw new Error("sections must be a list");
    }
    this._config = { ...config };
    this._states = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Render only when one of the card's entities (state objects are
    // replaced on every change) or the language changed.
    const ids = this._watched();
    const states = ids.map((id) => hass.states[id]);
    if (this._states && states.length === this._states.length && states.every((s, i) => s === this._states[i])
      && this._lang === hass.locale?.language) {
      return;
    }
    this._states = states;
    this._lang = hass.locale?.language;
    this._render();
  }

  getCardSize() {
    return 3 * Math.max(1, this._sections().length);
  }

  getGridOptions() {
    // Sections view: 12 columns are the section's full width.
    return { columns: "full", min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement("speicherwacht-card-editor");
  }

  static getStubConfig(hass) {
    const devices = storages(hass);
    return devices.length > 1 ? { device_id: devices[0] } : {};
  }

  _sections() {
    const wanted = this._config?.sections;
    return Array.isArray(wanted) && wanted.length ? SECTIONS.filter((s) => wanted.includes(s)) : SECTIONS;
  }

  _deviceId() {
    return this._config?.device_id || storages(this._hass)[0];
  }

  _watched() {
    if (!this._hass || !this._config) return [];
    const deviceId = this._deviceId();
    return deviceId ? Object.values(index(this._hass)[deviceId] || {}) : [];
  }

  _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return TEXT[lang] || TEXT.en;
  }

  /** Locale for numbers as the user's number format says (HA's mapping). */
  _numberLocale() {
    const locale = this._hass?.locale || {};
    return {
      comma_decimal: ["en-US", "en"],
      decimal_comma: ["de", "es", "it"],
      space_comma: ["fr", "sv", "cs"],
      system: undefined,
    }[locale.number_format] ?? locale.language ?? "en";
  }

  _num(value, digits) {
    if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "–";
    return new Intl.NumberFormat(this._numberLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
  }

  _stateOf(entityId) {
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _state(key) {
    return this._stateOf(this._entities[key]);
  }

  _known(state) {
    return Boolean(state) && !["unknown", "unavailable"].includes(state.state);
  }

  _format(state) {
    if (!this._known(state)) return "–";
    return this._hass.formatEntityState ? this._hass.formatEntityState(state)
      : `${state.state} ${state.attributes.unit_of_measurement || ""}`.trim();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (event) => {
        const path = event.composedPath();
        const repairs = path.find((el) => el.dataset && el.dataset.repairs !== undefined);
        if (repairs) {
          history.pushState(null, "", "/config/repairs");
          window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
          return;
        }
        const target = path.find((el) => el.dataset && el.dataset.entity);
        if (target) {
          this.dispatchEvent(new CustomEvent("hass-more-info", {
            detail: { entityId: target.dataset.entity }, bubbles: true, composed: true,
          }));
        }
      });
    }
    const t = this._t();
    const deviceId = this._deviceId();
    this._entities = (deviceId && index(this._hass)[deviceId]) || {};
    let body;
    if (!Object.keys(this._entities).length) {
      body = `<div class="empty">${escapeHtml(t.noDevice)}</div>`;
    } else {
      // One request per device for months and repair issues; a new monthly
      // efficiency means a new analysis.
      const sections = this._sections();
      const data = sections.some((s) => s === "health" || s === "months")
        ? cardData(this._hass, deviceId, this._state("efficiency_month")?.last_updated)
        : undefined;
      const single = sections.length === 1;
      body = sections
        .map((section) => {
          const inner = this[`_${section}`](t, data);
          if (!inner) return "";
          return single ? inner : `<section><div class="sub">${escapeHtml(t.sections[section])}</div>${inner}</section>`;
        })
        .filter(Boolean)
        .join("") || `<div class="empty">${escapeHtml(t.nothing)}</div>`;
    }
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${this._heading(t, deviceId)}${body}</ha-card>`;
  }

  _heading(t, deviceId) {
    const title = this._config.title === undefined ? undefined : String(this._config.title);
    if (title !== undefined && title !== "" && title.trim() === "") return "";
    const device = this._hass.devices?.[deviceId];
    const text = title || device?.name_by_user || device?.name || t.title;
    return `<div class="head"><ha-icon icon="${ICON}"></ha-icon>${escapeHtml(text)}</div>`;
  }

  /** The text of a reason; some name what is still missing. */
  _reason(t, reason, value) {
    const text = t.reasons[reason];
    if (typeof text === "function") return text(value);
    return text || reason || t.unknown;
  }

  // ---- Findings -----------------------------------------------------------

  _health(t, data) {
    const rows = [];
    for (const key of data?.issues || []) {
      if (!ISSUES.includes(key)) continue;
      rows.push(`<div class="row" data-repairs><div class="dot issue"></div><div>`
        + `<div class="name">${escapeHtml(t.issues[key])}</div>`
        + `<div class="text">${escapeHtml(t.issueText)}</div></div></div>`);
    }
    for (const check of CHECKS) {
      const id = this._entities[check];
      const state = this._stateOf(id);
      if (!state) continue;
      const attrs = state.attributes || {};
      let cls = "";
      let text;
      if (["on", "off"].includes(state.state) && !attrs.reason) {
        cls = state.state === "on" ? "problem" : "ok";
        text = this._finding(t, check, state.state === "on", attrs);
      } else {
        text = this._checkReason(t, check, attrs.reason);
      }
      rows.push(`<div class="row" data-entity="${escapeHtml(id)}"><div class="dot ${cls}"></div><div>`
        + `<div class="name">${escapeHtml(t.checks[check])}</div>`
        + `<div class="text">${escapeHtml(text)}</div></div></div>`);
    }
    return rows.join("");
  }

  /** "fine · 94,0 %, last year 94,3 %" or what is conspicuous. */
  _finding(t, check, problem, a) {
    const n = (v, d) => this._num(v, d);
    const texts = t.detail[check];
    let detail = "";
    try {
      if (!problem) detail = texts.ok(a, n);
      else if (check === "efficiency_drop") detail = texts.problem(a, n);
      else if (check === "capacity_low") {
        detail = a.share_percent < a.end_of_life_percent ? texts.low(a, n) : texts.drop(a, n);
      } else detail = a.watts > a.max_watts ? texts.high(a, n) : texts.rise(a, n);
    } catch (e) {
      detail = "";
    }
    if (problem) return detail || t.unknown;
    return detail ? `${t.fine} · ${detail}` : t.fine;
  }

  /** Why a check cannot judge yet, with what is still missing. */
  _checkReason(t, check, reason) {
    if (check === "efficiency_drop") {
      if (reason === "no_previous_year") return this._reason(t, reason, this._comparableFrom());
      if (reason === "too_few_days") {
        return this._reason(t, reason, this._stateOf(this._entities[check])?.attributes?.current_days ?? 0);
      }
    }
    if (check === "capacity_low" && reason === "no_estimate") {
      return this._capacityReason(t);
    }
    if (check === "rest_loss_high" && reason === "no_rest_loss") {
      return this._restReason(t);
    }
    return this._reason(t, reason);
  }

  /** Month and year from which a year of data exists, plus the 30 days the
   * comparison looks at; empty without the first day of the statistics. */
  _comparableFrom() {
    const since = this._state("efficiency_total")?.attributes?.since;
    if (!since) return "";
    const [y, m, d] = since.split("-").map(Number);
    const date = new Date(Date.UTC(y + 1, m - 1, d + 30, 12));
    return date.toLocaleDateString(this._hass.locale?.language || "en", { month: "short", year: "numeric", timeZone: "UTC" });
  }

  _capacityReason(t) {
    const a = this._state("capacity_estimate")?.attributes || {};
    if (a.reason === "too_few_discharges" || a.reason === undefined) {
      return this._reason(t, "too_few_discharges", (a.samples_kwh || []).length);
    }
    return this._reason(t, a.reason);
  }

  _restReason(t) {
    const a = this._state("rest_loss")?.attributes || {};
    if (a.reason === "too_few_rest_hours") return this._reason(t, a.reason, a.rest_hours ?? 0);
    return this._reason(t, a.reason || "too_few_rest_hours", a.rest_hours ?? 0);
  }

  // ---- Figures ------------------------------------------------------------

  _figures(t) {
    return this._hero(t) + this._grid([
      this._capacityTile(t),
      this._restTile(t),
      this._tile("full_cycles_year", t.cyclesYear),
      this._tile("full_cycles_total", t.cyclesTotal),
      this._warrantyTile(t),
    ]);
  }

  /** Efficiency: the year large, month and total beside it. */
  _hero(t) {
    const year = this._state("efficiency_year");
    if (!year) return "";
    const link = (key, label, cls) => {
      const state = this._state(key);
      if (!state) return "";
      return `<span class="link ${cls}" data-entity="${escapeHtml(this._entities[key])}">`
        + `${label ? `<b>${escapeHtml(label)}</b> ` : ""}${escapeHtml(this._format(state))}</span>`;
    };
    const reason = !this._known(year) ? this._reason(t, year.attributes?.reason) : "";
    const boundary = t.boundary[year.attributes?.boundary] || "";
    const extra = [reason, boundary].filter(Boolean).join(" · ");
    return `<div class="hero"><div class="label">${escapeHtml(`${t.efficiency} · ${t.year}`)}</div>`
      + `<div class="line">${link("efficiency_year", "", "big")}`
      + `${link("efficiency_month", t.month, "small")}${link("efficiency_total", t.total, "small")}</div>`
      + `${extra ? `<div class="extra">${escapeHtml(extra)}</div>` : ""}</div>`;
  }

  _grid(tiles) {
    const shown = tiles.filter(Boolean);
    return shown.length ? `<div class="grid">${shown.join("")}</div>` : "";
  }

  _tile(key, label, extra = "", inner = "") {
    const state = this._state(key);
    if (!state) return "";
    if (!extra && !this._known(state) && state.attributes?.reason) extra = this._reason(this._t(), state.attributes.reason);
    return `<div class="tile" data-entity="${escapeHtml(this._entities[key])}"><div class="label">${escapeHtml(label)}</div>`
      + `<div class="value">${escapeHtml(this._format(state))}</div>${inner}`
      + `${extra ? `<div class="extra">${escapeHtml(extra)}</div>` : ""}</div>`;
  }

  _bar(percent, mark, low) {
    const width = Math.max(0, Math.min(100, Number(percent) || 0));
    const marker = mark === undefined ? "" : `<div class="mark" style="left:${Math.min(100, mark)}%"></div>`;
    return `<div class="bar"><div class="fill${low ? " low" : ""}" style="width:${width}%"></div>${marker}</div>`;
  }

  _capacityTile(t) {
    const state = this._state("capacity_estimate");
    if (!state) return "";
    const a = state.attributes || {};
    if (!this._known(state)) return this._tile("capacity_estimate", t.capacity, this._capacityReason(t));
    const share = a.share_of_data_sheet_percent;
    const extra = share === null || share === undefined ? "" : t.ofDataSheet(this._num(share, 0), this._num(a.data_sheet_kwh, 1));
    const bar = share === null || share === undefined ? "" : this._bar(share, NEEDS.end_of_life, share < NEEDS.end_of_life);
    return this._tile("capacity_estimate", t.capacity, extra, bar);
  }

  _restTile(t) {
    const state = this._state("rest_loss");
    if (!state) return "";
    if (!this._known(state)) return this._tile("rest_loss", t.restLoss, this._restReason(t));
    const hours = state.attributes?.rest_hours;
    return this._tile("rest_loss", t.restLoss, hours === undefined ? "" : t.restHours(this._num(hours, 0)));
  }

  _warrantyTile(t) {
    const state = this._state("warranty_used");
    if (!state) return "";
    const a = state.attributes || {};
    const bar = this._known(state) ? this._bar(Number(state.state), undefined, false) : "";
    return this._tile("warranty_used", t.warranty, a.warranty_mwh ? t.warrantyOf(this._num(a.warranty_mwh, 0)) : "", bar);
  }

  // ---- Months -------------------------------------------------------------

  _months(t, data) {
    if (data === undefined) return `<div class="empty">…</div>`;
    const months = data?.months;
    if (!months) return `<div class="empty">${escapeHtml(this._reason(t, "not_analysed_yet"))}</div>`;
    if (!months.some((m) => m.days > 0)) return `<div class="empty">${escapeHtml(t.noMonths)}</div>`;
    return this._monthChart(t, months);
  }

  /** Charged and discharged per month side by side, the efficiency above.
   * Months of the calendar year (as the figures above) in full colour, the
   * months before paler, a thin line at 1 January. */
  _monthChart(t, months) {
    const W = this._chartWidth();
    this._drawnWidth = W;
    const H = 200;
    const L = 34;
    const B = 22;
    const T = 24;
    const high = Math.max(1, ...months.map((m) => Math.max(m.charged_kwh || 0, m.discharged_kwh || 0)));
    const step = niceStep(high / 4);
    const y1 = Math.ceil(high / step) * step;
    const y = (v) => T + (1 - v / y1) * (H - B - T);
    const slot = (W - L - 6) / months.length;
    const bar = Math.max(3, slot * 0.34);
    const lang = this._hass.locale?.language || "en";
    let grid = "";
    for (let v = 0; v <= y1 + step / 2; v += step) {
      grid += `<line class="axis" x1="${L}" x2="${W - 6}" y1="${y(v)}" y2="${y(v)}" stroke-dasharray="2 3"/>`
        + `<text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${this._num(v, stepDigits(step))}</text>`;
    }
    // The figures above are the calendar year: months before it paler.
    const year = months.at(-1).month.slice(0, 4);
    const first = months.findIndex((m) => m.month.startsWith(year));
    let bars = "";
    if (first > 0) {
      const xd = (L + first * slot).toFixed(1);
      bars += `<line class="year" x1="${xd}" x2="${xd}" y1="4" y2="${H - B}"/>`
        + `<text x="${(L + first * slot + 4).toFixed(1)}" y="12">${escapeHtml(year)}</text>`;
    }
    const names = { charged: t.charged, discharged: t.discharged };
    months.forEach((m, i) => {
      const [yy, mm] = m.month.split("-").map(Number);
      // Mid-month at noon UTC: the same month in every time zone.
      const label = new Date(Date.UTC(yy, mm - 1, 15, 12)).toLocaleDateString(lang, { month: "short", timeZone: "UTC" });
      const before = first > 0 && i < first;
      const x0 = L + i * slot + slot / 2 - bar - 1;
      [["charged", x0], ["discharged", x0 + bar + 2]].forEach(([key, left]) => {
        const v = Math.max(0, m[`${key}_kwh`] || 0);
        if (!v) return;
        bars += `<rect x="${left.toFixed(1)}" y="${y(v).toFixed(1)}" width="${bar.toFixed(1)}" height="${(y(0) - y(v)).toFixed(1)}" fill="${COLORS[key]}"${before ? ' class="before"' : ""}>`
          + `<title>${escapeHtml(label)} · ${escapeHtml(names[key])}: ${this._num(v, 0)} kWh</title></rect>`;
      });
      const top = Math.max(m.charged_kwh || 0, m.discharged_kwh || 0);
      if (m.efficiency_percent !== null && m.efficiency_percent !== undefined && top > 0) {
        bars += `<text x="${(L + i * slot + slot / 2).toFixed(1)}" y="${(y(top) - 3).toFixed(1)}" text-anchor="middle">`
          + `${this._num(m.efficiency_percent, 1)}</text>`;
      }
      bars += `<text x="${(L + i * slot + slot / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">${escapeHtml(label)}</text>`;
    });
    const legend = Object.keys(names).map((k) => `<span style="--c:${COLORS[k]}">${escapeHtml(names[k])}</span>`).join("");
    const target = this._entities.efficiency_month || this._entities.efficiency_year;
    return `<div class="chart" data-entity="${escapeHtml(target)}"><div class="caption">${escapeHtml(t.monthsCaption)}</div>`
      + `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(t.sections.months)}">${grid}${bars}</svg>`
      + `<div class="legend">${legend}</div></div>`;
  }
}

class SpeicherwachtCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const lang = (this._hass.locale?.language || "en").slice(0, 2);
    const texts = TEXT[lang] || TEXT.en;
    const devices = storages(this._hass).map((id) => {
      const entry = this._hass.devices?.[id];
      return { value: id, label: entry?.name_by_user || entry?.name || id };
    });
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        const value = { ...event.detail.value };
        for (const key of Object.keys(value)) {
          if (value[key] === "" || value[key] === null || (Array.isArray(value[key]) && !value[key].length)) delete value[key];
        }
        this._config = { type: this._config.type, ...value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.computeLabel = (schema) => texts.editor[schema.name] || schema.name;
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "device_id", selector: { select: { mode: "dropdown", options: devices } } },
      { name: "title", selector: { text: {} } },
      {
        name: "sections",
        selector: { select: { multiple: true, options: SECTIONS.map((s) => ({ value: s, label: texts.sections[s] })) } },
      },
    ];
  }
}

if (!customElements.get("speicherwacht-card")) {
  customElements.define("speicherwacht-card-editor", SpeicherwachtCardEditor);
  customElements.define("speicherwacht-card", SpeicherwachtCard);
  window.customCards = window.customCards || [];
  const texts = TEXT[(navigator.language || "en").slice(0, 2)] || TEXT.en;
  window.customCards.push({
    type: "speicherwacht-card",
    name: "Speicherwacht",
    description: texts.describe,
    preview: true,
    documentationURL: DOCS,
  });
  console.info(`%c SPEICHERWACHT %c ${CARD_VERSION} `, "color:#fff;background:#007D7F", "color:#007D7F");
}
