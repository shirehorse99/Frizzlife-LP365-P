"""Local HA settings; these values never write device configuration."""
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.exceptions import HomeAssistantError
from .comparison import finite
from .const import DOMAIN

# name, minimum, maximum, step, default, unit
NUMBERS = {
    "daily_target_litres": ("Daily water target (0 uses meter break-even)", 0, 100000, 1, 0, "L"),
    "flow_observation_lph": ("Flow observation threshold", .1, 10000, .1, 5, "L/h"),
    "sustained_minutes": ("Sustained flow alert duration", 1, 1440, 1, 60, "min"),
    "overnight_minutes": ("Night flow alert duration", 1, 1440, 1, 30, "min"),
    "night_start_hour": ("Night window start hour", 0, 23, 1, 0, None),
    "night_end_hour": ("Night window end hour", 0, 23, 1, 6, None),
    "offline_minutes": ("Monitoring outage alert delay", 1, 60, 1, 5, "min"),
    "high_daily_min_litres": ("High daily use minimum", 1, 100000, 1, 500, "L"),
    "high_daily_multiplier": ("High daily use average multiplier", 1, 20, .1, 2, None),
    "pressure_low_bar": ("Low pressure alert limit", 0, 20, .1, 1, "bar"),
    "pressure_high_bar": ("High pressure alert limit", .1, 20, .1, 6, "bar"),
    "pressure_alert_minutes": ("Pressure alert duration", 1, 60, 1, 5, "min"),
    "annual_unmetered_bill": ("Annual unmetered bill", 0, 100000, .01, 0, "GBP"),
    "sewer_return_percent": ("Sewer return allowance", 0, 100, 1, 95, "%"),
    "scenario_usage_percent": ("Usage scenario change", 0, 100, 1, 20, "%"),
    "scenario_tariff_percent": ("Tariff rise scenario", 0, 200, 1, 10, "%"),
}
SWITCHES = {
    "notifications_enabled": ("Water notifications", False),
    "pressure_alerts_enabled": ("Pressure observations and alerts", False),
    "comparison_enabled": ("Water meter comparison", False),
    "auto_tariffs": ("Automatic tariff catalogue checks", True),
    "device_controls_enabled": ("Allow manual water valve commands", False),
}


def validate_setting(options, key, value):
    if key in NUMBERS:
        _, low, high, step, _, _ = NUMBERS[key]
        if not finite(value, low, high) or (step == 1 and value != int(value)):
            raise HomeAssistantError("Value outside the supported range")
    if key in SWITCHES and type(value) is not bool:
        raise HomeAssistantError("A boolean setting is required")
    result = {**options, key: value}
    if result.get("night_start_hour", 0) == result.get("night_end_hour", 6):
        raise HomeAssistantError("Night start and end hours must differ")
    if result.get("pressure_low_bar", 1) >= result.get("pressure_high_bar", 6):
        raise HomeAssistantError("Low pressure must be below high pressure")
    return result


class SettingEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, key, name):
        self.entry, self.key = entry, key
        self._attr_name = name
        self._attr_unique_id = f"{entry.data['device_id']}_setting_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.data["device_id"])})

    async def async_added_to_hass(self):
        self.async_on_remove(self.entry.add_update_listener(self._updated))

    async def _updated(self, hass, entry):
        self.async_write_ha_state()

    async def save(self, value):
        self.hass.config_entries.async_update_entry(self.entry,
            options=validate_setting(self.entry.options, self.key, value))
