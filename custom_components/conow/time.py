"""Time entities for Tuya panel hourmin functions."""

from __future__ import annotations

from datetime import time

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceFunction

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, TUYA_DISCOVERY_NEW
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity
from .hourmin import hourmin_to_time, time_to_hourmin, validate_hourmin_encoded
from .panel_entity_discovery import (
    build_time_description,
    is_panel_device,
    iter_panel_functions,
    panel_unique_id,
)

LEGACY_DEMO_KEYS = ("demo_schedule_datetime", "demo_schedule_time")


@callback
def async_remove_legacy_demo_entities(
    hass: HomeAssistant, device: CustomerDevice
) -> None:
    """Remove obsolete demo time/datetime entities from earlier PoCs."""
    entity_registry = er.async_get(hass)
    for legacy_key in LEGACY_DEMO_KEYS:
        for platform in ("datetime", "time"):
            entity_id = entity_registry.async_get_entity_id(
                platform,
                DOMAIN,
                panel_unique_id(device.id, legacy_key),
            )
            if entity_id:
                entity_registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up hourmin time entities for panel devices."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add hourmin time entities."""
        entities: list[TuyaPanelHourminTimeEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if not is_panel_device(device):
                continue
            async_remove_legacy_demo_entities(hass, device)
            for function, platform in iter_panel_functions(device):
                if platform != "time":
                    continue
                entities.append(
                    TuyaPanelHourminTimeEntity(device, manager, function)
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaPanelHourminTimeEntity(TuyaEntity, TimeEntity):
    """Tuya time entity backed by an hourmin DP (HHMM integer)."""

    entity_description: TimeEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        function: DeviceFunction,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize an hourmin time entity."""
        super().__init__(
            device,
            device_manager,
            build_time_description(function, entity_category=entity_category),
        )
        self._code = function.code

    @property
    def native_value(self) -> time | None:
        """Return the current time from the device hourmin DP."""
        return hourmin_to_time(self.device.status.get(self._code))

    async def async_set_value(self, value: time) -> None:
        """Send an hourmin command for the selected time."""
        normalized = value.replace(second=0, microsecond=0)
        encoded = time_to_hourmin(normalized)
        validate_hourmin_encoded(encoded)
        await self._async_send_commands([{"code": self._code, "value": encoded}])

    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Refresh when this hourmin DP is reported."""
        if (
            updated_status_properties is not None
            and self._code not in updated_status_properties
        ):
            return False
        return True
