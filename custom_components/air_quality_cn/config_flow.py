import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, DEFAULT_PLACE, DEFAULT_STANDARD, DEFAULT_SCAN_INTERVAL, STANDARDS, CONF_PLACE, CONF_STANDARD, CONF_SCAN_INTERVAL

class AirQualityCNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if not user_input[CONF_PLACE].strip():
                errors[CONF_PLACE] = "invalid_place"
            if not errors:
                return self.async_create_entry(
                    title=f"在意空气 ({user_input[CONF_PLACE]})",
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required(CONF_PLACE, default=DEFAULT_PLACE): str,
            vol.Required(CONF_STANDARD, default=DEFAULT_STANDARD): vol.In(STANDARDS),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=1)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AirQualityCNOptionsFlow(config_entry)


class AirQualityCNOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # 优先从 options 取，其次从 data 取，最后用默认值
        options = self.config_entry.options
        data = self.config_entry.data
        current_interval = options.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        schema = vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(int, vol.Range(min=1)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
