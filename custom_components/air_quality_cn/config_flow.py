"""
config_flow.py for air_quality_cn integration
支持搜索式地点查找，3 步完成配置：搜索 → 选择 → AQI 标准
"""
import voluptuous as vol
import logging
from urllib.parse import quote

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_STANDARD,
    DEFAULT_SCAN_INTERVAL,
    STANDARDS,
    CONF_PLACE,
    CONF_STANDARD,
    CONF_SCAN_INTERVAL,
    CONF_PLACE_NAME,
)

_LOGGER = logging.getLogger(__name__)


class AirQualityCNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self):
        self._search_results = []
        self._selected_place = None

    # ─── 入口：直接进入搜索 ────────────────────────────────
    async def async_step_user(self, user_input=None):
        """直接进入地点搜索步骤。"""
        return await self.async_step_search()

    # ─── Step 1：输入搜索关键词 ───────────────────────────
    async def async_step_search(self, user_input=None):
        errors = {}
        if user_input is not None:
            query = user_input.get("query", "").strip()
            if query:
                session = async_get_clientsession(self.hass)
                try:
                    url = f"https://air-quality.com/data/search_places?term={quote(query)}&lang=zh-Hans"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            results = await resp.json(content_type=None)
                            if results:
                                self._search_results = results[:50]
                                return await self.async_step_search_select()
                            errors["query"] = "no_results"
                        else:
                            errors["query"] = "search_failed"
                except Exception as e:
                    _LOGGER.error("搜索失败: %s", e)
                    errors["query"] = "search_failed"
            else:
                errors["query"] = "invalid_place"

        schema = vol.Schema({
            vol.Required("query"): str,
        })
        return self.async_show_form(
            step_id="search",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "hint": "输入城市、地区或监测站名称（支持中文或英文）"
            },
        )

    # ─── Step 2：从搜索结果中选择地点 ────────────────────
    async def async_step_search_select(self, user_input=None):
        if user_input is not None:
            selected = user_input.get("place_selection", "")
            try:
                idx = int(selected)
                if 0 <= idx < len(self._search_results):
                    self._selected_place = self._search_results[idx]
                    # 设置 unique_id 防止重复添加同一地点
                    place, _ = self._resolve_place_and_name()
                    await self.async_set_unique_id(f"air_quality_cn_{place}")
                    self._abort_if_unique_id_configured()
                    return await self.async_step_standard()
            except (ValueError, TypeError):
                pass
            # 解析失败，重新显示选择表单
            return self.async_show_form(
                step_id="search_select",
                data_schema=vol.Schema({
                    vol.Required("place_selection"): vol.In(self._build_search_options())
                }),
                errors={"place_selection": "invalid_selection"},
            )

        options = self._build_search_options()
        schema = vol.Schema({
            vol.Required("place_selection"): vol.In(options),
        })
        return self.async_show_form(step_id="search_select", data_schema=schema)

    # ─── Step 3：选择 AQI 标准 ────────────────────────────
    async def async_step_standard(self, user_input=None):
        if user_input is not None:
            standard = user_input.get("standard", DEFAULT_STANDARD)
            place, place_name = self._resolve_place_and_name()
            return self.async_create_entry(
                title=f"在意空气 ({place_name})",
                data={
                    CONF_PLACE: place,
                    CONF_PLACE_NAME: place_name,
                    CONF_STANDARD: standard,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        schema = vol.Schema({
            vol.Required("standard", default=DEFAULT_STANDARD): vol.In(STANDARDS),
        })
        return self.async_show_form(step_id="standard", data_schema=schema)

    # ─── 构建搜索结果选项 ─────────────────────────────
    def _build_search_options(self):
        """构建搜索结果选项列表。"""
        return {
            str(i): f"{r.get('name', '')} ({r.get('description', '')})"
            for i, r in enumerate(self._search_results)
        }

    # ─── 解析最终 place URL 和显示名称 ───────────────────
    def _resolve_place_and_name(self):
        """从搜索结果中解析 place 路径和显示名称。"""
        result = self._selected_place or {}
        url_key = result.get("url_key", "").strip("/")
        place_id = result.get("place_id", "").strip("/")
        if url_key and place_id:
            place = f"{url_key}/{place_id}"
        elif url_key:
            place = url_key
        elif place_id:
            place = place_id
        else:
            place = ""
        name = result.get("name", place)
        return place, name

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

        options = self.config_entry.options
        data = self.config_entry.data
        current_interval = options.get(
            CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        schema = vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(int, vol.Range(min=1)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
