"""Dynamic grouped panel functions for Tuya devices."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceFunction, DeviceStatusRange
from tuya_sharing.exceptions import ApiRequestException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER
from .energy_model_converter import (
    build_panel_enum_code_maps,
    build_panel_enum_wire_to_code_maps,
    extract_energy_model_entries,
    parse_energy_properties_response,
    parse_energy_specifications_response,
)
from .hourmin import hourmin_to_time

DYNAMIC_PANEL_CATEGORIES = frozenset({"xnyjcn"})
PANEL_FUNCTIONS_MOCK_DIR = "mock"
PANEL_FUNCTIONS_MOCK_FILE = "tuya_panel_functions.json"
USE_MOCK_PANEL_FUNCTIONS = False
SPECIFICATIONS_API_PATH = "/v1.0/m/life/ha/{device_id}/energy/specifications"
PROPERTIES_API_PATH = "/v1.0/m/life/ha/{device_id}/energy/properties"
COMMANDS_API_PATH = "/v1.0/m/life/ha/{device_id}/energy/commands"

TYPE_PLATFORM_MAP = {
    "Boolean": "switch",
    "Integer": "number",
    "Enum": "select",
    "String": "text",
    "hourmin": "time",
}


def format_group_label(group_id: str) -> str:
    """Return a human-readable group label."""
    if group_id.startswith("group") and group_id[5:].isdigit():
        return f"Group {group_id[5:]}"
    if group_id.isdigit():
        return f"Group {group_id}"
    return group_id.replace("_", " ").title()


def format_function_label(function) -> str:
    """Return a human-readable function label."""
    if name := getattr(function, "name", None):
        return name
    return function.code.replace("_", " ").title()


def parse_function_spec(function) -> dict[str, Any]:
    """Parse a DeviceFunction values JSON string into a dict."""
    if not function.values:
        return {}
    try:
        parsed = json.loads(function.values)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def is_value_filled(value_type: str, value: Any) -> bool:
    """Return whether a panel value is considered non-empty for group submit."""
    if value_type == "Boolean":
        return value is not None
    if value_type == "Integer":
        return value is not None and value != ""
    if value_type == "Enum":
        return value is not None and value != ""
    if value_type == "String":
        return value is not None and str(value).strip() != ""
    if value_type == "hourmin":
        return hourmin_to_time(value) is not None
    return value is not None


def build_panel_state(hass: HomeAssistant, device: CustomerDevice) -> dict[str, Any]:
    """Serialize grouped panel functions and current values for the frontend."""
    from .panel_entity_discovery import resolve_entity_id_for_function

    groups: dict[str, Any] = {}
    for group_id, functions in sorted(
        getattr(device, "function_groups", {}).items()
    ):
        items: list[dict[str, Any]] = []
        for function in functions:
            if function.type not in TYPE_PLATFORM_MAP:
                continue
            items.append(
                {
                    "code": function.code,
                    "type": function.type,
                    "label": format_function_label(function),
                    "value": device.status.get(function.code),
                    "spec": parse_function_spec(function),
                    "entity_id": resolve_entity_id_for_function(
                        hass, device, function
                    ),
                }
            )
        groups[group_id] = {
            "id": group_id,
            "label": format_group_label(group_id),
            "functions": items,
        }
    return {
        "tuya_device_id": device.id,
        "name": device.name,
        "online": device.online,
        "category": device.category,
        "groups": groups,
    }


def normalize_function_groups_payload(
    grouped_functions: Any,
) -> dict[str, list[dict[str, Any]]] | None:
    """Normalize function-groups payload to {group_id: [functions]}.

    Supports a flat list (wrapped as group ``1``) or a grouped dict.
    """
    if isinstance(grouped_functions, list):
        functions = [
            item for item in grouped_functions if isinstance(item, dict) and "code" in item
        ]
        if not functions:
            return None
        return {"1": functions}

    if isinstance(grouped_functions, dict):
        normalized: dict[str, list[dict[str, Any]]] = {}
        for group_id, functions in grouped_functions.items():
            if not isinstance(functions, list):
                continue
            items = [
                item for item in functions if isinstance(item, dict) and "code" in item
            ]
            if items:
                normalized[str(group_id)] = items
        return normalized or None

    return None


def apply_specifications(
    device: CustomerDevice, specifications: dict[str, Any]
) -> None:
    """Merge instruction-set specifications into device.function and status_range."""
    for function in specifications.get("functions", []):
        if not isinstance(function, dict) or "code" not in function:
            continue
        code = function["code"]
        existing = device.function.get(code)
        if existing is not None:
            merged = DeviceFunction(**{**existing.__dict__, **function})
        else:
            merged = DeviceFunction(**function)
        device.function[code] = merged

    for status in specifications.get("status", []):
        if not isinstance(status, dict) or "code" not in status:
            continue
        code = status["code"]
        existing = device.status_range.get(code)
        if existing is not None:
            merged = DeviceStatusRange(**{**existing.__dict__, **status})
        else:
            merged = DeviceStatusRange(**status)
        device.status_range[code] = merged


def _apply_function_groups(
    device: CustomerDevice, grouped_functions: dict[str, Any]
) -> None:
    """Apply grouped function definitions to a device."""
    function_groups: dict[str, list[DeviceFunction]] = {}
    for group_id, functions in grouped_functions.items():
        if not isinstance(functions, list):
            continue
        group_list: list[DeviceFunction] = []
        for function in functions:
            if not isinstance(function, dict) or "code" not in function:
                continue
            code = function["code"]
            existing = device.function.get(code)
            if existing is not None:
                merged = DeviceFunction(**{**existing.__dict__, **function})
            else:
                merged = DeviceFunction(**function)

            device.function[code] = merged
            status_payload = {
                "code": code,
                "type": merged.type,
                "values": merged.values or "{}",
            }
            existing_status = device.status_range.get(code)
            if existing_status is not None:
                device.status_range[code] = DeviceStatusRange(
                    **{**existing_status.__dict__, **status_payload}
                )
            else:
                device.status_range[code] = DeviceStatusRange(**status_payload)
            group_list.append(merged)
        if group_list:
            function_groups[group_id] = group_list
    device.function_groups = function_groups


def apply_panel_status_entities(
    device: CustomerDevice, status_entities: list[dict[str, Any]]
) -> None:
    """Merge read-only status schema entries into device.status_range only."""
    for entry in status_entities:
        code = str(entry["code"])
        dp_type = str(entry["type"])
        values = entry.get("values", "{}")

        existing_status = device.status_range.get(code)
        status_payload = {"code": code, "type": dp_type, "values": values}
        if existing_status is not None:
            merged_status = DeviceStatusRange(
                **{**existing_status.__dict__, **status_payload}
            )
        else:
            merged_status = DeviceStatusRange(**status_payload)
        device.status_range[code] = merged_status


def normalize_status_entities(raw: Any) -> list[dict[str, Any]]:
    """Normalize status entity schema entries from API or mock payload."""
    if not isinstance(raw, list):
        return []
    return [
        item
        for item in raw
        if isinstance(item, dict) and item.get("code") and item.get("type")
    ]


def set_device_panel_status_entities(
    device: CustomerDevice, status_entities: list[dict[str, Any]]
) -> None:
    """Store and apply read-only status entity schema on a device."""
    normalized = normalize_status_entities(status_entities)
    device.panel_status_entities = normalized
    if normalized:
        apply_panel_status_entities(device, normalized)


def _get_mock_panel_functions_path() -> Path:
    """Return bundled panel functions mock path."""
    return Path(__file__).parent / PANEL_FUNCTIONS_MOCK_DIR / PANEL_FUNCTIONS_MOCK_FILE


def _read_mock_panel_file(
    mock_path: Path, category: str
) -> dict[str, Any] | None:
    """Read panel mock schema from local file (executor-safe)."""
    if not mock_path.is_file():
        return None

    try:
        data = json.loads(mock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if data.get("category") and data["category"] != category:
        return None

    return {
        "functions": normalize_function_groups_payload(data.get("functions")),
        "status": normalize_status_entities(data.get("status")),
    }


async def _load_mock_panel_schema(
    hass: HomeAssistant, device: CustomerDevice
) -> dict[str, Any] | None:
    """Load panel function groups and status entities from local mock file."""
    mock_path = _get_mock_panel_functions_path()
    mock_schema = await hass.async_add_executor_job(
        _read_mock_panel_file, mock_path, device.category
    )
    if mock_schema is None:
        LOGGER.debug(
            "No panel mock for device %s (file missing or invalid: %s)",
            device.id,
            mock_path,
        )
    return mock_schema


def _flatten_grouped_functions(
    grouped_functions: dict[str, list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    """Flatten grouped panel functions into a single list."""
    if not grouped_functions:
        return []
    flat: list[dict[str, Any]] = []
    for functions in grouped_functions.values():
        flat.extend(functions)
    return flat


async def _apply_mock_energy_schema(
    hass: HomeAssistant, device: CustomerDevice
) -> None:
    """Load panel schema from local mock without calling cloud API."""
    mock_schema = await _load_mock_panel_schema(hass, device)
    if mock_schema is None:
        LOGGER.warning(
            "Panel mock unavailable for device %s, skipping energy schema",
            device.id,
        )
        device.function_groups = {}
        return

    grouped_functions = mock_schema.get("functions")
    status_entities = mock_schema.get("status") or []
    spec_doc = {
        "category": device.category,
        "functions": _flatten_grouped_functions(grouped_functions),
        "status": status_entities,
    }
    apply_specifications(device, spec_doc)
    set_device_panel_status_entities(device, status_entities)

    if grouped_functions:
        _apply_function_groups(device, grouped_functions)
    else:
        device.function_groups = {}

    from .panel_entity_discovery import restrict_device_functions_to_panel

    restrict_device_functions_to_panel(device)

    LOGGER.debug(
        "Loaded mock energy schema for device %s: %d functions, %d status, "
        "%d panel groups from %s",
        device.id,
        len(spec_doc["functions"]),
        len(status_entities),
        len(device.function_groups),
        PANEL_FUNCTIONS_MOCK_FILE,
    )


async def _fetch_energy_specifications(
    hass: HomeAssistant, manager: Manager, device_id: str
) -> dict[str, Any] | None:
    """Fetch energy specifications from cloud API."""
    api_path = SPECIFICATIONS_API_PATH.format(device_id=device_id)
    LOGGER.debug("Fetching energy specifications from %s", api_path)
    try:
        response = await hass.async_add_executor_job(
            manager.customer_api.get, api_path
        )
    except ApiRequestException as err:
        LOGGER.warning(
            "Energy specifications API failed for device %s: %s", device_id, err
        )
        return None
    if not response.get("success"):
        LOGGER.warning(
            "Failed to fetch energy specifications for device %s", device_id
        )
        return None
    return response


async def ensure_device_energy_schema(
    hass: HomeAssistant, manager: Manager, device: CustomerDevice
) -> None:
    """Load energy specifications and panel groups from cloud API."""
    if device.category not in DYNAMIC_PANEL_CATEGORIES:
        return

    if USE_MOCK_PANEL_FUNCTIONS:
        await _apply_mock_energy_schema(hass, device)
        return

    response = await _fetch_energy_specifications(hass, manager, device.id)
    if response is None:
        device.function_groups = {}
        return

    parsed = parse_energy_specifications_response(
        response.get("result"),
        category=device.category,
    )
    if parsed is None:
        LOGGER.warning(
            "Invalid energy specifications payload for device %s", device.id
        )
        device.function_groups = {}
        return

    spec_doc, panel_functions = parsed
    model_entries = extract_energy_model_entries(response.get("result"))
    device.panel_enum_code_maps = (
        build_panel_enum_code_maps(model_entries) if model_entries else {}
    )
    device.panel_enum_wire_to_code_maps = (
        build_panel_enum_wire_to_code_maps(model_entries, spec_doc)
        if model_entries
        else {}
    )
    apply_specifications(device, spec_doc)
    set_device_panel_status_entities(device, spec_doc.get("status", []))

    grouped_functions = normalize_function_groups_payload(panel_functions)
    panel_source = SPECIFICATIONS_API_PATH.format(device_id=device.id)

    if grouped_functions:
        _apply_function_groups(device, grouped_functions)
    else:
        device.function_groups = {}

    from .panel_entity_discovery import restrict_device_functions_to_panel

    restrict_device_functions_to_panel(device)

    LOGGER.debug(
        "Loaded energy schema for device %s: %d functions, %d status, "
        "%d panel groups, %d status entities from %s",
        device.id,
        len(spec_doc.get("functions", [])),
        len(spec_doc.get("status", [])),
        len(device.function_groups),
        len(getattr(device, "panel_status_entities", [])),
        panel_source,
    )


async def preload_panel_devices(hass: HomeAssistant, manager: Manager) -> None:
    """Load panel function groups for all supported devices before entity setup."""
    from .panel_entity_discovery import (
        normalize_panel_device_status,
        prune_obsolete_panel_config_entities,
        restore_panel_entity_visibility,
    )

    for device in manager.device_map.values():
        await ensure_device_energy_schema(hass, manager, device)
        await ensure_panel_energy_properties(hass, manager, device)
        normalize_panel_device_status(device)
        prune_obsolete_panel_config_entities(hass, device)
        restore_panel_entity_visibility(hass, device)


_panel_energy_properties_locks: dict[str, asyncio.Lock] = {}


def _resolve_dp_type(device: CustomerDevice, code: str) -> str | None:
    """Return the DP type for a code from status_range or function schema."""
    if status_range := device.status_range.get(code):
        return status_range.type
    if function := device.function.get(code):
        return function.type
    return None


def _coerce_energy_property_value(
    device: CustomerDevice, code: str, value: Any
) -> Any:
    """Coerce API string value to the DP type declared on the device."""
    dp_type = _resolve_dp_type(device, code)
    if dp_type is None:
        return value

    if dp_type == "Enum":
        from .panel_entity_discovery import normalize_enum_status_value

        return normalize_enum_status_value(device, code, value)

    if not isinstance(value, str):
        return value

    if dp_type == "Boolean":
        lowered = value.lower()
        if lowered in ("true", "1"):
            return True
        if lowered in ("false", "0"):
            return False
        return value

    if dp_type in ("Integer", "hourmin"):
        try:
            return int(value)
        except ValueError:
            return value

    return value


def get_panel_property_codes(device: CustomerDevice) -> list[str]:
    """Return DP codes to query from energy/properties for the panel."""
    from .panel_entity_discovery import (
        get_panel_grouped_codes,
        get_panel_status_codes,
    )

    codes = set(get_panel_grouped_codes(device))
    codes.update(get_panel_status_codes(device))
    return sorted(codes)


def apply_energy_properties_to_device(
    hass: HomeAssistant, device: CustomerDevice, properties: dict[str, Any]
) -> list[str]:
    """Merge energy property values into device.status and notify entities."""
    from homeassistant.helpers.dispatcher import dispatcher_send

    from .const import TUYA_HA_SIGNAL_UPDATE_ENTITY
    from .panel_entity_discovery import normalize_panel_device_status

    if not properties:
        return []

    updated_codes: list[str] = []
    for code, value in properties.items():
        coerced = _coerce_energy_property_value(device, code, value)
        if device.status.get(code) != coerced:
            device.status[code] = coerced
            updated_codes.append(code)

    if updated_codes:
        normalize_panel_device_status(device, updated_codes)
        dispatcher_send(
            hass,
            f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}",
            updated_codes,
            None,
        )
    return updated_codes


async def _fetch_energy_properties(
    hass: HomeAssistant,
    manager: Manager,
    device: CustomerDevice,
    *,
    codes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Fetch current energy property values from cloud API."""
    device_id = device.id
    api_path = PROPERTIES_API_PATH.format(device_id=device_id)
    params: dict[str, str] | None = None
    if codes:
        params = {"codes": ",".join(codes)}

    LOGGER.debug(
        "Fetching energy properties from %s params=%s",
        api_path,
        params,
    )
    try:
        response = await hass.async_add_executor_job(
            manager.customer_api.get, api_path, params
        )
    except ApiRequestException as err:
        LOGGER.warning(
            "Energy properties API failed for device %s: %s", device_id, err
        )
        return None
    if not response.get("success"):
        LOGGER.warning(
            "Failed to fetch energy properties for device %s", device_id
        )
        return None

    properties = parse_energy_properties_response(response.get("result"))
    LOGGER.debug(
        "Fetched %d energy properties for device %s",
        len(properties),
        device_id,
    )
    return properties


