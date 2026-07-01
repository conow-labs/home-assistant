# agent-skills — Conow Open Energy Skills

`agent-skills` is a curated set of AI Agent skills built on top of the **Conow / Tuya end-user energy APIs** (the `sk-` Bearer token gateway used by Conow App). The skills let an AI Agent answer real questions about a user's home energy system — how much PV was generated, what the battery is doing right now, which device is dispatched, what the current tariff window looks like — and, where the gateway allows it, take action on a single device.

The package is structured to mirror [`tuya/tuya-openclaw-skills`](https://github.com/tuya/tuya-openclaw-skills): one folder per skill, each carrying its own `SKILL.md`, `references/`, and `scripts/`, so any one of them can be installed independently into OpenClaw / TuyaClaw or any agent runtime that consumes Anthropic-style skills.

> **⚠️ Trial notice**
>
> All open API endpoints are currently in a **trial phase**. Each endpoint is subject to limits on call count, call frequency, and quota. The specific limits will be published progressively — please watch this repository for follow-up announcements. If you run into rate-limiting or quota-exhaustion during use, wait a moment and retry.

---

## Skill Catalog

| Skill | Emoji | Scope | Mode |
|-------|-------|-------|------|
| [`conow-energy`](./conow-energy/SKILL.md) | ⚡ | Home-level energy: real-time PV / battery / grid / load flow, indicator aggregate / trend / top, hour-level forecast, tariff query/label, optimization impact, list / resolve homes | Read-only |
| [`conow-device`](./conow-device/SKILL.md) | 🔌 | Per-device queries and control. Auto-routes between Tuya generic device endpoints (`detail` / `model` / `shadow issue`) and Conow energy-device endpoints (`topo` / `protocol` / `model` / `properties` / `alarms` / `indicators` / `issue`) | Read + targeted Write |
| [`conow-dispatch`](./conow-dispatch/SKILL.md) | 🤖 | Home-level AI energy dispatch (HEMS savings mode): list dispatch status across homes, inspect schedule / `savePercent` / `deviceDispatchList`, disable on a specific home | Read + `disable` Write |

The three skills share the same authentication, the same data-center mapping, and the same routing convention so an agent can pick one of them based on the user's intent without tripping over auth differences.

Each skill also ships deep-dive references worth reading before non-trivial use: [`conow-energy/references/api_reference.md`](./conow-energy/references/api_reference.md), [`conow-device/references/device_routing.md`](./conow-device/references/device_routing.md) + [`device_control_confirm.md`](./conow-device/references/device_control_confirm.md), and [`conow-dispatch/references/dispatch_reference.md`](./conow-dispatch/references/dispatch_reference.md).

---

## Routing Cheatsheet (which skill answers which question)

| User intent | Default skill | Notes |
|-------------|---------------|-------|
| "How much did my home use today / this month?" | `conow-energy` | `indicators-aggregate` with the consumption SOL quartet. |
| "How much PV did I generate yesterday?" | `conow-energy` | `indicators-aggregate` with the produce SOL quartet. |
| "Am I importing or exporting right now?" / "What's flowing in my home?" | `conow-energy` | `conow-flow`; if real-time flow is unavailable, explain that and use aggregate data only as secondary context. |
| "What's the current tariff?" / "When is electricity cheapest tomorrow?" | `conow-energy` | `tariff-query` + `tariff-label` (+ optional `forecast`). |
| "Is the EV charger working?" / "How much is the heat pump using?" (specific device) | `conow-device` | `device-overview` after `detect` auto-routes the device. |
| "Does this device have any alarms?" | `conow-device` | `energy-alarms`. |
| "Turn on the living-room light" (generic device) | `conow-device` | `device-control` (generic `properties`) / `public-control`. |
| "Set the inverter to ..." (energy device — **inverters only**; all-in-one control is not offered) | `conow-device` | Two-step gate: `control-plan` → `control-confirm`. `energy-issue` is a low-level primitive, not the user path. |
| "Which homes are running AI dispatch right now?" | `conow-dispatch` | `list` scans all visible homes; status is three-state — **enabled** (actively dispatching), **idle** (dispatch on but `allDeviceUnable` / 0 dispatched — NOT actively saving), **disabled**. Never report an idle home as actively saving. |
| "Walk me through today's AI dispatch plan" / "Is savings mode working?" | `conow-dispatch` | `query` returns `scheduleList`, `reasonList`, `savePercent`. |
| "Disable AI dispatch on home X" | `conow-dispatch` | `disable` (only Write op in this skill). |
| "Enable AI dispatch on home X" | — | Intentionally not surfaced by this skill (not an API gap); direct the user to the Conow App to enable it. |

The same routing applies regardless of language. Reply in the user's language; never translate `home_id`, `devId`, `energyDevId`, indicator codes, or gateway error codes.

**Don't ask the user for a raw `home_id` up front.** Talk in home names — `resolve-home` / `list-homes` map a name (or substring) to its id, and a single-home account auto-resolves. Only fall back to asking for an id when a name is ambiguous or unmatched (the CLI returns `candidates[]`).

---

## Getting Started

### 1. Obtain a Conow / Tuya `sk-` API Key

These skills use the same end-user `sk-` Bearer token format as the rest of the Tuya Open Platform. Get your key from the **Conow web console** at <https://conowweb.saaszh.com/>. **The gateway base URL is auto-detected from the region prefix** — the first two characters after `sk-` map to a regional data-center URL, so you normally do not set a URL at all.

| Prefix | Region | REST API Base URL |
|--------|--------|-------------------|
| `sk-AY` | China | `https://openapi.tuyacn.com` |
| `sk-AZ` | US West | `https://openapi.tuyaus.com` |
| `sk-EU` | Central Europe | `https://openapi.tuyaeu.com` |
| `sk-IN` | India | `https://openapi.tuyain.com` |
| `sk-UE` | US East | `https://openapi-ueaz.tuyaus.com` |
| `sk-WE` | Western Europe | `https://openapi-weaz.tuyaeu.com` |
| `sk-SG` | Singapore | `https://openapi-sg.iotbing.com` |

Set `CONOW_BASE_URL` only if your deployment provides a dedicated gateway URL; when set, it **overrides** the auto-detected region URL.

### 2. Configure environment

```bash
export CONOW_API_KEY="sk-..."           # Required — base URL is auto-detected from the prefix
# Optional overrides
export CONOW_BASE_URL="https://openapi.tuyaeu.com"   # Overrides the auto-detected region URL
export CONOW_HOME_ID="<home_id>"        # Default home_id for conow-energy / conow-dispatch (the conow-device CLI does NOT read this)
export CONOW_DEVICE_ID="<dev_id>"       # Default devId for conow-device commands
export CONOW_VERBOSE=1                  # Print a redacted request summary to stderr (debugging)
```

The skills refuse to load if `CONOW_API_KEY` is missing. The CLIs **never** echo the raw key.

### 3. Verify your setup

Run the no-argument discovery command first — it confirms your key works and your base URL is reachable:

```bash
python3 conow-energy/scripts/conow_cli.py list-homes
```

If it returns a list of homes, you are set. Copy a `home_id` from the output and, optionally, export it as the default so you can drop `--home-id` from later commands:

```bash
export CONOW_HOME_ID="<home_id from list-homes>"
```

### 4. Prerequisites

- Python 3.7+

No third-party Python dependency is required. Each skill ships a self-contained CLI under `scripts/`.

### 5. Install into OpenClaw / TuyaClaw

Each subfolder is a standalone OpenClaw skill — drop `conow-energy/`, `conow-device/`, and/or `conow-dispatch/` into your skill registry, set `CONOW_API_KEY` in the skill configuration, and the metadata block in each `SKILL.md` will pick the right emoji, declare the required env var, and route prompts.

---

## Quick Examples

> Run these from the **repository root** — the examples use relative `python3 conow-energy/scripts/...` paths that will not resolve from another directory.

```bash
# === Start here: no-argument discovery ===
python3 conow-energy/scripts/conow_cli.py list-homes        # returns your homes (no args)
python3 conow-dispatch/scripts/conow_dispatch_cli.py list   # AI dispatch status across all homes

# === conow-energy ===
python3 conow-energy/scripts/conow_cli.py resolve-home --home-name "My Home"
# An ambiguous or unknown name is a normal result: prints {"success":false,...,"candidates":[...]} and exits 0.
python3 conow-energy/scripts/conow_cli.py conow-flow --home-id <home_id>
python3 conow-energy/scripts/conow_cli.py indicators-aggregate \
  --home-id <home_id> \
  --date-type day --begin-date 20260421 --end-date 20260421 \
  --indicator-code ele_consumption_sol,ele_consumption_from_pv_sol,ele_consumption_from_battery_sol,ele_consumption_from_grid_sol \
  --time-aggr-type sum
python3 conow-energy/scripts/conow_cli.py forecast --home-id <home_id> \
  --begin-date <yyyyMMddHH, current hour or later> --end-date <same window, up to +48h>

# === conow-device ===
python3 conow-device/scripts/conow_device_cli.py detect --dev-id <DEV_ID>
python3 conow-device/scripts/conow_device_cli.py device-overview --dev-id <DEV_ID>

# Generic device control (lights, sockets, ...):
python3 conow-device/scripts/conow_device_cli.py device-control \
  --dev-id <SOCKET_DEV_ID> --properties '{"switch_led": true}'

# Energy-device control is a two-step gate (control-plan validates, control-confirm writes):
python3 conow-device/scripts/conow_device_cli.py control-plan \
  --dev-id <INVERTER_DEV_ID> --properties '{"inverter_work_mode_setting":"1"}'   # ready=true -> prints a plan_hash, exit 0
python3 conow-device/scripts/conow_device_cli.py control-confirm \
  --dev-id <INVERTER_DEV_ID> --properties '{"inverter_work_mode_setting":"1"}' --plan-hash <PLAN_HASH>

# === conow-dispatch ===
python3 conow-dispatch/scripts/conow_dispatch_cli.py query --home-id <home_id>
python3 conow-dispatch/scripts/conow_dispatch_cli.py disable --home-id <home_id>
```

Use `--help` on any CLI for the full command list.

---

## Exit Codes

- **`0` = success; non-zero = failure.** Branch on "non-zero means failure" — do not hard-code specific values.
- Failure codes are not yet unified across the CLIs: `conow-energy` returns **`2`** on a business / gateway error; `conow-device` and `conow-dispatch` return **`1`**. A missing `CONOW_API_KEY` exits **`2`** in all three.
- `resolve-home`'s "ambiguous / not found" is a normal result, not a failure. `conow-energy`'s `resolve-home` exits **`0`** with the options in `candidates[]`; `conow-device`'s `resolve-home` exits **`1`** in that case (its `candidates[]` still come back in the printed payload — read it rather than branching on the exit code alone).
- `control-plan` exits **`1`** and emits no `plan_hash` when `ready=false`; do not proceed to `control-confirm`.

---

## Output Contract

- Data goes to **stdout** (JSON by default); friendly hints and error messages go to **stderr**.
- Even when the gateway returns `success:false`, the CLI **prints the full payload first** (including `code` / `msg`) to stdout, then exits non-zero.
- Judge success by both the exit code **and** `payload.success`; when surfacing an error, pass the raw `code` / `msg` through to the user.

---

## Common Pitfalls

- **No `week` granularity.** `--date-type` is `quarter / hour / day / month / year`. For a weekly total, use `day` across the 7-day range with `--time-aggr-type sum`.
- **`forecast` is narrow.** Hour granularity only (`yyyyMMddHH`), window ≤ 48h, anchored at the current hour or later, at most 2 codes (`ele_forecast_produce` / `ele_forecast_consumption`). Outside these bounds the raw gateway silently returns an empty `list[]` with `success:true`; the bundled CLI rejects > 48h windows, > 2 codes, and out-of-whitelist codes locally with a non-zero exit before the call (override via `--allow-long-window` / `--allow-any-code`). A **past anchor is not caught locally** — it still reaches the gateway and silently returns an empty list, so anchor `begin_date` at the current hour or later yourself.
- **`conow-impact --phone-code` is an ISO 3166 alpha-2 country code** (e.g. `CN` / `DE`) and is **not validated.** Passing a phone dial code (`86`) or an alpha-3 code (`CHN`) silently yields wrong carbon figures with no error. Do not copy `conow-station`'s `country_code` straight in — it is not guaranteed to be alpha-2.

See [`conow-energy/references/api_reference.md`](./conow-energy/references/api_reference.md) for the full field-level contract.

---

## Project Structure

```
agent-skills/
├── README.md                          # English overview (this file)
├── LICENSE                            # MIT
├── conow-energy/                      # Home-level energy skill (read-only)
│   ├── SKILL.md
│   ├── references/
│   │   ├── api_reference.md
│   │   └── skill_manifest.md
│   └── scripts/
│       └── conow_cli.py
├── conow-device/                      # Per-device skill (auto-routed read + write)
│   ├── SKILL.md
│   ├── references/
│   │   ├── device_routing.md
│   │   └── device_control_confirm.md
│   └── scripts/
│       └── conow_device_cli.py
└── conow-dispatch/                    # Home AI dispatch skill (read + disable)
    ├── SKILL.md
    ├── references/
    │   └── dispatch_reference.md
    └── scripts/
        └── conow_dispatch_cli.py
```

---

## Security & Data Egress

All three skills send the `sk-` Bearer token, the `home_id` / `devId` you reference, and the request parameters you pass to the configured base URL. The `conow-device` skill additionally sends control payloads (generic `properties` via `device-control` / `public-control`, or energy `setting` via the `control-plan` → `control-confirm` gate) when you invoke a write command; `conow-dispatch` sends a `disable` body to turn off AI dispatch on a specified home.

- **No raw keys in output.** Every CLI avoids printing the raw `CONOW_API_KEY`.
- **No runtime cache committed.** `scripts/.home_cache.json`, when generated, lives only on the local machine and is excluded by `.gitignore`.
- **Confirm before write.** Always confirm the target `home_id` / `devId` with the user before issuing a write. For generic devices that is `device-control` / `public-control`; for energy devices use the two-step gate `control-plan` (read-only preview, produces a `plan_hash`) → `control-confirm` (writes only when the `plan_hash` and settings match). `dispatch disable` is the only write in `conow-dispatch`.

---

## License

Released under the [MIT License](./LICENSE).
