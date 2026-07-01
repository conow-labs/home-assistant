"""Support for Tuya Smart devices."""

from tuya_sharing import Manager

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    TUYA_CLIENT_ID,
)
from .coordinator import DeviceListener, TuyaConfigEntry
from .panel_api import async_register_tuya_panel
from .panel_functions import preload_panel_devices
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tuya Services."""
    await async_setup_services(hass)
    await async_register_tuya_panel(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Async setup hass config entry."""
    listener = DeviceListener(hass, entry)
    await hass.async_add_executor_job(listener.initialize)

    # Connection is successful, store the listener in runtime_data
    entry.runtime_data = listener
    manager = listener.manager

    # Cleanup device registry
    await cleanup_device_registry(hass, manager, entry)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in manager.device_map.values():
        LOGGER.debug(
            "Register device %s (online: %s): %s (function: %s, status range: %s)",
            device.id,
            device.online,
            device.status,
            device.function,
            device.status_range,
        )
        # Register quirk, and add device to the device registry
        listener.async_register_device(device_registry, device)

    await preload_panel_devices(hass, manager)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _prune_panel_entities_later(_now) -> None:
        """Prune stale panel entities after platforms finish without blocking bootstrap."""
        from .panel_entity_discovery import (
            is_panel_device,
            prune_obsolete_panel_config_entities,
        )

        for device in manager.device_map.values():
            if is_panel_device(device):
                prune_obsolete_panel_config_entities(hass, device)

    async_call_later(hass, 0, _prune_panel_entities_later)

    # If the device does not register any entities,
    # the device does not need to subscribe
    # So the subscription is here
    await hass.async_add_executor_job(manager.refresh_mq)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: Manager, entry: TuyaConfigEntry
) -> None:
    """Unlink device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_update_device(
                    device_entry.id, remove_config_entry_id=entry.entry_id
                )
                break


async def async_unload_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        listener = entry.runtime_data
        manager = listener.manager
        if manager.mq is not None:
            manager.mq.stop()
        manager.remove_device_listener(listener)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    manager = Manager(
        TUYA_CLIENT_ID,
        entry.data[CONF_USER_CODE],
        entry.data[CONF_TERMINAL_ID],
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_TOKEN_INFO],
    )
    await hass.async_add_executor_job(manager.unload)
