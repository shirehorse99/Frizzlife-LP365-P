"""Read-only local FrizzLife monitoring."""
import asyncio
import voluptuous as vol
from datetime import timedelta
from pathlib import Path
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from .const import DOMAIN, PLATFORMS
from .protocol import read_status
from .comparison_coordinator import ComparisonCoordinator
from .analytics_coordinator import AnalyticsCoordinator
from .observations import ObservationLedger
from .readings import decode
from .notifications import NotificationManager
from homeassistant.exceptions import HomeAssistantError


class MonitorCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        import logging
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         update_interval=timedelta(seconds=30), config_entry=entry)
        self.entry = entry
        self.last_poll = None
        self.ledger = ObservationLedger()
        self.ledger_store = Store(hass, 1, f"{DOMAIN}_observations_{entry.entry_id}")
        self.ledger_save_at = None

    def schedule_ledger_save(self):
        now = dt_util.utcnow()
        if self.ledger_save_at is None or (now - self.ledger_save_at).total_seconds() >= 60:
            self.ledger_save_at = now
            self.ledger_store.async_delay_save(self.ledger.dump, 1)

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(read_status, self.entry.data)
            self.last_poll = dt_util.utcnow()
            self.ledger.record(dt_util.now(), True,
                decode(result, "water_today") if self.entry.data.get("verified_volume") else None,
                decode(result, "flow"), decode(result, "pressure_bar", self.entry.data.get("pressure_factor")),
                self.entry.options.get("flow_observation_lph", 5))
            self.schedule_ledger_save()
            return result
        except Exception:
            self.ledger.record(dt_util.now(), False)
            self.schedule_ledger_save()
            # Do not pass library exception text or payloads to HA logs.
            raise UpdateFailed("Unable to read local monitor status") from None


async def async_setup_entry(hass, entry):
    coordinator = MonitorCoordinator(hass, entry)
    coordinator.ledger = ObservationLedger(await coordinator.ledger_store.async_load())
    # Existing entries must still load quality/notification entities when the
    # monitor is offline at HA startup. Device entities remain unavailable.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    coordinator.analytics = AnalyticsCoordinator(hass, coordinator)
    await coordinator.analytics.async_refresh()
    coordinator.comparison = ComparisonCoordinator(hass, coordinator)
    await coordinator.comparison.async_refresh()
    coordinator.notifications = NotificationManager(hass, coordinator)
    await coordinator.notifications.async_load()
    entry.async_on_unload(coordinator.async_add_listener(coordinator.analytics.handle_monitor_update))
    entry.async_on_unload(coordinator.analytics.async_add_listener(coordinator.comparison.handle_monitor_update))
    entry.async_on_unload(coordinator.analytics.async_add_listener(coordinator.notifications.handle_update))
    coordinator.notifications.handle_update()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    data = hass.data.setdefault(DOMAIN, {})
    async with data.setdefault("resource_lock", asyncio.Lock()):
        if not data.get("resource_registered"):
            await hass.http.async_register_static_paths([StaticPathConfig(
                "/frizzlife_readonly/dashboard.js",
                str(Path(__file__).parent / "frontend" / "dashboard.js"), False)])
            data["resource_registered"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not hass.services.has_service(DOMAIN, "test_notifications"):
        async def test_notifications(call):
            target = next((e for e in hass.config_entries.async_entries(DOMAIN)
                           if e.entry_id == call.data["entry_id"]), None)
            if target is None or not hasattr(target, "runtime_data") or not target.options.get("notifications_enabled", False):
                raise HomeAssistantError("Enable notifications for a loaded FrizzLife entry first")
            await target.runtime_data.notifications.async_test()
        hass.services.async_register(DOMAIN, "test_notifications", test_notifications,
            schema=vol.Schema({vol.Required("entry_id"): str}))
    return True


async def async_unload_entry(hass, entry):
    await entry.runtime_data.ledger_store.async_save(entry.runtime_data.ledger.dump())
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