async def ensure_panel_energy_properties(
    hass: HomeAssistant,
    manager: Manager,
    device: CustomerDevice,
) -> list[str]:
    """Fetch energy property values once per session for a panel device.

    Called from ``preload_panel_devices`` during integration setup and from
    ``get_panel_functions`` when opening the optional custom configuration panel.
    """
    if device.category not in DYNAMIC_PANEL_CATEGORIES:
        return []
    if getattr(device, "panel_energy_properties_loaded", False):
        return []

    lock = _panel_energy_properties_locks.setdefault(device.id, asyncio.Lock())
    async with lock:
        if getattr(device, "panel_energy_properties_loaded", False):
            return []

        codes = get_panel_property_codes(device)
        properties = await _fetch_energy_properties(
            hass, manager, device, codes=codes or None
        )
        if properties is None:
            return []

        device.panel_energy_properties_loaded = True
        updated_codes = apply_energy_properties_to_device(
            hass, device, properties
        )
        LOGGER.info(
            "Loaded energy properties for device %s: %d codes updated",
            device.id,
            len(updated_codes),
        )
        return updated_codes


def _serialize_energy_command_value(value: Any) -> str:
    """Serialize a command value for energy/commands API (wire format is string)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _serialize_energy_commands(
    commands: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Normalize commands payload for energy/commands API."""
    return [
        {
            "code": str(command["code"]),
            "value": _serialize_energy_command_value(command["value"]),
        }
        for command in commands
    ]


