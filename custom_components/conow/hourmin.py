"""HHMM (hourmin) time encoding helpers for panel functions."""

from __future__ import annotations

from datetime import time

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN

MAX_HOURMIN = 2359


def hourmin_to_time(value: int | float | str | None) -> time | None:
    """Convert a Tuya hourmin value (e.g. 2300) to a time object."""
    if value is None or value == "":
        return None
    try:
        encoded = int(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= encoded <= MAX_HOURMIN:
        return None
    hour, minute = divmod(encoded, 100)
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute, 0)


def time_to_hourmin(value: time) -> int:
    """Convert a time object to a Tuya hourmin integer (e.g. 23:00 -> 2300)."""
    return value.hour * 100 + value.minute


def validate_hourmin_encoded(encoded: int) -> None:
    """Raise if an hourmin encoded value is out of range."""
    if not 0 <= encoded <= MAX_HOURMIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="hourmin_out_of_range",
            translation_placeholders={"value": str(encoded)},
        )
    hour, minute = divmod(encoded, 100)
    if hour > 23:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="demo_schedule_time_invalid_hour",
            translation_placeholders={"hour": str(hour)},
        )
    if minute > 59:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="demo_schedule_time_invalid_minute",
            translation_placeholders={"minute": str(minute)},
        )
