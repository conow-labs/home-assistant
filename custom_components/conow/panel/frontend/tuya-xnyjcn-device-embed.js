/**
 * Inject Tuya xnyjcn grouped configuration into the device detail page.
 * Only loaded when DEVICE_PAGE_GROUPED_PANEL_ENABLED is true in panel_api.py.
 */

/** Mirror panel_api.DEVICE_PAGE_GROUPED_PANEL_ENABLED when this script is registered. */
const DEVICE_PAGE_EMBED_ENABLED = false;

const PANEL_STATIC_VERSION = "9";
const PANEL_SCRIPT = `/tuya_xnyjcn_panel_static/tuya-xnyjcn-panel.js?v=${PANEL_STATIC_VERSION}`;
const EMBED_ROOT_ID = "tuya-xnyjcn-embed-root";
const DEVICE_PATH_RE = /\/config\/devices\/device\/([^/?#]+)/;
const PANEL_MARKER = "tuya-xnyjcn-panel";

let panelScriptPromise = null;
let embedTimer = null;
let panelDeviceIds = null;
let panelDeviceIdsPromise = null;

function deepQuerySelector(selector, root = document) {
  const direct = root.querySelector?.(selector);
  if (direct) {
    return direct;
  }
  const nodes = root.querySelectorAll ? root.querySelectorAll("*") : [];
  for (const node of nodes) {
    if (node.shadowRoot) {
      const found = deepQuerySelector(selector, node.shadowRoot);
      if (found) {
        return found;
      }
    }
  }
  return null;
}

function getDevicePage() {
  return deepQuerySelector("ha-config-device-page");
}

function getHass() {
  const page = getDevicePage();
  if (page?.hass) {
    return page.hass;
  }
  return deepQuerySelector("home-assistant")?.hass;
}

function getDeviceIdFromPath() {
  const match = location.pathname.match(DEVICE_PATH_RE);
  if (match) {
    return decodeURIComponent(match[1]);
  }
  const page = getDevicePage();
  return page?.deviceId || null;
}

async function loadPanelDeviceIds(hass) {
  if (panelDeviceIds) {
    return panelDeviceIds;
  }
  if (!panelDeviceIdsPromise) {
    panelDeviceIdsPromise = hass
      .callWS({ type: "conow/get_panel_devices" })
      .then((result) => {
        panelDeviceIds = new Set(
          (result.devices || []).map((device) => device.device_id)
        );
        return panelDeviceIds;
      })
      .catch(() => {
        panelDeviceIds = new Set();
        return panelDeviceIds;
      });
  }
  return panelDeviceIdsPromise;
}

async function shouldEmbed(hass, deviceId) {
  if (!DEVICE_PAGE_EMBED_ENABLED) {
    return false;
  }
  if (!hass || !deviceId) {
    return false;
  }
  const device = hass.devices[deviceId];
  if (device?.configuration_url?.includes(PANEL_MARKER)) {
    return true;
  }
  const ids = await loadPanelDeviceIds(hass);
  return ids.has(deviceId);
}

function getEmbedRoot(page) {
  if (!page?.shadowRoot) {
    return null;
  }
  return page.shadowRoot.getElementById(EMBED_ROOT_ID);
}

function removeEmbed() {
  deepQuerySelector("ha-config-device-page")?.shadowRoot
    ?.getElementById(EMBED_ROOT_ID)
    ?.remove();
}

function loadPanelScript() {
  if (customElements.get("tuya-xnyjcn-panel")) {
    return Promise.resolve();
  }
  if (!panelScriptPromise) {
    panelScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = PANEL_SCRIPT;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () =>
        reject(new Error("Failed to load tuya-xnyjcn-panel.js"));
      document.head.appendChild(script);
    });
  }
  return panelScriptPromise;
}

function findEntitiesColumn(page) {
  const root = page.shadowRoot;
  if (!root) {
    return null;
  }
  const entitiesCard = root.querySelector("ha-device-entities-card");
  if (entitiesCard) {
    return entitiesCard.closest(".column");
  }
  const columns = root.querySelectorAll(".column");
  return columns.length >= 2 ? columns[1] : columns[0] || null;
}