async def apply_panel_commands_via_api(
    hass: HomeAssistant,
    manager: Manager,
    device: CustomerDevice,
    commands: list[dict[str, Any]],
) -> None:
    """Apply panel dynamic entity commands via the energy commands API."""
    api_path = COMMANDS_API_PATH.format(device_id=device.id)
    payload = _serialize_energy_commands(commands)
    body = {"commands": json.dumps(payload, separators=(",", ":"))}
    LOGGER.info(
        "Applying panel commands on device %s via %s: %s",
        device.id,
        api_path,
        payload,
    )

    response = await hass.async_add_executor_job(
        manager.customer_api.post, api_path, None, body
    )
    if not response.get("success"):
        LOGGER.warning(
            "Energy commands API failed for device %s: %s",
            device.id,
            response,
        )
        raise HomeAssistantError(
            f"Failed to apply panel commands on device {device.id}"
        )


def notify_panel_commands_applied(
    hass: HomeAssistant, device: CustomerDevice, commands: list[dict[str, Any]]
) -> None:
    """Optimistically update local device status after panel commands succeed."""
    from homeassistant.helpers.dispatcher import dispatcher_send

    from .const import TUYA_HA_SIGNAL_UPDATE_ENTITY

    updated_codes = [command["code"] for command in commands]
    from .panel_entity_discovery import normalize_enum_status_value

    for command in commands:
        code = command["code"]
        device.status[code] = normalize_enum_status_value(
            device, code, command["value"]
        )
    from .panel_entity_discovery import normalize_panel_device_status

    normalize_panel_device_status(device, updated_codes)
    dispatcher_send(
        hass,
        f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}",
        updated_codes,
        None,
    )


