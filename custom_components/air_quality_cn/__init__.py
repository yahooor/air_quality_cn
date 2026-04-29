import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 当前版本，用于迁移判断
CURRENT_VERSION = "2.4.4"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # 检查是否需要迁移
    if entry.version != CURRENT_VERSION:
        # 进行数据迁移
        await _migrate_entry(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def _migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """迁移旧版本配置到新版本"""
    from .const import CONF_PLACE, CONF_PLACE_NAME, CONF_STANDARD, CONF_SCAN_INTERVAL

    # 如果没有版本信息，设置为当前版本并添加默认值
    new_data = {**entry.data}

    # 确保必要字段存在
    if CONF_PLACE_NAME not in new_data:
        # 从 place 字段提取名称
        place = new_data.get(CONF_PLACE, "")
        new_data[CONF_PLACE_NAME] = place.split("/")[-1] if place else "Unknown"

    # 添加默认刷新间隔
    if CONF_SCAN_INTERVAL not in new_data:
        new_data[CONF_SCAN_INTERVAL] = 30  # 默认 30 分钟

    # 更新版本号
    entry.version = CURRENT_VERSION
    hass.config_entries.async_update_entry(entry, data=new_data)
    _LOGGER.info("Migrated %s from version %s to %s", entry.entry_id, entry.version, CURRENT_VERSION)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration so new scan_interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
