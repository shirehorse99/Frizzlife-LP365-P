"""Read-only historical, quality, protection and notification summaries."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

SENSORS = {
    "water_yesterday": ("Usable recorded water yesterday", "L"),
    "recorded_week": ("Recorded water this week", "L"), "recorded_month": ("Recorded water this month", "L"),
    "average_7": ("Usable 7-day average water", "L/d"), "average_30": ("Usable 30-day average water", "L/d"),
    "average_90": ("Usable 90-day average water", "L/d"),
    "usable_days_7": ("Usable days in 7-day window", "d"), "usable_days_30": ("Usable days in 30-day window", "d"),
    "usable_days_90": ("Usable days in 90-day window", "d"),
    "history_progress_7": ("7-day history progress", "%"), "history_progress_30": ("30-day history progress", "%"),
    "history_progress_90": ("90-day history progress", "%"), "history_confidence": ("Usage history maturity", None),
    "coverage_today": ("Observed water coverage today", "%"), "coverage_24h": ("Observed water coverage last 24 hours", "%"),
    "coverage_week": ("Observed water coverage this week", "%"), "coverage_month": ("Observed water coverage this month", "%"),
    "tracking_hours": ("Observation history length", "h"), "offline_minutes": ("Minutes since successful local reading", "min"),
    "flow_run_minutes": ("Observed continuous flow duration", "min"), "night_flow_minutes": ("Observed night flow duration", "min"),
    "pressure_min_today": ("Observed minimum pressure today", "bar"),
    "pressure_max_today": ("Observed maximum pressure today", "bar"),
    "pressure_mean_today": ("Observed mean pressure today", "bar"),
    "high_daily_threshold": ("Unusual daily usage threshold", "L"),
    "statistics_status": ("Usage statistics status", None),
    "active_protection_mode": ("Active configured protection mode", None), "protection_review": ("Device shutoff review", None),
    "notification_status": ("Notification delivery status", None), "last_notification": ("Last water notification", None),
    "last_notification_time": ("Last water notification time", None),
}


class AnalyticsSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_name, self._attr_native_unit_of_measurement = SENSORS[key]
        self._attr_unique_id = f"{coordinator.entry.data['device_id']}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.data["device_id"])})
        if self._attr_native_unit_of_measurement:
            self._attr_suggested_display_precision = 2
        if self._attr_native_unit_of_measurement == "bar":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_suggested_unit_of_measurement = "bar"
        if key == "last_notification_time":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        if self.key.startswith("notification_") or self.key.startswith("last_notification"):
            return self.coordinator.monitor.notifications.values().get(self.key)
        return (self.coordinator.data or {}).get(self.key)

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        o = self.coordinator.entry.options
        result = {"basis": "Read-only observation; usable days need all expected hourly statistics, >=99% observed water coverage, no gap >90 seconds",
                  "flow_threshold_lph": o.get("flow_observation_lph", 5),
                  "sustained_minutes": o.get("sustained_minutes", 60), "overnight_minutes": o.get("overnight_minutes", 30),
                  "night_start_hour": o.get("night_start_hour", 0), "night_end_hour": o.get("night_end_hour", 6),
                  "physical_shutoff_tested": False}
        if self.key.startswith("last_notification") or self.key == "notification_status":
            result["recent_messages"] = self.coordinator.monitor.notifications.history
        return result
