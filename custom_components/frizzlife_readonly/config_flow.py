"""UI configuration, validated with a status request only."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN
from .protocol import read_status
from .comparison import PROFILES
from .comparison import finite
from homeassistant.util import dt as dt_util


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ComparisonOptionsFlow()

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


class ComparisonOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            for key, maximum in (("annual_unmetered_bill", 100000), ("sewer_return_percent", 100)):
                if not finite(user_input.get(key), 0, maximum):
                    errors["base"] = "invalid_number"
            if not errors:
                self.pending = {**self.config_entry.options, **user_input}
                if user_input["tariff_profile"] == "custom":
                    return await self.async_step_custom()
                return self.async_create_entry(title="", data=self.pending)
        o = self.config_entry.options
        return self.async_show_form(step_id="init", errors=errors, data_schema=vol.Schema({
            vol.Required("comparison_enabled", default=o.get("comparison_enabled", False)): bool,
            vol.Required("tariff_profile", default=o.get("tariff_profile", "welsh_standard")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[{"value": k, "label": v} for k, v in PROFILES.items()], mode="dropdown")),
            vol.Required("annual_unmetered_bill", default=o.get("annual_unmetered_bill", 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100000)),
            vol.Required("comparison_days", default=o.get("comparison_days", 30)): vol.In([7, 30, 90]),
            vol.Required("sewer_return_percent", default=o.get("sewer_return_percent", 95)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required("auto_tariffs", default=o.get("auto_tariffs", True)): bool,
        }))

    async def async_step_custom(self, user_input=None):
        errors = {}
        if user_input is not None:
            from datetime import date
            try:
                if date.fromisoformat(user_input["custom_valid_until"]) < dt_util.now().date():
                    raise ValueError
            except (TypeError, ValueError):
                errors["base"] = "invalid_tariff_date"
            for key, maximum in (("custom_water_rate", 20), ("custom_sewer_rate", 20), ("custom_standing", 2000)):
                if not finite(user_input.get(key), 0, maximum):
                    errors["base"] = "invalid_number"
            if not errors:
                return self.async_create_entry(title="", data={**self.pending, **user_input})
        o = self.config_entry.options
        return self.async_show_form(step_id="custom", errors=errors, data_schema=vol.Schema({
            vol.Required("custom_supplier", default=o.get("custom_supplier", "")): str,
            vol.Required("custom_water_rate", default=o.get("custom_water_rate", 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=20)),
            vol.Required("custom_sewer_rate", default=o.get("custom_sewer_rate", 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=20)),
            vol.Required("custom_standing", default=o.get("custom_standing", 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=2000)),
            vol.Required("custom_valid_until", default=o.get("custom_valid_until", "")): selector.DateSelector(),
        }))
