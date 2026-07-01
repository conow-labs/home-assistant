/**
 * Tuya xnyjcn custom configuration panel.
 * Loaded as a Home Assistant custom panel module.
 */

const PANEL_STYLE = `
  :host {
    display: block;
    padding: 16px;
    color: var(--primary-text-color, #e0e0e0);
    background: var(--primary-background-color, #111);
    min-height: 100%;
    box-sizing: border-box;
    font-family: var(--ha-font-family-body, Roboto, sans-serif);
  }
  h1 {
    margin: 0 0 4px;
    font-size: 1.5rem;
    font-weight: 500;
  }
  .subtitle {
    margin: 0 0 20px;
    opacity: 0.7;
    font-size: 0.9rem;
  }
  .toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }
  select, input[type="text"], input[type="number"] {
    background: var(--card-background-color, #1c1c1c);
    color: inherit;
    border: 1px solid var(--divider-color, #333);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.95rem;
    min-width: 200px;
  }
  button {
    background: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  button.secondary {
    background: transparent;
    border: 1px solid var(--divider-color, #444);
    color: inherit;
  }
  .status {
    font-size: 0.85rem;
    opacity: 0.8;
  }
  .status.offline { color: var(--error-color, #f44336); }
  .status.online { color: var(--success-color, #4caf50); }
  .group {
    background: var(--card-background-color, #1c1c1c);
    border-radius: 12px;
    margin-bottom: 16px;
    overflow: hidden;
    border: 1px solid var(--divider-color, #2a2a2a);
  }
  .group-header {
    padding: 14px 16px;
    font-weight: 600;
    font-size: 1rem;
    border-bottom: 1px solid var(--divider-color, #2a2a2a);
    background: var(--secondary-background-color, #181818);
  }
  .group-footer {
    display: flex;
    justify-content: flex-end;
    padding: 12px 16px 16px;
    border-top: 1px solid var(--divider-color, #2a2a2a);
    background: var(--secondary-background-color, #181818);
  }
  .function-row {
    display: grid;
    grid-template-columns: minmax(160px, 1fr) minmax(200px, 1.2fr);
    gap: 12px;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--divider-color, #222);
  }
  .function-row:last-child { border-bottom: none; }
  .function-label {
    font-size: 0.92rem;
    line-height: 1.35;
  }
  .function-label-btn {
    background: none;
    border: none;
    color: var(--primary-color, #03a9f4);
    padding: 0;
    text-align: left;
    cursor: pointer;
    font: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .function-label-btn:hover {
    opacity: 0.85;
  }
  .function-control {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .unit {
    opacity: 0.7;
    font-size: 0.85rem;
  }
  .switch {
    position: relative;
    width: 46px;
    height: 26px;
    display: inline-block;
  }
  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }
  .slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background: #555;
    border-radius: 26px;
    transition: 0.2s;
  }
  .slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 3px;
    bottom: 3px;
    background: white;
    border-radius: 50%;
    transition: 0.2s;
  }
  input:checked + .slider { background: var(--primary-color, #03a9f4); }
  input:checked + .slider:before { transform: translateX(20px); }
  .empty, .error, .loading {
    padding: 24px;
    text-align: center;
    opacity: 0.8;
  }
  .error { color: var(--error-color, #f44336); }
  .history-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 16px;
    box-sizing: border-box;
  }
  .history-dialog {
    width: min(520px, 100%);
    max-height: 80vh;
    overflow: auto;
    background: var(--card-background-color, #1c1c1c);
    border: 1px solid var(--divider-color, #333);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  }
  .history-dialog h2 {
    margin: 0 0 16px;
    font-size: 1.1rem;
    font-weight: 600;
  }
  .history-list {
    list-style: none;
    margin: 0 0 16px;
    padding: 0;
  }
  .history-item {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px 16px;
    padding: 10px 0;
    border-bottom: 1px solid var(--divider-color, #2a2a2a);
    font-size: 0.92rem;
  }
  .history-item:last-child { border-bottom: none; }
  .history-value {
    font-weight: 500;
    word-break: break-word;
  }
  .history-meta {
    opacity: 0.75;
    font-size: 0.82rem;
    text-align: right;
  }
  .history-empty {
    opacity: 0.75;
    padding: 12px 0 16px;
  }
  @media (max-width: 640px) {
    .function-row { grid-template-columns: 1fr; }
    .history-item { grid-template-columns: 1fr; }
    .history-meta { text-align: left; }
  }
`;

