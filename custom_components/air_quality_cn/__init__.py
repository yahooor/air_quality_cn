"""Air Quality CN - Home Assistant 自定义集成"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# 预导入平台模块：集成模块本身由 loader 在执行器线程导入，
# 在此处一并导入各平台可避免 async_forward_entry_setups 在事件循环内做磁盘导入
from . import sensor as _sensor  # noqa: F401  预导入，见上
from . import weather as _weather  # noqa: F401  预导入，见上
from .const import (
    DOMAIN,
    CONF_PLACE,
    CONF_PLACE_NAME,
    CONF_STANDARD,
    CONF_SCAN_INTERVAL,
    DEFAULT_STANDARD,
    DEFAULT_SCAN_INTERVAL,
)
from .sensor import AirQualityCoordinator

PLATFORMS = ["sensor", "weather"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # coordinator 在集成级创建，sensor/weather 两平台共享，避免平台加载竞态
    place = entry.data[CONF_PLACE]
    place_id = place.strip("/").split("/")[-1]
    place_name = entry.data.get(CONF_PLACE_NAME, place)
    standard = entry.options.get(
        CONF_STANDARD, entry.data.get(CONF_STANDARD, DEFAULT_STANDARD)
    )
    try:
        scan_interval = int(entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ))
    except (TypeError, ValueError):
        scan_interval = DEFAULT_SCAN_INTERVAL

    coordinator = AirQualityCoordinator(
        hass, entry, place, place_id, place_name, standard, scan_interval
    )
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("首次数据刷新失败: %s，仍将创建实体。", e)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """旧版本 entry 升级（新版 HA 中不得向 async_update_entry 传 version，
    返回 True 后 HA 自动将 entry 提升到流程当前 VERSION/MINOR_VERSION）。"""
    old_version = config_entry.version

    if old_version > 2:
        _LOGGER.error(
            "配置条目 %s 版本 %s 高于当前支持版本，可能由降级导致",
            config_entry.entry_id, old_version,
        )
        return False

    if old_version < 2:
        new_data = {**config_entry.data}
        if CONF_PLACE_NAME not in new_data:
            place = new_data.get("place", "")
            new_data[CONF_PLACE_NAME] = place.split("/")[-1] if place else "Unknown"
        if CONF_SCAN_INTERVAL not in new_data:
            new_data[CONF_SCAN_INTERVAL] = 30
        if CONF_STANDARD not in new_data:
            new_data[CONF_STANDARD] = "aqi_cn"
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    _LOGGER.info(
        "迁移完成 %s：版本 %s → 当前版本",
        config_entry.entry_id, old_version,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """选项更新后重新加载集成，使新的 scan_interval / standard 生效。"""
    await hass.config_entries.async_reload(entry.entry_id)
