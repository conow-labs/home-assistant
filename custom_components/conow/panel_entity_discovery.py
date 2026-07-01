"""Dynamic entity discovery for Tuya panel function groups."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from tuya_sharing import CustomerDevice
from tuya_sharing.device import DeviceFunction

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.time import TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import DOMAIN, LOGGER
from .energy_model_converter import KNOWN_ENUM_WIRE_ALIASES
from .panel_functions import DYNAMIC_PANEL_CATEGORIES, format_function_label

PANEL_TYPE_TO_PLATFORM: dict[str, str] = {
    "Boolean": "switch",
    "Integer": "number",
    "Enum": "select",
    "hourmin": "time",
}

PANEL_STATUS_SENSOR_TYPES = frozenset({"Integer", "Enum", "String"})

CONFIG_PLATFORMS = ("number", "select", "switch", "time")


def _normalize_integer_status_value(
    value: Any, *, min_val: int, max_val: int, scale: int
) -> Any:
    """Convert /sta display values to raw INTEGER device status."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        if scale > 0:
            try:
                display_value = float(value)
                raw_value = round(display_value * (10**scale))
                if min_val <= raw_value <= max_val:
                    return raw_value
            except ValueError:
                pass
        try:
            raw_value = int(value)
            if min_val <= raw_value <= max_val:
                return raw_value
        except ValueError:
            pass
        return value

    if isinstance(value, float):
        if scale > 0:
            raw_value = round(value * (10**scale))
            if min_val <= raw_value <= max_val:
                return raw_value
        raw_value = round(value)
        if min_val <= raw_value <= max_val:
            return raw_value

    return value


