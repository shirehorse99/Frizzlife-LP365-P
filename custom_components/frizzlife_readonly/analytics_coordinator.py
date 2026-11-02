"""Hourly Recorder trends with live local quality and pattern observations."""
from datetime import timedelta
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .analytics import daily_records, usage_summary
from .const import DOMAIN
from .readings import decode


class AnalyticsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, monitor):
        super().__init__(hass, logging.getLogger(__name__), name=f"{DOMAIN}_analytics",
                         update_interval=timedelta(hours=1), config_entry=monitor.entry)
        self.monitor, self.entry = monitor, monitor.entry
        self.rows, self.records, self.usable = [], {}, {}
        self.statistics_status = "Waiting for Recorder"

    async def _async_update_data(self):
        now = dt_util.now()
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{self.entry.data['device_id']}_water_today")
        if entity_id and "recorder" in self.hass.config.components and self.entry.data.get("verified_volume"):
            try:
                midnight = dt_util.start_of_local_day(now)
                result = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period, self.hass, dt_util.as_utc(midnight - timedelta(days=94)),
                    dt_util.as_utc(midnight), {entity_id}, "hour", {"volume": "m³"}, {"change"})
                self.rows = result.get(entity_id, [])
                self.records = daily_records(self.rows, now)
                self.statistics_status = "Recorder queried successfully"
            except Exception:
                self.statistics_status = "Recorder unavailable — cached history may be incomplete"
        return self.values()

    def values(self):
        now = dt_util.now()
        ledger, options = self.monitor.ledger, self.entry.options
        live = ledger.live(now, options)
        today = decode(self.monitor.data or {}, "water_today") if self.monitor.last_update_success else None
        result, self.usable = usage_summary(self.rows, now, ledger, today, self.records)
        result.update(live, statistics_status=self.statistics_status)
        last = ledger.last_success or ledger.started or now.timestamp()
        result["offline_minutes"] = max(0, now.timestamp() - last) / 60
        result["monitor_offline"] = result["offline_minutes"] >= options.get("offline_minutes", 5)
        if self.monitor.last_update_success:
            data = self.monitor.data or {}
            protection = decode(data, "protection")
            valve = decode(data, "valve_position")
            result.update(device_leak_alarm=decode(data, "leak_alarm"), device_leak_warning=decode(data, "leak_warning"),
                          protection_disabled=protection == "Disabled" if protection is not None else None,
                          valve_closed=valve == "Closed" if valve is not None else None,
                          device_fault=bool(decode(data, "faults")) if decode(data, "faults") is not None else None)
            group, smart, pro = decode(data, "mode_group"), decode(data, "smart_mode"), decode(data, "pro_mode")
            result["active_protection_mode"] = smart if group == "Automatic" else pro if group == "Advanced settings" else None
            result["protection_review"] = ("Device protection reported enabled; shutoff not physically tested" if protection == "Enabled"
                                            else "Device protection reported disabled" if protection == "Disabled" else "Protection state unknown")
        if result.get("usable_days_30", 0) >= 7 and today is not None and result.get("average_30", 0) > 0:
            threshold = max(options.get("high_daily_min_litres", 500), result["average_30"] * options.get("high_daily_multiplier", 2))
            result["high_daily_threshold"] = threshold
            result["high_daily_use"] = today * 1000 > threshold
        else:
            result["high_daily_use"] = None
        return result

    def sample(self, window):
        now = dt_util.now()
        return [v for d, v in self.usable.items() if now.date() - timedelta(days=window) <= d < now.date()]

    def handle_monitor_update(self):
        self.data = self.values()
        self.async_update_listeners()
