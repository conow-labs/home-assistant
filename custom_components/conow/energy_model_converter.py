"""Convert energy device model JSON to HA instruction set and panel schema."""

from __future__ import annotations

import json
import re
from typing import Any

PANEL_DP_TYPES = frozenset({"Boolean", "Integer", "Enum", "String", "hourmin"})

DATA_SPEC_TYPE_MAP: dict[str, str] = {
    "value": "Integer",
    "enum": "Enum",
    "boolean": "Boolean",
    "hourmin": "hourmin",
    "string": "String",
    "date": "String",
}

SEMANTIC_TO_BUCKET: dict[str, str] = {
    "instant": "status",
    "setting": "functions",
}

ENERGY_MODEL_TYPES = frozenset({"instant", "setting", "alarm"})

_WIRE_ENUM_TOKEN = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_wire_enum_token(value: str) -> bool:
    """Return whether a range_info name looks like a wire enum value."""
    if not value:
        return False
    if " " in value or "-" in value:
        return False
    return bool(_WIRE_ENUM_TOKEN.match(value))


def _to_float(value: Any) -> float:
    """Convert numeric spec field to float."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _to_int(value: Any) -> int:
    """Convert numeric spec field to int for values JSON."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(float(str(value)))


def is_energy_model_entry(entry: Any) -> bool:
    """Return whether an object is an energy model schema entry."""
    if not isinstance(entry, dict):
        return False
    if "data_spec" in entry:
        return True
    return entry.get("type") in ENERGY_MODEL_TYPES


def extract_energy_model_entries(result: Any) -> list[dict[str, Any]] | None:
    """Extract energy model entries from an API or mock payload."""
    if isinstance(result, list):
        if result and is_energy_model_entry(result[0]):
            return result
        return None

    if not isinstance(result, dict):
        return None

    for key in ("model", "items", "data", "schemas", "specifications"):
        value = result.get(key)
        if isinstance(value, list) and value and is_energy_model_entry(value[0]):
            return value

    return None


def map_data_spec_type(data_spec: dict[str, Any] | None) -> str | None:
    """Map energy model data_spec.type to Tuya HA DP type."""
    if not data_spec:
        return None
    spec_type = data_spec.get("type")
    if not spec_type:
        return None
    return DATA_SPEC_TYPE_MAP.get(str(spec_type))


def build_enum_range(data_spec: dict[str, Any]) -> list[str]:
    """Build enum range for values JSON."""
    range_info = data_spec.get("range_info")
    if isinstance(range_info, list) and range_info:
        result: list[str] = []
        for item in range_info:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            code = str(item.get("code", ""))
            if _is_wire_enum_token(name):
                result.append(name)
            elif code:
                result.append(code)
        if result:
            return result
    raw_range = data_spec.get("range")
    if isinstance(raw_range, list):
        return [str(item) for item in raw_range]
    return []


def build_enum_code_to_wire_map(data_spec: dict[str, Any]) -> dict[str, str]:
    """Map energy/commands protocol codes to HA enum range tokens."""
    mapping: dict[str, str] = {}
    range_info = data_spec.get("range_info")
    if not isinstance(range_info, list):
        return mapping

    for item in range_info:
        if not isinstance(item, dict):
            continue
        protocol_code = str(item.get("code", ""))
        if not protocol_code:
            continue
        name = str(item.get("name", ""))
        if _is_wire_enum_token(name):
            mapping[protocol_code] = name
        else:
            mapping[protocol_code] = protocol_code
    return mapping


