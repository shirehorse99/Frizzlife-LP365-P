"""Indicative financial sensors, separate from device availability."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

SENSORS = {
    "daily_target": ("Daily water target", "L"),
    "daily_target_progress": ("Daily water target used", "%"),
    "daily_target_remaining": ("Water remaining against daily target", "L"),
    "target_basis": ("Daily target basis", None),
    "comparison_status": ("Meter comparison status", None),
    "tariff_status": ("Tariff update status", None),
    "tariff_valid_until": ("Tariff valid until", None),
    "tariff_last_checked": ("Tariff last checked", None),
    "sample_days": ("Meter comparison full days", "d"),
    "average_daily_litres": ("Comparison average daily water", "L/d"),
    "projected_annual_m3": ("Projected annual water use", "m³"),
    "current_annual_bill": ("Current annual unmetered bill", "GBP"),
    "projected_annual_cost": ("Estimated annual metered cost", "GBP"),
    "projected_monthly_cost": ("Estimated monthly metered cost", "GBP"),
    "projected_annual_saving": ("Estimated annual meter saving", "GBP"),
    "break_even_daily_litres": ("Meter break-even daily water", "L/d"),
    "today_metered_cost": ("Estimated metered cost today", "GBP"),
    "annual_standing": ("Metered annual standing charge", "GBP"),
    "water_rate": ("Metered water unit rate", "GBP/m³"),
    "sewer_rate": ("Metered sewerage unit rate", "GBP/m³"),
    "effective_rate": ("Metered combined effective rate", "GBP/m³"),
    "comparison_result": ("Meter comparison result", None),
    "scenario_lower_usage": ("Metered cost with lower usage", "GBP"),
    "scenario_higher_usage": ("Metered cost with higher usage", "GBP"),
    "scenario_tariff_rise": ("Metered cost with tariff increase", "GBP"),
    "scenario_rise_saving": ("Meter saving with tariff increase", "GBP"),
}


class ComparisonSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        name, unit = SENSORS[key]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{coordinator.entry.data['device_id']}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.data["device_id"])})
        if unit == "GBP":
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_suggested_display_precision = 2
        elif key == "tariff_last_checked":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif unit:
            self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        tariff = self.coordinator.tariff or {}
        return {"tariff_source": tariff.get("source"),
                "profile": self.coordinator.entry.options.get("tariff_profile", "welsh_standard"),
                "sewer_return_percent": tariff.get("return_percent"),
                "usage_scenario_percent": self.coordinator.entry.options.get("scenario_usage_percent", 20),
                "tariff_scenario_percent": self.coordinator.entry.options.get("scenario_tariff_percent", 10),
                "basis": "Recorded full hourly days, annualised to 365 days at current tariff; indicative only",
                "tariff_updates": "Daily checks of maintained GitHub catalogue; no official live feed"}
