"""Air Quality CN - Home Assistant 自定义集成"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """HA 标准迁移函数：处理旧版本 entry 升级到当前 VERSION/MINOR_VERSION。"""
    from .const import CONF_PLACE, CONF_PLACE_NAME, CONF_STANDARD, CONF_SCAN_INTERVAL

    old_version = config_entry.version
    old_minor = config_entry.minor_version

    _LOGGER.debug(
        "迁移配置条目 %s，当前版本 %s.%s",
        config_entry.entry_id, old_version, old_minor,
    )

    # 防止降级：版本号大于当前 → 拒绝
    if old_version > 2:
        _LOGGER.error(
            "配置条目 %s 版本 %s 高于当前支持版本，可能由降级导致",
            config_entry.entry_id, old_version,
        )
        return False

    new_data = {**config_entry.data}

    # ── 版本 1 → 2：补充缺失字段 ──────────────────────────
    if old_version < 2:
        # 补充 place_name
        if CONF_PLACE_NAME not in new_data:
            place = new_data.get(CONF_PLACE, "")
            new_data[CONF_PLACE_NAME] = place.split("/")[-1] if place else "Unknown"

        # 补充 scan_interval
        if CONF_SCAN_INTERVAL not in new_data:
            new_data[CONF_SCAN_INTERVAL] = 30

        # 补充 standard
        if CONF_STANDARD not in new_data:
            new_data[CONF_STANDARD] = "aqi_cn"

    # ── 次版本 0 → 1：（预留，当前无额外变更）──────────────
    # if old_minor < 1:
    #     pass

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        version=2,
        minor_version=1,
    )

    _LOGGER.info(
        "迁移完成 %s：%s.%s → 2.1",
        config_entry.entry_id, old_version, old_minor,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """选项更新后重新加载集成，使新的 scan_interval 生效。"""
    await hass.config_entries.async_reload(entry.entry_id)