def build_panel_enum_code_maps(
    model_entries: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Build per-DP protocol-code maps for all enum entries in a model."""
    maps: dict[str, dict[str, str]] = {}
    for entry in model_entries:
        if not isinstance(entry, dict):
            continue
        data_spec = entry.get("data_spec")
        if not isinstance(data_spec, dict):
            continue
        if map_data_spec_type(data_spec) != "Enum":
            continue
        code = entry.get("code")
        if not code:
            continue
        code_map = build_enum_code_to_wire_map(data_spec)
        if code_map:
            maps[str(code)] = code_map
    return maps


def _parse_enum_range_from_values(values: Any) -> list[str]:
    """Parse enum range tokens from a Tuya values JSON string or dict."""
    parsed: dict[str, Any] | None
    if isinstance(values, str):
        try:
            parsed = json.loads(values)
        except (json.JSONDecodeError, TypeError):
            return []
    elif isinstance(values, dict):
        parsed = values
    else:
        return []

    enum_range = parsed.get("range") if parsed else None
    if isinstance(enum_range, list):
        return [str(item) for item in enum_range]
    return []


def build_enum_wire_to_code_map(
    data_spec: dict[str, Any],
    *,
    mqtt_enum_range: list[str] | None = None,
    target_enum_range: list[str] | None = None,
) -> dict[str, str]:
    """Map MQTT/status wire enum tokens to HA select range tokens."""
    target_range = target_enum_range or build_enum_range(data_spec)
    if not target_range:
        return {}

    wire_map: dict[str, str] = {}
    range_info = data_spec.get("range_info")
    if isinstance(range_info, list):
        for item in range_info:
            if not isinstance(item, dict):
                continue
            protocol_code = str(item.get("code", ""))
            if not protocol_code or protocol_code not in target_range:
                continue
            name = str(item.get("name", ""))
            if _is_wire_enum_token(name):
                wire_map[name] = protocol_code

        if mqtt_enum_range:
            for wire, item in zip(mqtt_enum_range, range_info):
                if not isinstance(item, dict):
                    continue
                protocol_code = str(item.get("code", ""))
                if protocol_code in target_range:
                    wire_map[str(wire)] = protocol_code

    if mqtt_enum_range:
        for wire in mqtt_enum_range:
            token = str(wire)
            if token in target_range:
                wire_map[token] = token

    return wire_map


# MQTT wire tokens that differ from energy-model protocol codes (xnyjcn).
KNOWN_ENUM_WIRE_ALIASES: dict[str, dict[str, str]] = {
    "work_mode": {
        "self_powered": "1",
        "time_of_use": "2",
        "manual": "3",
        "diy": "5",
        "self": "1",
        "tou": "2",
    },
}

# Backward-compatible alias for internal builder usage.
_KNOWN_ENUM_WIRE_ALIASES = KNOWN_ENUM_WIRE_ALIASES


def build_panel_enum_wire_to_code_maps(
    model_entries: list[dict[str, Any]],
    spec_doc: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Build per-DP wire-to-range maps for MQTT/status enum normalization."""
    mqtt_ranges: dict[str, list[str]] = {}
    for bucket in ("status", "functions"):
        for item in spec_doc.get(bucket, []):
            if not isinstance(item, dict) or item.get("type") != "Enum":
                continue
            code = str(item.get("code", ""))
            if not code:
                continue
            enum_range = _parse_enum_range_from_values(item.get("values", "{}"))
            if enum_range and any(_is_wire_enum_token(token) for token in enum_range):
                mqtt_ranges[code] = enum_range

    maps: dict[str, dict[str, str]] = {}
    for entry in model_entries:
        if not isinstance(entry, dict):
            continue
        data_spec = entry.get("data_spec")
        if not isinstance(data_spec, dict):
            continue
        if map_data_spec_type(data_spec) != "Enum":
            continue
        code = str(entry.get("code", ""))
        if not code:
            continue

        target_range = build_enum_range(data_spec)
        wire_map = build_enum_wire_to_code_map(
            data_spec,
            mqtt_enum_range=mqtt_ranges.get(code),
            target_enum_range=target_range,
        )
        for wire, protocol in _KNOWN_ENUM_WIRE_ALIASES.get(code, {}).items():
            if protocol in target_range:
                wire_map.setdefault(wire, protocol)

        if wire_map:
            maps[code] = wire_map
    return maps


def build_values_payload(dp_type: str, data_spec: dict[str, Any]) -> dict[str, Any]:
    """Build the values object before JSON string serialization."""
    if dp_type in {"Boolean", "hourmin"}:
        return {}
    if dp_type == "Integer":
        scale = _to_int(data_spec.get("scale", 0))
        min_display = _to_float(data_spec.get("min", 0))
        max_display = _to_float(data_spec.get("max", 0))
        step_display = _to_float(data_spec.get("step", 1))
        factor = 10**scale if scale > 0 else 1
        payload: dict[str, Any] = {
            "min": int(round(min_display * factor)),
            "max": int(round(max_display * factor)),
            "scale": scale,
            "step": max(1, int(round(step_display * factor)))
            if scale > 0
            else _to_int(step_display),
        }
        unit = data_spec.get("unit")
        payload["unit"] = "" if unit is None else str(unit)
        return payload
    if dp_type == "Enum":
        return {"range": build_enum_range(data_spec)}
    if dp_type == "String":
        length = data_spec.get("length") or data_spec.get("maxlen")
        if length is not None:
            return {"maxlen": _to_int(length)}
        return {}
    return {}


def build_values_string(dp_type: str, data_spec: dict[str, Any]) -> str:
    """Serialize values field as compact JSON string (Tuya SDK format)."""
    payload = build_values_payload(dp_type, data_spec)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def convert_model_entry(entry: dict[str, Any]) -> dict[str, str] | None:
    """Convert one energy model entry to instruction-set item."""
    semantic_type = entry.get("type")
    if semantic_type not in SEMANTIC_TO_BUCKET:
        return None

    data_spec = entry.get("data_spec")
    if not isinstance(data_spec, dict):
        return None

    dp_type = map_data_spec_type(data_spec)
    if dp_type is None:
        return None

    code = entry.get("code")
    if not code:
        return None

    return {
        "code": str(code),
        "type": dp_type,
        "values": build_values_string(dp_type, data_spec),
    }


def convert_energy_model(
    model_entries: list[dict[str, Any]],
    *,
    category: str,
) -> dict[str, Any]:
    """Convert energy model list to report/command instruction set document."""
    result: dict[str, Any] = {
        "category": category,
        "functions": [],
        "status": [],
    }

    for entry in model_entries:
        if not isinstance(entry, dict):
            continue
        converted = convert_model_entry(entry)
        if converted is None:
            continue
        bucket = SEMANTIC_TO_BUCKET[str(entry["type"])]
        result[bucket].append(converted)

    return result


def _dedupe_panel_functions_by_code(
    functions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one item per DP code in a panel function list."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in functions:
        code = str(item.get("code", ""))
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append(item)
    return deduped


def convert_panel_functions(
    model_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert setting entries to flat panel function list (control entities)."""
    functions: list[dict[str, Any]] = []

    for entry in model_entries:
        if not isinstance(entry, dict) or entry.get("type") != "setting":
            continue
        converted = convert_model_entry(entry)
        if converted is None or converted["type"] not in PANEL_DP_TYPES:
            continue

        item: dict[str, Any] = dict(converted)
        if name := entry.get("name"):
            item["name"] = str(name)
        functions.append(item)

    functions.sort(key=lambda item: item["code"])
    return _dedupe_panel_functions_by_code(functions)


def parse_energy_specifications_response(
    result: Any,
    *,
    category: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """Parse energy specifications API result into instruction set + panel list."""
    model_entries = extract_energy_model_entries(result)
    if model_entries is not None:
        return (
            convert_energy_model(model_entries, category=category),
            convert_panel_functions(model_entries),
        )

    if not isinstance(result, dict):
        return None

    functions = result.get("functions")
    status = result.get("status")
    if isinstance(functions, list) and isinstance(status, list):
        panel_functions = result.get("groups")
        if panel_functions is None:
            panel_functions = functions
        if isinstance(panel_functions, dict):
            panel_functions = [
                item
                for items in panel_functions.values()
                if isinstance(items, list)
                for item in items
                if isinstance(item, dict) and "code" in item
            ]
        if not isinstance(panel_functions, list):
            panel_functions = []
        return (
            {
                "category": result.get("category") or category,
                "functions": functions,
                "status": status,
            },
            panel_functions,
        )

    return None


def parse_energy_properties_response(result: Any) -> dict[str, Any]:
    """Parse List[DeviceModelPropertyValueVO] into {code: value}.

    API item shape::

        {"code": "day_time1_end", "value": "1059", "time": "1776046921026"}

    ``value`` and ``time`` are strings on the wire; ``time`` is ignored here.
    """
    properties: dict[str, Any] = {}

    if not isinstance(result, list):
        return properties

    for item in result:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if not code or "value" not in item:
            continue
        properties[str(code)] = item["value"]

    return properties
