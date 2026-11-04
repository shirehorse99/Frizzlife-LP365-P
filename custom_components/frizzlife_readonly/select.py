"""Runtime phone destinations and comparison window."""
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from .settings import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SettingSelect(entry, "phone_notify_service", "Water alert phone"),
                        SettingSelect(entry, "comparison_days", "Comparison history window")])

class SettingSelect(SettingEntity, SelectEntity):
    @property
    def options(self):
        if self.key == "comparison_days":
            return ["7", "30", "90"]
        services = sorted(n for n in self.hass.services.async_services().get("notify", {}) if n.startswith("mobile_app_"))
        current = self.entry.options.get(self.key, "none")
        return ["none"] + sorted(set(services + ([current] if current != "none" else [])))
    @property
    def current_option(self):
        return str(self.entry.options.get(self.key, 30 if self.key == "comparison_days" else "none"))
    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unsupported selection")
        await self.save(int(option) if self.key == "comparison_days" else option)