async def apply_function_group_via_api(
    hass: HomeAssistant,
    manager: Manager,
    device: CustomerDevice,
    group_id: str,
    commands: list[dict[str, Any]],
) -> None:
    """Apply a grouped panel configuration via thing commands API."""
    LOGGER.debug(
        "Applying function group %s on device %s: %s",
        group_id,
        device.id,
        commands,
    )
    await apply_panel_commands_via_api(hass, manager, device, commands)


async def fetch_function_history_from_api(
    hass: HomeAssistant,
    manager: Manager,
    device: CustomerDevice,
    code: str,
) -> list[dict[str, Any]]:
    """Return function change history (not available yet)."""
    _ = (hass, manager, device, code)
    return []


def get_group_function_map(device: CustomerDevice) -> dict[str, set[str]]:
    """Return allowed function codes grouped by group id."""
    grouped: dict[str, set[str]] = {}
    for group_id, functions in getattr(device, "function_groups", {}).items():
        grouped[group_id] = {function.code for function in functions}
    return grouped


def validate_group_commands(
    device: CustomerDevice, group_id: str, commands: list[dict[str, Any]]
) -> None:
    """Validate that a batch command payload is complete and allowed."""
    group_map = get_group_function_map(device)
    allowed_codes = group_map.get(group_id)
    if not allowed_codes:
        raise ValueError(f"Unknown group {group_id}")

    if len(commands) != len(allowed_codes):
        raise ValueError("All functions in the group must be submitted together")

    submitted_codes = {command["code"] for command in commands}
    if submitted_codes != allowed_codes:
        raise ValueError("Submitted functions do not match the group schema")

    function_types = {
        function.code: function.type
        for functions in device.function_groups.values()
        for function in functions
    }
    for command in commands:
        code = command["code"]
        value = command.get("value")
        if not is_value_filled(function_types[code], value):
            raise ValueError(f"Function {code} must not be empty")
