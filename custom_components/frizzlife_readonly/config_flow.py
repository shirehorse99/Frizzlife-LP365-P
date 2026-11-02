"""UI configuration, validated with a status request only."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import DOMAIN
from .protocol import read_status


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if len(user_input["local_key"].encode()) != 16:
                errors["local_key"] = "invalid_key"
            else:
                await self.async_set_unique_id(user_input["device_id"].strip())
                self._abort_if_unique_id_configured()
                try:
                    await self.hass.async_add_executor_job(read_status, user_input)
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="FrizzLife Water Monitor", data=user_input)
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("host"): str,
            vol.Required("device_id"): str,
            vol.Required("local_key"): selector.TextSelector(selector.TextSelectorConfig(type="password")),
            vol.Required("protocol", default="3.5"): vol.In(["3.3", "3.4", "3.5"]),
            vol.Required("verified_volume", default=False): bool,
            vol.Optional("pressure_factor", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        }))
