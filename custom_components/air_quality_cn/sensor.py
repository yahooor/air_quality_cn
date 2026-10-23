"""
Air Quality CN - Home Assistant 自定义集成
通过 air-quality.com 获取全球空气质量数据。

数据获取优先走站点 JSON 接口（读数/等级/花粉/历史/天气/预报），
接口异常时自动回退到 HTML 页面解析。
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfDensity,
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfSpeed,
    UV_INDEX,
    DEGREE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)

from . import api
from .const import (
    DOMAIN,
    CONF_PLACE,
    CONF_PLACE_NAME,
    CONF_STANDARD,
    CONF_SCAN_INTERVAL,
    CONF_LAT,
    CONF_LON,
    DEFAULT_STANDARD,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# 附近数据（天气/预报/首要污染物）缓存时长（秒）
NEARBY_CACHE_TTL = 3 * 3600

# 花粉传感器 key 集合（非花粉季值为 None 属正常，视为"可用但无数据"）
POLLEN_KEYS = {
    "pollen", "pollen_max", "pollen_total", "pollen_birch", "pollen_grass",
    "pollen_alder", "pollen_olive", "pollen_ragweed",
    "pollen_mugwort", "allergy_risk",
}

# 天气图标代码 → mdi
WEATHER_ICON_MAP = {
    "clear": "mdi:weather-sunny",
    "nt_clear": "mdi:weather-night-clear",
    "partly_cloudy": "mdi:weather-partly-cloudy",
    "nt_partly_cloudy": "mdi:weather-night-partly-cloudy",
    "cloudy": "mdi:weather-cloudy",
    "overcast": "mdi:weather-cloudy",
    "rain": "mdi:weather-rainy",
    "light_rain": "mdi:weather-rainy",
    "heavy_rain": "mdi:weather-pouring",
    "snow": "mdi:weather-snowy",
    "sleet": "mdi:weather-snowy-rain",
    "fog": "mdi:weather-fog",
    "mist": "mdi:weather-fog",
    "haze": "mdi:weather-hazy",
    "thunderstorm": "mdi:weather-lightning",
    "wind": "mdi:weather-windy",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    place = entry.data[CONF_PLACE]
    place_id = place.strip("/").split("/")[-1]
    place_name = entry.data.get(CONF_PLACE_NAME, place)
    standard = entry.options.get(
        CONF_STANDARD, entry.data.get(CONF_STANDARD, DEFAULT_STANDARD)
    )
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    coordinator = AirQualityCoordinator(
        hass, entry, place, place_id, place_name, standard, scan_interval
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("首次数据刷新失败: %s，仍将创建实体。", e)

    # (key, 显示名, 单位, device_class, state_class, icon)
    sensor_defs = [
        ("aqi",             "AQI",                         None,                                     SensorDeviceClass.AQI,              SensorStateClass.MEASUREMENT, "mdi:air-filter"),
        ("level",           "空气质量等级",                  None,                                     None,                               None,                         "mdi:numeric"),
        ("primary_pollutant", "首要污染物",                  None,                                     None,                               None,                         "mdi:filter-variant"),
        ("aqi_trend",       "24小时AQI趋势",                 None,                                     None,                               None,                         "mdi:trending-neutral"),
        ("pm25",            "PM2.5",                        UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM25,             SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("pm10",            "PM10",                         UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM10,             SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("o3",              "臭氧 O3",                      UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.OZONE,            SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("no2",             "二氧化氮 NO2",                   UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.NITROGEN_DIOXIDE, SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("co",              "一氧化碳 CO",                   UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.CARBON_MONOXIDE,  SensorStateClass.MEASUREMENT, "mdi:molecule-co"),
        ("so2",             "二氧化硫 SO2",                  UnitOfDensity.MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.SULPHUR_DIOXIDE,  SensorStateClass.MEASUREMENT, "mdi:smog"),
        # 花粉（花粉季之外均为 None，属正常）
        ("pollen",          "花粉浓度",                      None,                                     None,                               None,                         "mdi:flower-pollen"),
        ("pollen_max",      "花粉浓度范围最大值",             None,                                     None,                               SensorStateClass.MEASUREMENT, "mdi:chart-line"),
        ("pollen_birch",    "桦木花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:sprout"),
        ("pollen_grass",    "草花粉",                        "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:grass"),
        ("pollen_alder",    "桤木花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:flower"),
        ("pollen_olive",    "橄榄树花粉",                    "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:tree"),
        ("pollen_ragweed",  "豚草花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:weed"),
        ("pollen_mugwort",  "艾蒿花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:flower-tulip"),
        ("allergy_risk",    "过敏风险指数",                  None,                                     None,                               SensorStateClass.MEASUREMENT, "mdi:allergy"),
        # 天气
        ("weather_condition", "天气状况",                    None,                                     None,                               None,                         "mdi:weather-cloudy"),
        ("temperature",     "温度",                          UnitOfTemperature.CELSIUS,                SensorDeviceClass.TEMPERATURE,      SensorStateClass.MEASUREMENT, "mdi:thermometer"),
        ("feel_like",       "体感温度",                      UnitOfTemperature.CELSIUS,                SensorDeviceClass.TEMPERATURE,      SensorStateClass.MEASUREMENT, "mdi:thermometer-lines"),
        ("humidity",        "湿度",                          PERCENTAGE,                               SensorDeviceClass.HUMIDITY,         SensorStateClass.MEASUREMENT, "mdi:water-percent"),
        ("wind_speed",      "风速",                          UnitOfSpeed.KILOMETERS_PER_HOUR,          SensorDeviceClass.WIND_SPEED,       SensorStateClass.MEASUREMENT, "mdi:weather-windy"),
        ("wind_direction",  "风向",                          None,                                     None,                               None,                         "mdi:compass"),
        ("wind_degrees",    "风向角度",                      DEGREE,                                   None,                               SensorStateClass.MEASUREMENT, "mdi:angle-acute"),
        ("uv_index",        "紫外线指数",                    UV_INDEX,                                 None,                               SensorStateClass.MEASUREMENT, "mdi:weather-sunny"),
        ("update_time",     "数据更新时间",                  None,                                     SensorDeviceClass.TIMESTAMP,        None,                         "mdi:clock"),
    ]

    entities = [
        AirQualitySensor(coordinator, key, name, unit, device_class, state_class, icon, place, place_name)
        for key, name, unit, device_class, state_class, icon in sensor_defs
    ]
    async_add_entities(entities)
    _LOGGER.info("已创建 %d 个传感器, 地点: %s", len(entities), place_name)


class AirQualityCoordinator(DataUpdateCoordinator):
    """JSON 接口主路径 + HTML 回退的数据协调器。"""

    def __init__(self, hass, entry, place, place_id, place_name, standard, scan_interval):
        self.place = place
        self.place_id = place_id
        self.place_name = place_name
        self.standard = standard
        self._entry_id = entry.entry_id
        store = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
        self._lat = entry.data.get(CONF_LAT) or store.get("lat")
        self._lon = entry.data.get(CONF_LON) or store.get("lon")
        self._nearby_cache = (0.0, {})
        super().__init__(
            hass,
            _LOGGER,
            name="air_quality_cn",
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _resolve_coords(self, session):
        """旧配置条目缺坐标：按 place_name 搜索并精确匹配 place_id。"""
        store = self.hass.data.setdefault(DOMAIN, {}).setdefault(self._entry_id, {})
        if store.get("lat"):
            self._lat, self._lon = store["lat"], store["lon"]
            return
        try:
            lat, lon = await api.resolve_coords(session, self.place_id, self.place_name)
        except api.ApiError as e:
            _LOGGER.warning("坐标解析失败（本次使用 HTML 回退）: %s", e)
            return
        if lat is not None and lon is not None:
            self._lat, self._lon = lat, lon
            store.update({"lat": lat, "lon": lon})
            _LOGGER.info("已解析地点 %s 坐标: (%s, %s)", self.place_name, lat, lon)

    async def _nearby_data(self, session):
        """附近数据（天气/预报/首要污染物），带 TTL 缓存。"""
        ts, cached = self._nearby_cache
        now = time.monotonic()
        if now - ts < NEARBY_CACHE_TTL:
            return cached
        payload = await api.fetch_nearby(session, self._lat, self._lon, self.standard)
        parsed = api.parse_nearby(payload)
        self._nearby_cache = (now, parsed)
        return parsed

    async def _async_update_data(self):
        session = async_get_clientsession(self.hass)
        data = {}

        # ── 主路径：JSON 接口 ────────────────────────────────
        if self._lat is None or self._lon is None:
            await self._resolve_coords(session)

        if self._lat is not None and self._lon is not None:
            try:
                row = await api.fetch_map_row(session, self._lat, self._lon, self.standard, self.place_id)
                if row is not None:
                    data.update(api.parse_place_row(row))
            except api.ApiError as e:
                _LOGGER.warning("地图数据接口失败: %s", e)

            if data:
                # 历史数据：精确更新时间 + 趋势（失败不致命）
                try:
                    hist = await api.fetch_history(session, self.place_id, self.standard)
                    summary = api.summarize_history(api.parse_history(hist))
                    data.update(summary)
                except api.ApiError as e:
                    _LOGGER.debug("历史数据接口失败: %s", e)

                # 附近数据：天气/首要污染物/预报（带缓存，失败不致命）
                try:
                    nearby = await self._nearby_data(session)
                    data.update(nearby)
                except api.ApiError as e:
                    _LOGGER.debug("附近数据接口失败: %s", e)

                if data.get("update_time") is None and data.get("nearby_update_time"):
                    data["update_time"] = data.pop("nearby_update_time")

        # ── 回退路径：HTML 页面解析 ──────────────────────────
        if not data:
            _LOGGER.info("JSON 接口无数据，回退 HTML 页面解析: %s", self.place)
            try:
                html = await api.fetch_html(session, self.place, self.standard)
                data = api.parse_html(html)
            except api.SkeletonPageError as e:
                raise UpdateFailed(str(e)) from e
            except api.ApiError as e:
                raise UpdateFailed(str(e)) from e

        if not data:
            raise UpdateFailed("未获取到任何数据")

        # 健康警告：除 update_time 外全为空，多半是页面/接口结构变化
        if all(v is None for k, v in data.items() if k != "update_time"):
            _LOGGER.warning("所有解析字段均为空，请检查站点结构是否变化。place: %s", self.place)

        return data


class AirQualitySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit, device_class, state_class, icon, place, place_name):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._place = place
        self._place_name = place_name
        safe_place = place.replace("/", "_")
        self._attr_unique_id = f"air_quality_cn_{safe_place}_{key}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {(DOMAIN, place)},
            "name": f"在意空气 {place_name}",
            "manufacturer": "在意空气",
            "model": "站点数据接口",
        }

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self._key)
        if self._key == "update_time":
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return None
        return value

    @property
    def icon(self):
        data = self.coordinator.data or {}
        if self._key == "aqi_trend":
            return {
                "上升": "mdi:trending-up",
                "下降": "mdi:trending-down",
            }.get(data.get("aqi_trend"), "mdi:trending-neutral")
        if self._key == "weather_condition":
            return WEATHER_ICON_MAP.get(str(data.get("weather_icon") or ""), self._attr_icon)
        return self._attr_icon

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        attrs = {}
        level = data.get(f"{self._key}_level")
        if level is not None:
            attrs["level"] = level
        if self._key == "aqi":
            for src, dst in (
                ("aqi_trend", "trend"),
                ("trend_delta", "trend_delta"),
                ("aqi_avg_24h", "avg_24h"),
                ("aqi_max_24h", "max_24h"),
                ("primary_pollutant", "primary_pollutant"),
            ):
                if data.get(src) is not None:
                    attrs[dst] = data[src]
            if data.get("forecast"):
                attrs["forecast"] = data["forecast"]
        return attrs

    @property
    def available(self):
        if not self.coordinator.last_update_success:
            return False
        if self._key in POLLEN_KEYS:
            return True
        return (self.coordinator.data or {}).get(self._key) is not None
