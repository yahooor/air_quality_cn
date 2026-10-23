"""Weather 平台：当前天气 + 48h 逐时 / 11 天每日预报。

数据来自 get_nearby_data 的 weather 对象与 weather_forecast 段
（经 sensor 平台同一个 coordinator 的 JSON 主路径刷新）。
"""
import logging

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import api
from .const import (
    DOMAIN,
    CONF_PLACE,
    CONF_PLACE_NAME,
)
from .sensor import AirQualityCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    coordinator = store.get("coordinator")
    if coordinator is None:
        return
    place = entry.data[CONF_PLACE]
    place_name = entry.data.get(CONF_PLACE_NAME, place)
    async_add_entities([AirQualityWeather(coordinator, place, place_name)])


class AirQualityWeather(CoordinatorEntity, WeatherEntity):
    """在意空气天气实体（复用 sensor 的 CoordinatorEntity 基类链）。"""

    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: AirQualityCoordinator, place: str, place_name: str):
        super().__init__(coordinator)
        self._place = place
        self._place_name = place_name
        self._attr_unique_id = f"air_quality_cn_{place.replace('/', '_')}_weather"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, place)},
            "name": f"在意空气 {place_name}",
            "manufacturer": "在意空气",
            "model": "站点数据接口",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def condition(self) -> str | None:
        data = self.coordinator.data or {}
        return api.weather_condition(
            data.get("weather_icon"), data.get("weather_condition")
        )

    @property
    def native_temperature(self) -> float | None:
        return (self.coordinator.data or {}).get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        return (self.coordinator.data or {}).get("feel_like")

    @property
    def humidity(self) -> float | None:
        return (self.coordinator.data or {}).get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        return (self.coordinator.data or {}).get("wind_speed")

    @property
    def wind_bearing(self) -> float | None:
        return (self.coordinator.data or {}).get("wind_degrees")

    @property
    def uv_index(self) -> float | None:
        return (self.coordinator.data or {}).get("uv_index")

    @property
    def native_precipitation_unit(self) -> str:
        return "mm"

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return (self.coordinator.data or {}).get("wf_daily") or None

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        return (self.coordinator.data or {}).get("wf_hourly") or None
