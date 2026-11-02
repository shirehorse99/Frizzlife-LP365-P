"""Read-only leak, reported fault and protection status."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from .entity import MonitorEntity


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
