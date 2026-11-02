"""Shared read-only entity properties."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .readings import decode


class MonitorEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        device_id = coordinator.entry.data["device_id"]
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)},
            name="FrizzLife Water Monitor", manufacturer="FrizzLife", model="LP365-P")

    @property
    def reading(self):
        if self.key == "last_poll":
            return self.coordinator.last_poll
        return decode(self.coordinator.data or {}, self.key,
                      self.coordinator.entry.data.get("pressure_factor"))

    @property
    def available(self):
        return super().available and self.reading is not None
