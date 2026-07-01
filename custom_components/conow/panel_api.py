"""WebSocket API and custom panel for Tuya xnyjcn device configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.frontend import (
    add_extra_js_url,
    async_panel_exists,
    remove_extra_js_url,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER
from .panel_functions import (
    DYNAMIC_PANEL_CATEGORIES,
    apply_function_group_via_api,
    build_panel_state,
    ensure_device_energy_schema,
    ensure_panel_energy_properties,
    fetch_function_history_from_api,
    notify_panel_commands_applied,
    validate_group_commands,
)
from .services import _get_tuya_device

URL_BASE = "/tuya_xnyjcn_panel_static"
PANEL_URL_PATH = "tuya-xnyjcn-panel"
PANEL_WEBCOMPONENT = "tuya-xnyjcn-panel"
PANEL_STATIC_VERSION = "9"
# Grouped configuration card on the HA device detail page (UI only).
DEVICE_PAGE_GROUPED_PANEL_ENABLED = False
# Sidebar "Tuya Device Panel" menu entry.
PANEL_SIDEBAR_ENABLED = False
EMBED_SCRIPT_URL = (
    f"{URL_BASE}/tuya-xnyjcn-device-embed.js?v={PANEL_STATIC_VERSION}"
)
LEGACY_WS_DOMAIN = "tuya"

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("code"): str,
        vol.Required("value"): vol.Any(bool, int, float, str, None),
    }
)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_panel_devices"})
@websocket_api.async_response
async def websocket_get_panel_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return xnyjcn devices available for the custom configuration panel."""
    device_registry = dr.async_get(hass)
    devices: list[dict[str, Any]] = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        manager = entry.runtime_data.manager
        for device in manager.device_map.values():
            if device.category not in DYNAMIC_PANEL_CATEGORIES:
                continue
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, device.id)}
            )
            if device_entry is None:
                continue
            devices.append(
                {
                    "device_id": device_entry.id,
                    "tuya_device_id": device.id,
                    "name": device.name,
                    "online": device.online,
                }
            )
    connection.send_result(msg["id"], {"devices": devices})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_panel_functions",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def websocket_get_panel_functions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return grouped panel functions and current values for a device."""
    try:
        device, manager = _get_tuya_device(hass, msg["device_id"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    await ensure_device_energy_schema(hass, manager, device)
    await ensure_panel_energy_properties(hass, manager, device)
    connection.send_result(msg["id"], build_panel_state(hass, device))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_panel_function_history",
        vol.Required("device_id"): str,
        vol.Required("code"): str,
    }
)
@websocket_api.async_response
async def websocket_get_panel_function_history(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return change history for a grouped panel function."""
    try:
        device, manager = _get_tuya_device(hass, msg["device_id"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    code = msg["code"]
    await ensure_device_energy_schema(hass, manager, device)
    allowed_codes = {
        function.code
        for functions in device.function_groups.values()
        for function in functions
    }
    if code not in allowed_codes:
        connection.send_error(
            msg["id"], "invalid_code", f"Function {code} is not in the panel schema"
        )
        return

    history = await fetch_function_history_from_api(hass, manager, device, code)
    connection.send_result(
        msg["id"],
        {
            "code": code,
            "label": code.replace("_", " ").title(),
            "history": history,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_panel_functions",
        vol.Required("device_id"): str,
        vol.Required("group_id"): str,
        vol.Required("commands"): [COMMAND_SCHEMA],
    }
)
@websocket_api.async_response
async def websocket_set_panel_functions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Set all grouped panel functions in a group on a device."""
    try:
        device, manager = _get_tuya_device(hass, msg["device_id"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    group_id = msg["group_id"]
    commands = msg["commands"]
    await ensure_device_energy_schema(hass, manager, device)
    try:
        validate_group_commands(device, group_id, commands)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_command", str(err))
        return

    try:
        await apply_function_group_via_api(
            hass, manager, device, group_id, commands
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "apply_failed", str(err))
        return

    notify_panel_commands_applied(hass, device, commands)
    connection.send_result(msg["id"], build_panel_state(hass, device))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{LEGACY_WS_DOMAIN}/get_panel_devices"}
)
@websocket_api.websocket_command(
    {vol.Required("type"): "tuya_energy/get_panel_devices"}
)
@websocket_api.async_response
async def websocket_get_panel_devices_legacy(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Legacy alias for cached frontend builds."""
    await websocket_get_panel_devices(hass, connection, msg)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{LEGACY_WS_DOMAIN}/get_panel_functions",
        vol.Required("device_id"): str,
    }
)
@websocket_api.websocket_command(
    {
        vol.Required("type"): "tuya_energy/get_panel_functions",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def websocket_get_panel_functions_legacy(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Legacy alias for cached frontend builds."""
    await websocket_get_panel_functions(hass, connection, msg)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{LEGACY_WS_DOMAIN}/get_panel_function_history",
        vol.Required("device_id"): str,
        vol.Required("code"): str,
    }
)
@websocket_api.websocket_command(
    {
        vol.Required("type"): "tuya_energy/get_panel_function_history",
        vol.Required("device_id"): str,
        vol.Required("code"): str,
    }
)
@websocket_api.async_response
async def websocket_get_panel_function_history_legacy(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Legacy alias for cached frontend builds."""
    await websocket_get_panel_function_history(hass, connection, msg)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{LEGACY_WS_DOMAIN}/set_panel_functions",
        vol.Required("device_id"): str,
        vol.Required("group_id"): str,
        vol.Required("commands"): [COMMAND_SCHEMA],
    }
)
@websocket_api.websocket_command(
    {
        vol.Required("type"): "tuya_energy/set_panel_functions",
        vol.Required("device_id"): str,
        vol.Required("group_id"): str,
        vol.Required("commands"): [COMMAND_SCHEMA],
    }
)
@websocket_api.async_response
async def websocket_set_panel_functions_legacy(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Legacy alias for cached frontend builds."""
    await websocket_set_panel_functions(hass, connection, msg)


@callback
def _register_websocket_api(hass: HomeAssistant) -> None:
    """Register panel websocket commands."""
    for handler in (
        websocket_get_panel_devices,
        websocket_get_panel_devices_legacy,
        websocket_get_panel_functions,
        websocket_get_panel_functions_legacy,
        websocket_get_panel_function_history,
        websocket_get_panel_function_history_legacy,
        websocket_set_panel_functions,
        websocket_set_panel_functions_legacy,
    ):
        websocket_api.async_register_command(hass, handler)


async def async_register_tuya_panel(hass: HomeAssistant) -> None:
    """Register the xnyjcn custom configuration panel and websocket API."""
    if not hass.data.get(f"{DOMAIN}_panel_ws_registered"):
        _register_websocket_api(hass)
        hass.data[f"{DOMAIN}_panel_ws_registered"] = True

    frontend_dir = Path(__file__).parent / "panel" / "frontend"
    if not hass.data.get(f"{DOMAIN}_panel_static_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, str(frontend_dir), cache_headers=False)]
        )
        hass.data[f"{DOMAIN}_panel_static_registered"] = True

    if DEVICE_PAGE_GROUPED_PANEL_ENABLED:
        add_extra_js_url(hass, EMBED_SCRIPT_URL, es5=True)
        for legacy_version in ("6", "7", "8"):
            remove_extra_js_url(
                hass,
                f"{URL_BASE}/tuya-xnyjcn-device-embed.js?v={legacy_version}",
            )
    else:
        remove_extra_js_url(hass, EMBED_SCRIPT_URL, es5=True)
        for legacy_version in ("6", "7", "8"):
            remove_extra_js_url(
                hass,
                f"{URL_BASE}/tuya-xnyjcn-device-embed.js?v={legacy_version}",
                es5=True,
            )

    if hass.data.get(f"{DOMAIN}_panel_registered"):
        return

    if PANEL_SIDEBAR_ENABLED and not async_panel_exists(hass, PANEL_URL_PATH):
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_WEBCOMPONENT,
            config_panel_domain=DOMAIN,
            module_url=f"{URL_BASE}/tuya-xnyjcn-panel.js?v={PANEL_STATIC_VERSION}",
            sidebar_title="Tuya Device Panel",
            sidebar_icon="mdi:solar-power",
            embed_iframe=False,
            require_admin=False,
        )

    hass.data[f"{DOMAIN}_panel_registered"] = True


def get_panel_configuration_url(ha_device_id: str) -> str:
    """Build the configuration panel URL for a device registry entry."""
    return f"homeassistant://{PANEL_URL_PATH}?device_id={ha_device_id}"
