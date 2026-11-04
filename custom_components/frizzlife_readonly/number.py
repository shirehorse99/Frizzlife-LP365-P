"""Editable local observation and comparison settings."""
from homeassistant.components.number import NumberEntity, NumberMode
from .settings import SettingEntity, NUMBERS

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(SettingNumber(entry, k) for k in NUMBERS)

class SettingNumber(SettingEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    def __init__(self, entry, key):
        name, low, high, step, self.default, unit = NUMBERS[key]
        super().__init__(entry, key, name)
        self._attr_native_min_value, self._attr_native_max_value = low, high
        self._attr_native_step, self._attr_native_unit_of_measurement = step, unit
    @property
    def native_value(self):
        return self.entry.options.get(self.key, self.default)
    async def async_set_native_value(self, value):
        await self.save(value)
