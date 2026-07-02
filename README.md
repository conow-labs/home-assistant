# Conow Official for Home Assistant

**Conow Official** is the official Home Assistant custom integration (domain: `conow`) for Conow / Tuya home energy users. It connects your Conow account to Home Assistant with cloud push updates, exposes standard Tuya device entities, and adds first-class support for balcony-solar / all-in-one energy devices (`xnyjcn`) via the Conow Energy Model APIs.

> **⚠️ Trial notice**
>
> Energy API endpoints used by this integration (`energy/specifications`, `energy/properties`, `energy/commands`) are currently in a **trial phase**. Each endpoint may be subject to limits on call count, frequency, and quota. Specific limits will be published progressively — please watch this repository for follow-up announcements. If you hit rate limits or quota exhaustion, wait a moment and retry.

---

## Feature Catalog

| Capability | Description | Mode |
|------------|-------------|------|
| General Tuya devices | Lights, switches, sensors, climate, cameras, and more via `tuya-device-handlers` | Read + Write |
| Energy all-in-one (`xnyjcn`) | Lyra, CBE, and similar balcony-solar devices with dynamic DP entities | Read + Write |
| Energy Model discovery | Auto-create `select` / `number` / `switch` / `time` / `sensor` from `energy/specifications` | Read + Write |
| Energy Properties sync | Pull current values from `energy/properties` on startup and refresh | Read |
| Energy Commands | Grouped parameter writes through `energy/commands` | Write |
| Custom panel | WebSocket-backed configuration panel for advanced energy device setup | Read + Write |
| Scenes | Trigger cloud scenes bound to your Conow account | Write |

---

## Routing Cheatsheet

| User intent | Where to look |
|-------------|---------------|
| "How much PV is my home generating right now?" | `sensor.*_total_photovoltaic_power`, `sensor.*_pv_power_*` on `xnyjcn` devices |
| "What is the battery doing?" | `sensor.*_battery_power`, `sensor.*_current_soc`, `select.*_charge_discharge` |
| "Switch inverter work mode / DIY settings" | `select.*_inverter_work_mode`, `number.*_diy_*` |
| "Run automation when mode changes from manual (3) to DIY (5)" | State trigger on `select.*_inverter_work_mode` from `3` to `5` |
| "Change a group of parameters at once" | Device detail energy panel, or Developer Tools → Services |
| "Control a regular Tuya device" | Standard `switch`, `light`, `climate`, etc. entities |

Reply in the user's language in automations and dashboards; entity IDs and DP codes stay as-is.

---

## Getting Started

### 1. Install

**HACS (recommended)**

1. Add this repository as a custom HACS integration source.
2. Install **Conow Official**.
3. Restart Home Assistant.

**Manual**

Copy `custom_components/conow` into your Home Assistant `config/custom_components/` directory and restart.

### 2. Configure

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Conow Official**.
3. Enter your **User Code** (Conow / Smart Life account user code).
4. Scan the QR code with the **Conow App** to authorize.
5. Wait for devices to sync.

To re-authenticate: open the integration entry → **Reconfigure**.

### 3. Prerequisites

- Home Assistant **2026.6.0** or later
- A Conow account with devices already bound in the app
- Outbound HTTPS access to Tuya cloud endpoints

Runtime Python dependencies are declared in `manifest.json`:

- `tuya-device-handlers`
- `tuya-device-sharing-sdk`

---

## Energy Devices (`xnyjcn`)

### Dynamic entities

For supported energy devices the integration:

1. Loads the device schema from `energy/specifications`.
2. Syncs live values from `energy/properties`.
3. Creates Home Assistant entities by DP type (Enum → `select`, Integer → `number`, etc.).

Entity names follow Energy Model `code` values (e.g. `work_mode`, `diy_max_power`) and support localization via `strings.json` / `translations/`.

### Enum normalization

Cloud MQTT may report the same enum DP twice:

- Semantic aliases: `manual`, `diy`, `self_powered`, …
- Protocol codes: `"3"`, `"5"`, …

The integration **normalizes wire aliases to protocol codes** before updating entity state, so `select` entities do not briefly become `unknown` and state-based automations (e.g. `from: '3'` → `to: '5'`) remain reliable.

### Automation example

```yaml
alias: Charge on DIY mode
triggers:
  - trigger: state
    entity_id: select.my_lyra_inverter_work_mode
    from: "3"
    to: "5"
actions:
  - action: select.select_option
    target:
      entity_id: select.my_lyra_charge_mode
    data:
      option: "0"
```

Prefer **state triggers** with the full `entity_id`. Device triggers must reference the correct entity registry entry.

---

## Common Pitfalls

- **Do not run both `tuya` and `conow` on the same device.** Pick one integration per device to avoid duplicate entities and conflicting state.
- **`select` flashing `unknown` on mode change** usually means enum normalization failed — update to the latest integration version and reload the entry.
- **Automation not firing on 3 → 5** — open Developer Tools → States and confirm the entity transitions directly from `3` to `5` without an intermediate `unknown`.
- **Missing entities after firmware or model change** — reload the integration to re-fetch `energy/specifications`.

---

## Project Structure

```
home-assistant/
├── LICENSE                          # MIT
├── README.md                        # This file (HACS readme)
├── hacs.json
└── custom_components/
    └── conow/                       # Conow Official integration
        ├── manifest.json            # domain: conow
        ├── config_flow.py           # QR login flow
        ├── coordinator.py           # Device listener & state dispatch
        ├── panel_functions.py       # Energy Model / Properties / Commands
        ├── panel_entity_discovery.py
        ├── energy_model_converter.py
        ├── strings.json / translations/
        └── panel/frontend/          # xnyjcn configuration panel
```

---

## Security & Data Egress

- Login tokens are stored in the Home Assistant **config entry** (encrypted at rest by HA); they are not written to logs.
- Device status and commands travel through **Tuya cloud MQTT / REST** over TLS.
- Group writes via `energy/commands` are validated before submission; only devices under the logged-in account are reachable.
- The integration does **not** log API keys, session tokens, or other credentials.

Always confirm the target device and action with the user before issuing write commands from automations or scripts.

---

## Q&A

### Energy dashboard shows **Entity not defined** after switching from the Tuya integration to Conow

**Symptom:** On **Settings → Dashboards → Energy**, the Electricity grid section shows a warning such as:

> Entity not defined — Check the integration or your configuration that provides:
> - `sensor.ke_ting_lyra_2500_pro_2_lifetime_battery_charge_energy`
> - `sensor.ke_ting_lyra_2500_pro_2_lifetime_battery_discharge_energy`

**Cause:** Energy configuration stores full `entity_id` values. When you migrate from the official **Tuya** integration (or the legacy `tuya_energy` integration) to **Conow**, entity IDs are recreated with different naming — for example, Conow uses Energy Model `code` slugs such as `stack_accumulated_charging_power` instead of Tuya translation keys such as `lifetime_battery_charge_energy`. The old IDs no longer exist, so Energy still points at orphaned entries.

**Fix:** Open the Energy configuration, remove or replace the broken entities, and **manually select the new Conow sensor entities** for the same device. Exact names depend on your device and area assignment; search in the entity picker by device name (e.g. **Lyra 2500 Pro 2**) and choose the kWh sensors with `device_class: energy`.

**Note:** If a newly added entity shows **Statistics not defined** briefly, wait up to 5 minutes after the sensor first reports a numeric value — Home Assistant generates statistics metadata on the next recorder compile cycle.

---

## License

Released under the [MIT License](./LICENSE).
