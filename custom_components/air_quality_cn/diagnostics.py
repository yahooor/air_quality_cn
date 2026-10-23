"""Diagnostics 支持：导出配置与最新一次解析结果，便于远程排障。"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = store.get("coordinator")
    return {
        "entry": {
            "version": f"{entry.version}.{entry.minor_version}",
            "data": entry.data,
            "options": entry.options,
        },
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "data": coordinator.data if coordinator else None,
    }
