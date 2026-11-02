"""Read-only local FrizzLife monitoring."""
import asyncio
from datetime import timedelta
from pathlib import Path
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .const import DOMAIN, PLATFORMS
from .protocol import read_status
from .comparison_coordinator import ComparisonCoordinator


class MonitorCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        import logging
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         update_interval=timedelta(seconds=30), config_entry=entry)
        self.entry = entry
        self.last_poll = None

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(read_status, self.entry.data)
            self.last_poll = dt_util.utcnow()
            return result
        except Exception:
            # Do not pass library exception text or payloads to HA logs.
            raise UpdateFailed("Unable to read local monitor status") from None


async def async_setup_entry(hass, entry):
    coordinator = MonitorCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.comparison = ComparisonCoordinator(hass, coordinator)
    await coordinator.comparison.async_refresh()
    entry.async_on_unload(coordinator.async_add_listener(coordinator.comparison.handle_monitor_update))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    data = hass.data.setdefault(DOMAIN, {})
    async with data.setdefault("resource_lock", asyncio.Lock()):
        if not data.get("resource_registered"):
            await hass.http.async_register_static_paths([StaticPathConfig(
                "/frizzlife_readonly/dashboard.js",
                str(Path(__file__).parent / "frontend" / "dashboard.js"), False)])
            data["resource_registered"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