def _normalize_boolean_status_value(value: Any) -> Any:
    """Convert /sta string booleans to Python bool for device handlers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "1"):
            return True
        if lowered in ("false", "0"):
            return False
    if value in (0, 1):
        return bool(value)
    return value


def _resolve_panel_dp_type(device: CustomerDevice, code: str) -> str | None:
    """Return DP type from status_range or function schema."""
    if status_range := device.status_range.get(code):
        return status_range.type
    if function := device.function.get(code):
        return function.type
    return None


def _enum_range_for_code(device: CustomerDevice, code: str) -> list[str]:
    """Return enum option tokens declared on the device status schema."""
    status_range = device.status_range.get(code)
    if status_range is None or status_range.type != "Enum":
        return []
    try:
        parsed = json.loads(status_range.values)
    except (json.JSONDecodeError, TypeError):
        return []
    enum_range = parsed.get("range")
    if not isinstance(enum_range, list):
        return []
    return [str(item) for item in enum_range]


def _ha_enum_range_for_code(device: CustomerDevice, code: str) -> list[str]:
    """Return enum options used by HA select entities (energy model preferred)."""
    function = device.function.get(code)
    if function is not None and function.type == "Enum" and function.values:
        try:
            parsed = json.loads(function.values)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            enum_range = parsed.get("range")
            if isinstance(enum_range, list) and enum_range:
                return [str(item) for item in enum_range]
    return _enum_range_for_code(device, code)


def _map_wire_enum_to_protocol(
    device: CustomerDevice, code: str, wire_value: str, ha_range: list[str]
) -> str | None:
    """Map MQTT wire enum token to HA/protocol enum code."""
    wire_to_code_maps = getattr(device, "panel_enum_wire_to_code_maps", None)
    if isinstance(wire_to_code_maps, dict):
        protocol_value = wire_to_code_maps.get(code, {}).get(wire_value)
        if protocol_value is not None and (not ha_range or protocol_value in ha_range):
            return protocol_value

    protocol_value = KNOWN_ENUM_WIRE_ALIASES.get(code, {}).get(wire_value)
    if protocol_value is not None and (not ha_range or protocol_value in ha_range):
        return protocol_value

    code_maps = getattr(device, "panel_enum_code_maps", None)
    if isinstance(code_maps, dict):
        mapped_wire = code_maps.get(code, {}).get(wire_value)
        if mapped_wire is not None and (not ha_range or mapped_wire in ha_range):
            return mapped_wire

    return None


def normalize_enum_status_value(
    device: CustomerDevice, code: str, value: Any
) -> Any:
    """Normalize enum status to match HA select options after commands/properties."""
    if value is None:
        return value

    str_value = str(value)
    ha_range = _ha_enum_range_for_code(device, code)
    status_range = _enum_range_for_code(device, code)

    if ha_range and str_value in ha_range:
        return str_value

    if mapped := _map_wire_enum_to_protocol(device, code, str_value, ha_range):
        return mapped

    if status_range and str_value in status_range:
        return str_value

    return value


def normalize_panel_device_status(
    device: CustomerDevice,
    codes: list[str] | None = None,
) -> None:
    """Normalize panel status values for tuya_device_handlers."""
    if not is_panel_device(device):
        return

    targets = codes if codes else list(device.status.keys())
    for code in targets:
        if code not in device.status:
            continue

        dp_type = _resolve_panel_dp_type(device, code)
        if dp_type == "Boolean":
            device.status[code] = _normalize_boolean_status_value(device.status[code])
            continue

        if dp_type == "Enum":
            device.status[code] = normalize_enum_status_value(
                device, code, device.status[code]
            )
            continue

        status_range = device.status_range.get(code)
        if status_range is None or status_range.type != "Integer":
            continue
        try:
            range_values = json.loads(status_range.values)
        except (json.JSONDecodeError, TypeError):
            continue

        normalized = _normalize_integer_status_value(
            device.status[code],
            min_val=int(range_values.get("min", 0)),
            max_val=int(range_values.get("max", 0)),
            scale=int(range_values.get("scale", 0)),
        )
        device.status[code] = normalized


def is_panel_device(device: CustomerDevice) -> bool:
    """Return whether the device supports dynamic panel entities."""
    return device.category in DYNAMIC_PANEL_CATEGORIES


def panel_unique_id(tuya_device_id: str, code: str) -> str:
    """Return the unique id used by Tuya config entities."""
    return f"tuya.{tuya_device_id}{code}"


def get_panel_status_entities(device: CustomerDevice) -> list[dict]:
    """Return read-only status DP schema entries for sensor discovery."""
    entities = getattr(device, "panel_status_entities", [])
    return entities if isinstance(entities, list) else []


def iter_panel_status_sensors(
    device: CustomerDevice,
) -> Iterator[dict[str, Any]]:
    """Yield read-only status schema entries as sensor candidates."""
    if not is_panel_device(device):
        return

    grouped_codes = get_panel_grouped_codes(device)
    seen: set[str] = set()
    for entry in get_panel_status_entities(device):
        if not isinstance(entry, dict) or "code" not in entry:
            continue
        code = str(entry["code"])
        if code in grouped_codes or code in seen:
            continue
        if str(entry.get("type", "")) not in PANEL_STATUS_SENSOR_TYPES:
            continue
        seen.add(code)
        yield entry


def build_panel_status_sensor_description(
    entry: dict[str, Any],
) -> SensorEntityDescription:
    """Build a sensor entity description for a read-only status DP."""
    function = status_entry_to_function(entry)
    return SensorEntityDescription(
        key=function.code,
        name=format_function_label(function),
        translation_key=function.code,
    )


def get_panel_status_sensor_definition(device: CustomerDevice, code: str):
    """Return a sensor definition for a read-only panel status DP."""
    from tuya_device_handlers.definition.sensor import (
        SensorDefinition,
        get_default_definition,
    )
    from tuya_device_handlers.device_wrapper.common import DPCodeStringWrapper

    if definition := get_default_definition(device, code):
        return definition
    if wrapper := DPCodeStringWrapper.find_dpcode(device, code):
        return SensorDefinition(sensor_wrapper=wrapper)
    return None


def status_entry_to_function(entry: dict) -> DeviceFunction:
    """Convert a status schema entry to a DeviceFunction."""
    return DeviceFunction(**entry)


def iter_panel_functions(
    device: CustomerDevice,
) -> Iterator[tuple[DeviceFunction, str]]:
    """Yield panel functions that should become dynamic entities."""
    if not is_panel_device(device):
        return

    seen: set[str] = set()
    for functions in getattr(device, "function_groups", {}).values():
        for function in functions:
            code = function.code
            if code in seen:
                continue
            platform = PANEL_TYPE_TO_PLATFORM.get(function.type)
            if platform is None:
                continue
            seen.add(code)
            yield function, platform


def build_number_description(
    function: DeviceFunction, *, entity_category: EntityCategory | None = None
) -> NumberEntityDescription:
    """Build a number entity description for a panel function."""
    return NumberEntityDescription(
        key=function.code,
        name=format_function_label(function),
        translation_key=function.code,
        entity_category=entity_category,
    )


def build_select_description(
    function: DeviceFunction, *, entity_category: EntityCategory | None = None
) -> SelectEntityDescription:
    """Build a select entity description for a panel function."""
    return SelectEntityDescription(
        key=function.code,
        name=format_function_label(function),
        translation_key=function.code,
        entity_category=entity_category,
    )


def build_switch_description(
    function: DeviceFunction, *, entity_category: EntityCategory | None = None
) -> SwitchEntityDescription:
    """Build a switch entity description for a panel function."""
    return SwitchEntityDescription(
        key=function.code,
        name=format_function_label(function),
        translation_key=function.code,
        entity_category=entity_category,
    )


def build_time_description(
    function: DeviceFunction, *, entity_category: EntityCategory | None = None
) -> TimeEntityDescription:
    """Build a time entity description for an hourmin panel function."""
    return TimeEntityDescription(
        key=function.code,
        name=format_function_label(function),
        translation_key=function.code,
        entity_category=entity_category,
    )


def resolve_entity_id(
    hass: HomeAssistant, tuya_device_id: str, code: str, platform: str
) -> str | None:
    """Resolve entity_id from platform and unique_id."""
    entity_registry = er.async_get(hass)
    return entity_registry.async_get_entity_id(
        platform, DOMAIN, panel_unique_id(tuya_device_id, code)
    )


def get_panel_grouped_codes(device: CustomerDevice) -> set[str]:
    """Return all DP codes that belong to panel function groups."""
    grouped_codes: set[str] = set()
    for functions in getattr(device, "function_groups", {}).values():
        grouped_codes.update(function.code for function in functions)
    return grouped_codes


def get_panel_status_codes(device: CustomerDevice) -> set[str]:
    """Return read-only status DP codes allowed for panel sensor entities."""
    status_codes: set[str] = set()
    grouped_codes = get_panel_grouped_codes(device)
    for entry in get_panel_status_entities(device):
        if not isinstance(entry, dict) or "code" not in entry:
            continue
        code = str(entry["code"])
        if code in grouped_codes:
            continue
        if str(entry.get("type", "")) not in PANEL_STATUS_SENSOR_TYPES:
            continue
        status_codes.add(code)
    return status_codes


def restrict_device_functions_to_panel(device: CustomerDevice) -> None:
    """Keep only panel-group writable DPs in device.function."""
    if not is_panel_device(device):
        return
    allowed_codes = get_panel_grouped_codes(device)
    for code in list(device.function.keys()):
        if code not in allowed_codes:
            device.function.pop(code, None)


def prune_obsolete_panel_config_entities(
    hass: HomeAssistant, device: CustomerDevice
) -> None:
    """Remove panel entities that are not in the current mock/API schema."""
    if not is_panel_device(device):
        return

    from .const import DOMAIN

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, device.id)}
    )
    if device_entry is None:
        return

    allowed_config_codes = get_panel_grouped_codes(device)
    allowed_sensor_codes = get_panel_status_codes(device)
    entity_registry = er.async_get(hass)
    expected_prefix = panel_unique_id(device.id, "")
    stale_entity_ids: list[tuple[str, str]] = []
    for entry in er.async_entries_for_device(
        entity_registry, device_entry.id, include_disabled_entities=True
    ):
        if entry.platform != DOMAIN:
            continue
        if not entry.unique_id.startswith(expected_prefix):
            continue
        code = entry.unique_id.removeprefix(expected_prefix)
        if entry.domain in CONFIG_PLATFORMS:
            if code not in allowed_config_codes:
                stale_entity_ids.append((entry.entity_id, "config"))
            continue
        if entry.domain == "sensor" and code not in allowed_sensor_codes:
            stale_entity_ids.append((entry.entity_id, "sensor"))

    for entity_id, kind in stale_entity_ids:
        entry = entity_registry.async_get(entity_id)
        if entry is None:
            continue
        delete_key = (entry.domain, entry.platform, entry.unique_id)
        entity_registry.async_remove(entity_id)
        entity_registry.deleted_entities.pop(delete_key, None)
        LOGGER.info(
            "Removing obsolete panel %s entity %s (not in panel schema)",
            kind,
            entity_id,
        )


def is_panel_grouped_code(device: CustomerDevice, code: str) -> bool:
    """Return whether a DP code belongs to panel function groups."""
    return code in get_panel_grouped_codes(device)


def is_panel_dynamic_code(device: CustomerDevice, code: str) -> bool:
    """Return whether a DP code should use the panel commands API."""
    return is_panel_grouped_code(device, code)


def restore_panel_entity_visibility(hass: HomeAssistant, device: CustomerDevice) -> None:
    """Clear integration-hidden state for panel function entities."""
    if not is_panel_device(device):
        return

    entity_registry = er.async_get(hass)
    for code in get_panel_grouped_codes(device):
        for platform in CONFIG_PLATFORMS:
            entity_id = resolve_entity_id(hass, device.id, code, platform)
            if not entity_id:
                continue
            entry = entity_registry.async_get(entity_id)
            if not entry:
                continue
            updates: dict[str, object] = {}
            if entry.hidden_by == RegistryEntryHider.INTEGRATION:
                updates["hidden_by"] = None
            if entry.entity_category is not None:
                updates["entity_category"] = None
            if updates:
                entity_registry.async_update_entity(entity_id, **updates)


def resolve_entity_id_for_function(
    hass: HomeAssistant, device: CustomerDevice, function: DeviceFunction
) -> str | None:
    """Resolve entity_id for a panel function."""
    if function.type == "hourmin":
        return resolve_entity_id(hass, device.id, function.code, "time")

    platform = PANEL_TYPE_TO_PLATFORM.get(function.type)
    if platform and (
        entity_id := resolve_entity_id(hass, device.id, function.code, platform)
    ):
        return entity_id

    for fallback_platform in CONFIG_PLATFORMS:
        if entity_id := resolve_entity_id(
            hass, device.id, function.code, fallback_platform
        ):
            return entity_id
    return None
