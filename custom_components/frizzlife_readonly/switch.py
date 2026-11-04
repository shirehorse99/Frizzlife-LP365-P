"""Local HA feature switches. Switching on does not command the monitor."""
from homeassistant.components.switch import SwitchEntity
from .settings import SettingEntity, SWITCHES

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(SettingSwitch(entry, k) for k in SWITCHES)

class SettingSwitch(SettingEntity, SwitchEntity):
    def __init__(self, entry, key):
        name, self.default = SWITCHES[key]
        super().__init__(entry, key, name)
    @property
    def is_on(self):
        return self.entry.options.get(self.key, self.default)
    async def async_turn_on(self, **kwargs):
        await self.save(True)
    async def async_turn_off(self, **kwargs):
        await self.save(False)
