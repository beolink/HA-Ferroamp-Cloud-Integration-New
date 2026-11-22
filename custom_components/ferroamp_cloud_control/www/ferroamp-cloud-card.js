/* Ferroamp Cloud Control: the page's cards, with an explanation for every value.
 *
 * Served by the integration at /ferroamp_cloud_control/ferroamp-cloud-card.js and
 * loaded into the frontend. The page is built in Python (page_views.py) and uses two
 * cards from here, in the manner of CTC Local Easyconf's:
 *
 *   custom:ferroamp-cloud-readings   what happens right now: a small name over a big
 *                                    number, with a word for the direction of power
 *   custom:ferroamp-cloud-rows       a list of values, name on the left and value
 *                                    on the right
 *
 * Every value carries a blue "i" right after its name. It writes the explanation out
 * underneath, with where the value comes from and a way into Home Assistant's own
 * dialog for the entity. The "i" is the one toggle for its note: a button, with
 * aria-expanded and aria-controls pointing at the note. A click elsewhere on a value
 * opens Home Assistant's dialog, which is also where a control is changed: the cards
 * themselves write nothing. Every string goes into the page as text, never as HTML.
 *
 * The pure helpers at the top, formatValue and describeRule, decide what a value
 * reads as. They are loaded into node by tests/test_page.py, so the closure hands
 * them over and stops before the custom elements when there is no browser.
 */

