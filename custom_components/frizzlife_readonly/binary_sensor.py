"""Leak warning/alarm status only."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .entity import MonitorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([LeakStatus(c, "leak_warning", "Leak warning"),
                        LeakStatus(c, "leak_alarm", "Leak alarm")])


class LeakStatus(MonitorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return self.reading