const EMBED_STYLE = `
  :host {
    padding: 0;
    min-height: auto;
    background: transparent;
  }
  .embed-toolbar {
    margin-bottom: 12px;
    padding: 0 16px;
  }
  .group:first-child {
    margin-top: 0;
  }
`;

class TuyaXnyjcnPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._deviceId = null;
    this._embedMode = false;
    this._devices = [];
    this._state = null;
    this._groupDrafts = {};
    this._loading = false;
    this._error = null;
    this._pendingGroups = new Set();
    this._historyDialog = null;
    this._styleEl = document.createElement("style");
    this._styleEl.textContent = PANEL_STYLE;
    this._root = document.createElement("div");
    this.shadowRoot.append(this._styleEl, this._root);
  }

  set deviceId(deviceId) {
    if (this._deviceId === deviceId) {
      return;
    }
    this._deviceId = deviceId || null;
    if (this._hass && this._deviceId) {
      this._loadFunctions();
    } else {
      this._render();
    }
  }

  get deviceId() {
    return this._deviceId;
  }

  set embedMode(value) {
    const embedMode = Boolean(value);
    if (this._embedMode === embedMode) {
      return;
    }
    this._embedMode = embedMode;
    this._styleEl.textContent = PANEL_STYLE + (this._embedMode ? EMBED_STYLE : "");
    this._render();
  }

  get embedMode() {
    return this._embedMode;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      if (!this._deviceId) {
        this._readDeviceFromUrl();
      }
      if (this._embedMode && this._deviceId) {
        this._loadFunctions();
      } else {
        this._loadDevices();
      }
    }
  }

  set route(route) {
    this._route = route;
    this._readDeviceFromUrl();
    if (this._hass) {
      this._loadDevices();
    }
  }

  _readDeviceFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const deviceId = params.get("device_id");
    if (deviceId) {
      this._deviceId = deviceId;
    }
  }

  async _callWS(type, extra = {}) {
    return this._hass.callWS({ type, ...extra });
  }

  _initDraftsFromState() {
    this._groupDrafts = {};
    if (!this._state?.groups) {
      return;
    }
    for (const [groupId, group] of Object.entries(this._state.groups)) {
      this._groupDrafts[groupId] = {};
      for (const fn of group.functions || []) {
        this._groupDrafts[groupId][fn.code] = fn.value;
      }
    }
  }

  _hourminToTimeInput(value) {
    if (value === null || value === undefined || value === "") {
      return "";
    }
    const encoded = Number(value);
    if (Number.isNaN(encoded)) {
      return "";
    }
    const hour = Math.floor(encoded / 100);
    const minute = encoded % 100;
    if (hour > 23 || minute > 59) {
      return "";
    }
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }

  _timeInputToHourmin(value) {
    if (!value) {
      return null;
    }
    const [hour, minute] = value.split(":").map(Number);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return null;
    }
    return hour * 100 + minute;
  }

  _isValueFilled(type, value) {
    if (type === "Boolean") {
      return value !== null && value !== undefined;
    }
    if (type === "Integer") {
      return value !== null && value !== "" && !Number.isNaN(value);
    }
    if (type === "Enum") {
      return value !== null && value !== "";
    }
    if (type === "String") {
      return value !== null && String(value).trim() !== "";
    }
    if (type === "hourmin") {
      return this._hourminToTimeInput(value) !== "";
    }
    return value !== null && value !== undefined;
  }

  _readControlValue(el, type) {
    if (type === "Boolean") {
      return el.checked;
    }
    if (type === "Integer") {
      return el.value === "" ? null : Number(el.value);
    }
    if (type === "hourmin") {
      return this._timeInputToHourmin(el.value);
    }
    return el.value;
  }

  _isGroupComplete(groupId) {
    const group = this._state?.groups?.[groupId];
    if (!group) {
      return false;
    }
    const drafts = this._groupDrafts[groupId] || {};
    return (group.functions || []).every((fn) =>
      this._isValueFilled(fn.type, drafts[fn.code])
    );
  }

  _updateGroupDraft(el) {
    const groupId = el.dataset.group;
    const code = el.dataset.code;
    const type = el.dataset.type;
    if (!groupId || !code) {
      return;
    }
    if (!this._groupDrafts[groupId]) {
      this._groupDrafts[groupId] = {};
    }
    this._groupDrafts[groupId][code] = this._readControlValue(el, type);
    this._updateGroupSubmitStates();
  }

  _updateGroupSubmitStates() {
    this._root.querySelectorAll(".group-submit").forEach((btn) => {
      const groupId = btn.dataset.groupId;
      btn.disabled =
        this._pendingGroups.has(groupId) || !this._isGroupComplete(groupId);
    });
  }

  async _loadDevices() {
    if (!this._hass) return;
    try {
      const result = await this._callWS("conow/get_panel_devices");
      this._devices = result.devices || [];
      if (!this._deviceId && this._devices.length === 1) {
        this._deviceId = this._devices[0].device_id;
      }
      if (this._deviceId) {
        await this._loadFunctions();
      } else {
        this._render();
      }
    } catch (err) {
      this._error = err.message || String(err);
      this._render();
    }
  }

  async _loadFunctions() {
    if (!this._hass || !this._deviceId) return;
    this._loading = true;
    this._error = null;
    this._render();
    try {
      this._state = await this._callWS("conow/get_panel_functions", {
        device_id: this._deviceId,
      });
      this._initDraftsFromState();
    } catch (err) {
      this._error = err.message || String(err);
      this._state = null;
      this._groupDrafts = {};
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _submitGroup(groupId) {
    if (!this._deviceId || this._pendingGroups.has(groupId)) {
      return;
    }
    const group = this._state?.groups?.[groupId];
    if (!group || !this._isGroupComplete(groupId)) {
      return;
    }

    const commands = (group.functions || []).map((fn) => ({
      code: fn.code,
      value: this._groupDrafts[groupId][fn.code],
    }));

    this._pendingGroups.add(groupId);
    this._error = null;
    this._updateGroupSubmitStates();
    try {
      this._state = await this._callWS("conow/set_panel_functions", {
        device_id: this._deviceId,
        group_id: groupId,
        commands,
      });
      this._initDraftsFromState();
    } catch (err) {
      this._error = err.message || String(err);
    } finally {
      this._pendingGroups.delete(groupId);
      this._render();
    }
  }

  _openMoreInfo(entityId) {
    if (!entityId) {
      return;
    }
    const event = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId },
    });
    this.dispatchEvent(event);
    document.querySelector("home-assistant")?.dispatchEvent(event);
  }

  async _showHistory(code, label) {
    if (!this._hass || !this._deviceId) {
      return;
    }
    this._closeHistory();
    const overlay = document.createElement("div");
    overlay.className = "history-overlay";
    overlay.innerHTML = `<div class="history-dialog"><div class="loading">Loading history…</div></div>`;
    this.shadowRoot.appendChild(overlay);
    this._historyDialog = overlay;

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        this._closeHistory();
      }
    });

    const closeBtn = () => {
      const dialog = overlay.querySelector(".history-dialog");
      if (!dialog) return;
      const footer = document.createElement("div");
      footer.style.textAlign = "right";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = "Close";
      button.addEventListener("click", () => this._closeHistory());
      footer.appendChild(button);
      dialog.appendChild(footer);
    };

    try {
      const result = await this._callWS("conow/get_panel_function_history", {
        device_id: this._deviceId,
        code,
      });
      const history = result.history || [];
      const items = history.length
        ? history
            .map(
              (item) => `
              <li class="history-item">
                <div class="history-value">${this._escape(this._formatHistoryValue(item.value))}</div>
                <div class="history-meta">${this._escape(item.source || "unknown")}<br>${this._escape(this._formatHistoryTime(item.timestamp))}</div>
              </li>
            `
            )
            .join("")
        : `<li class="history-empty">No history available.</li>`;

      overlay.querySelector(".history-dialog").innerHTML = `
        <h2>${this._escape(label || result.label || code)}</h2>
        <ul class="history-list">${items}</ul>
      `;
      closeBtn();
    } catch (err) {
      overlay.querySelector(".history-dialog").innerHTML = `
        <h2>${this._escape(label || code)}</h2>
        <div class="error">${this._escape(err.message || String(err))}</div>
      `;
      closeBtn();
    }
  }

  _closeHistory() {
    if (this._historyDialog) {
      this._historyDialog.remove();
      this._historyDialog = null;
    }
  }

  _formatHistoryValue(value) {
    if (value === null || value === undefined || value === "") {
      return "(empty)";
    }
    if (typeof value === "boolean") {
      return value ? "true" : "false";
    }
    return String(value);
  }

  _formatHistoryTime(timestamp) {
    if (!timestamp) {
      return "";
    }
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return timestamp;
    }
    return date.toLocaleString();
  }

  _onDeviceChange(event) {
    this._deviceId = event.target.value || null;
    this._state = null;
    this._groupDrafts = {};
    if (this._deviceId) {
      if (!this._embedMode) {
        const url = new URL(window.location.href);
        url.searchParams.set("device_id", this._deviceId);
        window.history.replaceState({}, "", url);
      }
      this._loadFunctions();
    } else {
      this._render();
    }
  }

  _renderBoolean(fn, groupId, value) {
    const checked = Boolean(value);
    const disabled = this._pendingGroups.has(groupId) ? "disabled" : "";
    const id = `sw-${groupId}-${fn.code}`;
    return `
      <label class="switch">
        <input type="checkbox" id="${id}" ${checked ? "checked" : ""} ${disabled}
          data-group="${groupId}" data-code="${fn.code}" data-type="Boolean" />
        <span class="slider"></span>
      </label>
    `;
  }

  _renderNumber(fn, groupId, value) {
    const spec = fn.spec || {};
    const min = spec.min !== undefined ? `min="${spec.min}"` : "";
    const max = spec.max !== undefined ? `max="${spec.max}"` : "";
    const step = spec.step !== undefined ? `step="${spec.step}"` : 'step="any"';
    const unit = spec.unit ? `<span class="unit">${spec.unit}</span>` : "";
    const val = value ?? "";
    const disabled = this._pendingGroups.has(groupId) ? "disabled" : "";
    return `
      <div class="function-control">
        <input type="number" value="${val}" ${min} ${max} ${step} ${disabled}
          data-group="${groupId}" data-code="${fn.code}" data-type="Integer" />
        ${unit}
      </div>
    `;
  }

  _renderEnum(fn, groupId, value) {
    const options = (fn.spec && fn.spec.range) || [];
    const disabled = this._pendingGroups.has(groupId) ? "disabled" : "";
    const opts = options
      .map(
        (opt) =>
          `<option value="${opt}" ${opt === value ? "selected" : ""}>${opt}</option>`
      )
      .join("");
    return `
      <select data-group="${groupId}" data-code="${fn.code}" data-type="Enum" ${disabled}>
        ${opts}
      </select>
    `;
  }

  _renderString(fn, groupId, value) {
    const maxlen = fn.spec && fn.spec.maxlen ? `maxlength="${fn.spec.maxlen}"` : "";
    const val = value ?? "";
    const disabled = this._pendingGroups.has(groupId) ? "disabled" : "";
    return `
      <input type="text" value="${this._escape(val)}" ${maxlen} ${disabled}
        data-group="${groupId}" data-code="${fn.code}" data-type="String" placeholder="" />
    `;
  }

  _renderHourmin(fn, groupId, value) {
    const val = this._hourminToTimeInput(value);
    const disabled = this._pendingGroups.has(groupId) ? "disabled" : "";
    return `
      <input type="time" value="${val}" ${disabled}
        data-group="${groupId}" data-code="${fn.code}" data-type="hourmin" />
    `;
  }

  _renderFunction(fn, groupId) {
    const draftValue =
      this._groupDrafts[groupId]?.[fn.code] !== undefined
        ? this._groupDrafts[groupId][fn.code]
        : fn.value;
    let control = "";
    switch (fn.type) {
      case "Boolean":
        control = this._renderBoolean(fn, groupId, draftValue);
        break;
      case "Integer":
        control = this._renderNumber(fn, groupId, draftValue);
        break;
      case "Enum":
        control = this._renderEnum(fn, groupId, draftValue);
        break;
      case "String":
        control = this._renderString(fn, groupId, draftValue);
        break;
      case "hourmin":
        control = this._renderHourmin(fn, groupId, draftValue);
        break;
      default:
        control = `<span class="unit">Unsupported (${fn.type})</span>`;
    }
    return `
      <div class="function-row">
        <div class="function-label">
          <button type="button" class="function-label-btn"
            data-history-code="${fn.code}"
            data-entity-id="${fn.entity_id || ""}">
            ${this._escape(fn.label)}
          </button>
        </div>
        <div class="function-control">${control}</div>
      </div>
    `;
  }

  _escape(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  _renderGroups() {
    if (!this._state || !this._state.groups) {
      return `<div class="empty">No grouped functions configured for this device.</div>`;
    }
    const groups = Object.values(this._state.groups);
    if (!groups.length) {
      return `<div class="empty">No grouped functions configured for this device.</div>`;
    }
    return groups
      .map((group) => {
        const complete = this._isGroupComplete(group.id);
        const pending = this._pendingGroups.has(group.id);
        return `
        <section class="group">
          <div class="group-header">${this._escape(group.label)}</div>
          ${(group.functions || []).map((fn) => this._renderFunction(fn, group.id)).join("")}
          <div class="group-footer">
            <button type="button" class="group-submit"
              data-group-id="${group.id}"
              ${complete && !pending ? "" : "disabled"}>
              ${pending ? "Applying…" : "Apply group"}
            </button>
          </div>
        </section>
      `;
      })
      .join("");
  }

  _bindEvents() {
    this._root.querySelectorAll("[data-group][data-code]").forEach((el) => {
      const handler = () => this._updateGroupDraft(el);
      el.addEventListener("input", handler);
      el.addEventListener("change", handler);
    });

    this._root.querySelectorAll(".group-submit").forEach((btn) => {
      btn.addEventListener("click", () => this._submitGroup(btn.dataset.groupId));
    });

    this._root.querySelectorAll("[data-history-code]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const entityId = btn.dataset.entityId;
        if (entityId) {
          this._openMoreInfo(entityId);
          return;
        }
        const code = btn.dataset.historyCode;
        const label =
          Object.values(this._state?.groups || {})
            .flatMap((group) => group.functions || [])
            .find((fn) => fn.code === code)?.label || code;
        this._showHistory(code, label);
      });
    });

    const refreshBtn = this._root.querySelector("#refresh-btn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this._loadFunctions());
    }

    const deviceSelect = this._root.querySelector("#device-select");
    if (deviceSelect) {
      deviceSelect.addEventListener("change", (ev) => this._onDeviceChange(ev));
    }
  }

  _render() {
    const deviceOptions = this._devices
      .map(
        (d) =>
          `<option value="${d.device_id}" ${
            d.device_id === this._deviceId ? "selected" : ""
          }>${this._escape(d.name)}${d.online ? "" : " (offline)"}</option>`
      )
      .join("");

    let body = "";
    if (this._loading) {
      body = `<div class="loading">Loading…</div>`;
    } else if (this._error) {
      body = `<div class="error">${this._escape(this._error)}</div>${this._state ? this._renderGroups() : ""}`;
    } else if (!this._deviceId) {
      body = `<div class="empty">Select a device to configure grouped functions.</div>`;
    } else {
      body = this._renderGroups();
    }

    const onlineClass = this._state?.online ? "online" : "offline";
    const onlineText = this._state
      ? this._state.online
        ? "Online"
        : "Offline"
      : "";

    if (this._embedMode) {
      this._root.innerHTML = `
        <div class="toolbar embed-toolbar">
          <button id="refresh-btn" class="secondary" type="button">Refresh</button>
          ${
            onlineText
              ? `<span class="status ${onlineClass}">${onlineText}</span>`
              : ""
          }
        </div>
        ${body}
      `;
    } else {
      this._root.innerHTML = `
        <h1>Tuya Device Panel</h1>
        <p class="subtitle">Dynamic grouped configuration for xnyjcn devices</p>
        <div class="toolbar">
          <select id="device-select">
            <option value="">Select device…</option>
            ${deviceOptions}
          </select>
          <button id="refresh-btn" class="secondary" type="button">Refresh</button>
          ${
            onlineText
              ? `<span class="status ${onlineClass}">${onlineText}</span>`
              : ""
          }
        </div>
        ${body}
      `;
    }
    this._bindEvents();
  }
}

customElements.define("tuya-xnyjcn-panel", TuyaXnyjcnPanel);
