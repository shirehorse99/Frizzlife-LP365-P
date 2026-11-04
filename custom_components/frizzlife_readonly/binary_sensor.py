"""Read-only leak, reported fault and protection status."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from .entity import MonitorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    entities = [LeakStatus(c, "leak_warning", "Leak warning"),
                LeakStatus(c, "leak_alarm", "Leak alarm")]
    for key, name in {
        "fault_power": "Reported power failure", "fault_empty_pipe": "Reported empty pipe",
        "fault_backflow": "Reported reverse flow", "fault_overrange": "Reported over-range fault",
        "fault_temperature": "Reported temperature fault", "fault_hardware": "Reported hardware fault",
        "fault_valve_stuck": "Reported stuck valve",
    }.items():
        entity = LeakStatus(c, key, name)
        entity._attr_entity_category = EntityCategory.DIAGNOSTIC
        entities.append(entity)
    entities.append(ProtectionStatus(c, "low_flow_enabled", "Low-flow protection enabled"))
    for key, name in {"monitoring_online": "Local monitoring connected", "monitor_offline": "Local monitoring outage",
                      "sustained_flow": "Sustained flow pattern", "overnight_flow": "Overnight flow pattern",
                      "high_daily_use": "Unusually high daily water use", "pressure_low": "Sustained low pressure", "pressure_high": "Sustained high pressure"}.items():
        entities.append(ObservationStatus(c.analytics, key, name))
    async_add_entities(entities)


class LeakStatus(MonitorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return self.reading


class ProtectionStatus(MonitorEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return self.reading


class ObservationStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.data['device_id']}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.data["device_id"])})
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY if key == "monitoring_online" else BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def available(self):
        return super().available and self.is_on is not None
