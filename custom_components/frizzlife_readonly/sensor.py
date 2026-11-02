"""Reading-only sensor entities. No controls are registered."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from .entity import MonitorEntity

EXTRA_DIAGNOSTICS = {
    "mode_group": "Protection mode group",
    "smart_mode": "Configured smart mode", "pro_mode": "Configured pro mode",
    "mode4_time_raw": "Mode 4 alarm time raw", "mode5_time_raw": "Mode 5 alarm time raw",
    "mode6_time_raw": "Mode 6 alarm time raw",
    "mode4_flow_code": "Mode 4 flow threshold code", "mode5_flow_code": "Mode 5 flow threshold code",
    "mode6_flow_code": "Mode 6 flow threshold code", "low_flow_code": "Low-flow threshold code",
    "leak_duration_raw": "Leak-event duration raw", "leak_volume_raw": "Leak-event volume raw",
    "warning_duration_raw": "Warning-event duration raw", "warning_volume_raw": "Warning-event volume raw",
    "test_remaining_raw": "Test remaining time raw",
}

async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    entities = [Reading(c, "valve_position", "Valve position"),
                Reading(c, "protection", "Protection status"),
                Reading(c, "faults", "Reported fault bitmap"),
                Reading(c, "measurement_units", "Reported measurement units"),
                Reading(c, "pressure_raw", "Pressure raw reading"),
                Reading(c, "reported_104", "DP104 raw reading"),
                Reading(c, "last_poll", "Last successful local poll", device_class=SensorDeviceClass.TIMESTAMP)]
    if entry.data.get("pressure_factor"):
        entities.append(Reading(c, "pressure", "Water pressure", "psi", SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT))
    if entry.data.get("verified_volume"):
        entities.extend([
            Reading(c, "water_today", "Water used today", "m³", SensorDeviceClass.WATER, SensorStateClass.TOTAL_INCREASING),
            Reading(c, "flow", "Water flow", "L/h", SensorDeviceClass.VOLUME_FLOW_RATE, SensorStateClass.MEASUREMENT),
        ])
    entities.extend(Reading(c, key, name) for key, name in EXTRA_DIAGNOSTICS.items())
    async_add_entities(entities)


class Reading(MonitorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit=None, device_class=None, state_class=None):
        super().__init__(coordinator, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        if key in EXTRA_DIAGNOSTICS or key in ("pressure_raw", "measurement_units", "faults", "last_poll", "reported_104"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "water_today":
            self._attr_suggested_display_precision = 3

    @property
    def native_value(self):
        return self.reading