(() => {
  const HIDDEN = new Set(["unavailable", "unknown"]);
  //: Below this many watts a power is read as standing still, whichever its sign.
  const STILL_W = 20;
  //: A charge or discharge reference this large, or a threshold this far out,
  //: means the cloud sets no limit of its own (100 000 W and -1 000 000 W seen).
  const NO_LIMIT_W = 100000;

  /* ---------------------------------------------------------- pure helpers */

  function number(value, lang, digits = 1) {
    return new Intl.NumberFormat(lang || "en", { maximumFractionDigits: digits }).format(value);
  }

  function withUnit(text, unit) {
    return unit ? `${text} ${unit}` : String(text);
  }

  const DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];

  /** An iCalendar rule ("RRULE:FREQ=WEEKLY;BYDAY=MO,TU") in the page's words:
   *  "once" without one, "every day" for a week of all seven days, the days by
   *  name for some of them, and the rule itself where it says more than that. */
  function describeRule(raw, w) {
    if (raw === undefined || raw === null || raw === "") return w.once || "once";
    const parts = {};
    for (const part of String(raw).replace(/^RRULE:/, "").split(";")) {
      const [key, value] = part.split("=");
      if (key) parts[key] = value || "";
    }
    const known = new Set(["FREQ", "BYDAY", "INTERVAL", "WKST"]);
    if (Object.keys(parts).some((key) => !known.has(key)) || (parts.INTERVAL && parts.INTERVAL !== "1")) {
      return String(raw);
    }
    const days = parts.BYDAY ? parts.BYDAY.split(",") : [];
    if (parts.FREQ === "DAILY" || (parts.FREQ === "WEEKLY" && DAYS.every((d) => days.includes(d)))) {
      return w.every_day || "every day";
    }
    if (parts.FREQ === "WEEKLY" && days.length && days.every((d) => DAYS.includes(d))) {
      const names = DAYS.filter((d) => days.includes(d)).map((d) => w[`day_${d.toLowerCase()}`] || d);
      return `${w.every_week || "every week"}: ${names.join(", ")}`;
    }
    const plain = { WEEKLY: w.every_week, MONTHLY: w.every_month, YEARLY: w.every_year }[parts.FREQ];
    return plain && !days.length ? plain : String(raw);
  }

  /** What a value reads as: [main text, word under it or null].
   *  `item` is the card's description of the value, `raw` what Home Assistant
   *  holds for it (a state, or an attribute), `unit` its unit, `words` the card's
   *  own words, `lang` the language to format numbers in, `formatTime` a function
   *  that writes a date as the user reads dates. */
  /** Ferroamp's own code ("BAT_SOC_POWER_DERATING") as words: "bat soc power derating". */
  function plainCode(code) {
    return String(code).toLowerCase().replace(/_/g, " ");
  }

  function formatValue(item, raw, unit, words, lang, formatTime, attrs) {
    const w = words || {};
    const fmt = item.format;
    const states = item.states || {};
    if (fmt === "rrule") return [describeRule(raw, w), null];
    if (fmt === "codes") {
      const codes = Array.isArray(raw) ? raw : [];
      return [codes.length ? codes.map((c) => states[c] || plainCode(c)).join(", ") : (w.none || "none"), null];
    }
    if (fmt === "alarms") {
      const alarms = Array.isArray(raw) ? raw : [];
      if (!alarms.length) return [w.no_alarms || "none", null];
      return [alarms.map((a) => {
        const when = a.since ? formatTime(new Date(a.since)) : null;
        const what = states[a.code] || plainCode(a.code);
        const head = [what, a.product_id ? `(${a.product_id})` : null].filter(Boolean).join(" ");
        return when ? `${head}, ${when}` : head;
      }).join("\n"), null];
    }
    if (fmt === "strings") {
      const strings = Array.isArray(raw) ? raw : [];
      if (!strings.length) return [w.none || "none", null];
      return [strings.map((s) => {
        const state = states[s.state] || (s.state ? plainCode(s.state) : (w.none || "none"));
        const rating = s.rating_w ? `${number(s.rating_w, lang, 0)} W` : null;
        return [`${s.name}: ${state}`, rating].filter(Boolean).join(", ");
      }).join("\n"), null];
    }
    if (fmt === "of_total") {
      const total = attrs ? attrs.total : undefined;
      if (raw === undefined || raw === null || raw === "unknown" || raw === "unavailable") {
        return [raw === "unavailable" ? (w.unavailable || "unavailable") : (w.none || "none"), null];
      }
      return [total === undefined || total === null ? String(raw) : `${raw} ${w.of || "of"} ${total}`, null];
    }
    if (raw === undefined || raw === null || raw === "" || raw === "unknown") return [w.none || "none", null];
    if (raw === "unavailable") return [w.unavailable || String(raw), null];
    if (item.states && Object.prototype.hasOwnProperty.call(item.states, String(raw))) {
      return [item.states[String(raw)], null];
    }
    if (fmt === "bool") {
      const on = raw === true || raw === "on" || raw === "true";
      return [on ? (w.yes || "Yes") : (w.no || "No"), null];
    }
    if (fmt === "time") {
      const when = new Date(raw);
      return [Number.isNaN(when.getTime()) ? String(raw) : formatTime(when), null];
    }
    const value = Number(raw);
    if (!Number.isFinite(value)) return [withUnit(String(raw), unit), null];
    if (fmt === "limit" && Math.abs(value) >= NO_LIMIT_W) return [w.no_limit || "no limit", null];
    if (fmt === "power_grid" || fmt === "power_battery") {
      const size = withUnit(number(Math.abs(value), lang, 0), unit);
      if (Math.abs(value) < STILL_W) return [withUnit(number(value, lang, 0), unit), w.still || null];
      if (fmt === "power_grid") return [size, value > 0 ? w.buying : w.selling];
      return [size, value > 0 ? w.discharging : w.charging];
    }
    const digits = fmt === "volts" ? 3 : unit === "W" || unit === "%" ? 0 : unit === "V" || unit === "A" ? 1 : 2;
    return [withUnit(number(value, lang, digits), unit), null];
  }

  if (typeof window === "undefined") {
    if (typeof module !== "undefined") module.exports = { formatValue, describeRule, plainCode };
    return;
  }

  /* ---------------------------------------------------------- the cards */

  const STYLE = `
    ha-card { padding: 12px 16px 16px; }
    .title { font-size: 1.15em; font-weight: 500; margin: 4px 0 10px; }
    .why {
      border: none; background: none; cursor: pointer; padding: 0 0 0 4px; margin: 0;
      color: var(--primary-color, #03a9f4); font-size: 1em; line-height: 1; vertical-align: baseline;
    }
    .why:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); border-radius: 4px; }
    .note {
      margin: 6px 0 10px; padding: 8px 10px; border-radius: 8px; font-size: .9em; line-height: 1.45;
      background: var(--secondary-background-color, rgba(127,127,127,.08));
      color: var(--primary-text-color);
    }
    .meta { display: block; margin-top: 6px; color: var(--secondary-text-color); font-size: .85em; }
    .meta a { color: var(--primary-color, #03a9f4); cursor: pointer; text-decoration: underline; }
    .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
    .tile {
      padding: 10px 12px; border-radius: 10px; cursor: pointer;
      background: var(--secondary-background-color, rgba(127,127,127,.06));
    }
    .tile .label { color: var(--secondary-text-color); font-size: .85em; }
    .tile .big { font-size: 1.6em; font-weight: 500; margin-top: 2px; white-space: nowrap; }
    .tile .word { color: var(--secondary-text-color); font-size: .85em; min-height: 1.2em; }
    .row {
      display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
      padding: 7px 0; border-bottom: 1px solid var(--divider-color, rgba(127,127,127,.2)); cursor: pointer;
    }
    .row:last-of-type { border-bottom: none; }
    .row .value { text-align: right; font-weight: 500; white-space: pre-line; }
    .row .value .word { color: var(--secondary-text-color); font-weight: 400; margin-left: 6px; }
  `;

  let noteIds = 0;

  function moreInfo(element, entityId) {
    element.dispatchEvent(
      new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId } })
    );
  }

  class FerroampCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._open = new Set();
      this._values = [];
    }

    setConfig(config) {
      this._config = config || {};
      this._build();
      if (this._hass) this._update();
    }

    set hass(hass) {
      this._hass = hass;
      this._update();
    }

    getCardSize() {
      return 1 + (this._config && this._config.items ? this._config.items.length : 0);
    }

    _lang() {
      const locale = this._hass && this._hass.locale;
      return (locale && locale.language) || (this._hass && this._hass.language) || "en";
    }

    _key(item) {
      return item.attribute ? `${item.entity}#${item.attribute}` : item.entity;
    }

    /** The "i" after a name, and the note it opens. */
    _explain(item, note) {
      const why = document.createElement("button");
      why.className = "why";
      why.type = "button";
      why.textContent = "ⓘ";
      why.setAttribute("aria-label", `${this._config.explain || "Explanation"}: ${item.name}`);
      note.id = `ferroamp-cloud-note-${++noteIds}`;
      why.setAttribute("aria-controls", note.id);
      why.setAttribute("aria-expanded", "false");
      why.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const open = note.hidden;
        if (open) this._open.add(this._key(item));
        else this._open.delete(this._key(item));
        this._fill(note, item, open, why);
      });
      return why;
    }

    _fill(note, item, open, why) {
      note.hidden = !open;
      why.setAttribute("aria-expanded", String(open));
      if (!open) return;
      note.replaceChildren(document.createTextNode(item.explanation || ""));
      const meta = document.createElement("span");
      meta.className = "meta";
      if (item.source) meta.append(item.source, " · ");
      const link = document.createElement("a");
      link.textContent = this._config.more_info || "More info";
      link.setAttribute("role", "button");
      link.tabIndex = 0;
      const openDialog = (event) => {
        event.preventDefault();
        event.stopPropagation();
        moreInfo(this, item.entity);
      };
      link.addEventListener("click", openDialog);
      link.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") openDialog(event);
      });
      meta.appendChild(link);
      note.appendChild(meta);
    }

    _shell() {
      const style = document.createElement("style");
      style.textContent = STYLE;
      const card = document.createElement("ha-card");
      if (this._config.title) {
        const title = document.createElement("div");
        title.className = "title";
        title.textContent = this._config.title;
        card.appendChild(title);
      }
      this.shadowRoot.replaceChildren(style, card);
      return card;
    }

    _format(item) {
      const state = this._hass && this._hass.states[item.entity];
      if (!state) return [(this._config.words || {}).unavailable || "unavailable", null];
      const raw = item.attribute ? state.attributes[item.attribute] : state.state;
      const unit = item.unit || (item.attribute ? null : state.attributes.unit_of_measurement);
      const lang = this._lang();
      const formatTime = (when) => when.toLocaleString(lang, { dateStyle: "short", timeStyle: "short" });
      // A plain entity state without words of the page's own reads as Home
      // Assistant writes it, translations and number format included.
      if (!item.attribute && !item.states && !item.format && this._hass.formatEntityState
          && !HIDDEN.has(state.state)) {
        return [this._hass.formatEntityState(state), null];
      }
      return formatValue(item, raw, unit, this._config.words, lang, formatTime, state.attributes);
    }

    _update() {
      if (!this._hass) return;
      for (const { item, value, word } of this._values) {
        const [text, extra] = this._format(item);
        if (value.textContent !== text) value.textContent = text;
        const wordText = extra || "";
        if (word && word.textContent !== wordText) word.textContent = wordText;
      }
    }
  }

  class FerroampCloudReadings extends FerroampCard {
    _build() {
      const card = this._shell();
      const tiles = document.createElement("div");
      tiles.className = "tiles";
      const notes = document.createElement("div");
      this._values = [];
      for (const item of this._config.items || []) {
        const note = document.createElement("div");
        note.className = "note";
        note.hidden = true;
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.addEventListener("click", () => moreInfo(this, item.entity));
        const label = document.createElement("div");
        label.className = "label";
        label.append(item.name);
        const why = this._explain(item, note);
        label.appendChild(why);
        const big = document.createElement("div");
        big.className = "big";
        const word = document.createElement("div");
        word.className = "word";
        tile.append(label, big, word);
        tiles.appendChild(tile);
        notes.appendChild(note);
        if (this._open.has(this._key(item))) this._fill(note, item, true, why);
        this._values.push({ item, value: big, word });
      }
      card.append(tiles, notes);
    }
  }

  class FerroampCloudRows extends FerroampCard {
    _build() {
      const card = this._shell();
      this._values = [];
      for (const item of this._config.items || []) {
        const row = document.createElement("div");
        row.className = "row";
        row.addEventListener("click", () => moreInfo(this, item.entity));
        const label = document.createElement("span");
        label.className = "label";
        label.append(item.name);
        const note = document.createElement("div");
        note.className = "note";
        note.hidden = true;
        const why = this._explain(item, note);
        label.appendChild(why);
        const value = document.createElement("span");
        value.className = "value";
        const text = document.createElement("span");
        const word = document.createElement("span");
        word.className = "word";
        value.append(text, word);
        row.append(label, value);
        card.append(row, note);
        if (this._open.has(this._key(item))) this._fill(note, item, true, why);
        this._values.push({ item, value: text, word });
      }
    }
  }

  for (const [name, card] of [
    ["ferroamp-cloud-readings", FerroampCloudReadings],
    ["ferroamp-cloud-rows", FerroampCloudRows],
  ]) {
    if (!customElements.get(name)) customElements.define(name, card);
  }
})();