async function mountEmbed(hass, deviceId, page) {
  const column = findEntitiesColumn(page);
  if (!column) {
    return false;
  }

  await loadPanelScript();

  const root = document.createElement("div");
  root.id = EMBED_ROOT_ID;
  root.dataset.deviceId = deviceId;

  const card = document.createElement("ha-card");
  card.setAttribute("outlined", "");

  const header = document.createElement("h1");
  header.className = "card-header";
  header.textContent = "Grouped configuration";

  const panel = document.createElement("tuya-xnyjcn-panel");
  panel.hass = hass;
  panel.deviceId = deviceId;
  panel.embedMode = true;

  card.appendChild(header);
  card.appendChild(panel);
  root.appendChild(card);
  column.insertBefore(root, column.firstChild);
  return true;
}

async function tryEmbed(retry = 0) {
  if (!DEVICE_PAGE_EMBED_ENABLED) {
    removeEmbed();
    return;
  }
  if (!DEVICE_PATH_RE.test(location.pathname)) {
    removeEmbed();
    return;
  }

  const deviceId = getDeviceIdFromPath();
  const page = getDevicePage();
  const hass = getHass();

  if (!page || !hass) {
    if (retry < 30) {
      window.setTimeout(() => tryEmbed(retry + 1), 200);
    }
    return;
  }

  if (!(await shouldEmbed(hass, deviceId))) {
    removeEmbed();
    if (retry === 5) {
      panelDeviceIds = null;
      panelDeviceIdsPromise = null;
    }
    if (retry < 15) {
      window.setTimeout(() => tryEmbed(retry + 1), 300);
    }
    return;
  }

  const existing = getEmbedRoot(page);
  if (existing && existing.dataset.deviceId === deviceId) {
    const panel = existing.querySelector("tuya-xnyjcn-panel");
    if (panel) {
      panel.hass = hass;
    }
    return;
  }

  removeEmbed();

  if (!findEntitiesColumn(page)) {
    if (retry < 30) {
      window.setTimeout(() => tryEmbed(retry + 1), 200);
    }
    return;
  }

  try {
    const mounted = await mountEmbed(hass, deviceId, page);
    if (!mounted && retry < 30) {
      window.setTimeout(() => tryEmbed(retry + 1), 200);
    }
  } catch (err) {
    console.warn("[tuya-xnyjcn-embed]", err);
    if (retry < 30) {
      window.setTimeout(() => tryEmbed(retry + 1), 500);
    }
  }
}

function scheduleEmbed() {
  if (!DEVICE_PAGE_EMBED_ENABLED) {
    removeEmbed();
    return;
  }
  if (embedTimer) {
    window.clearTimeout(embedTimer);
  }
  embedTimer = window.setTimeout(() => {
    if (!DEVICE_PATH_RE.test(location.pathname)) {
      panelDeviceIds = null;
      panelDeviceIdsPromise = null;
      removeEmbed();
      return;
    }
    tryEmbed(0);
  }, 100);
}

function waitForHass(callback) {
  const check = () => {
    const hass = getHass();
    if (hass) {
      callback(hass);
      return;
    }
    window.requestAnimationFrame(check);
  };
  check();
}

function init() {
  if (!DEVICE_PAGE_EMBED_ENABLED) {
    return;
  }
  window.addEventListener("location-changed", scheduleEmbed);
  window.addEventListener("popstate", scheduleEmbed);

  const observer = new MutationObserver(scheduleEmbed);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  waitForHass(() => {
    scheduleEmbed();
  });
}

window.__tuyaXnyjcnEmbed = {
  enabled: DEVICE_PAGE_EMBED_ENABLED,
  tryEmbed,
  getDevicePage,
  getDeviceIdFromPath,
  deepQuerySelector,
};

if (DEVICE_PAGE_EMBED_ENABLED) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}

export {};
