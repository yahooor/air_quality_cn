"""
Updated sensor.py - supports country-level and all place levels
Key changes:
- URL builder handles both /country/ and /place/ URLs
- Added aqi_au standard support
- Fixed CO unit (μg/m³ not mg/m³)
- Updated AQI Gauge regex
- Level regex includes "中等"
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfSpeed,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_PLACE, CONF_PLACE_NAME, CONF_STANDARD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

POLLUTANT_NAMES = ["PM2.5", "PM10", "O3", "NO2", "CO", "SO2"]
WIND_DIRECTIONS = [
    "北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
    "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北",
]

NUM_PATTERN = r"(\d+(?:\.\d+)?)"


def _to_float(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_int(value, default=None):
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _build_url(place, standard):
    """Build the full URL from place string and standard.
    
    Place formats:
    - 'china/haidian/7d638731' -> /place/china/haidian/7d638731
    - 'china//7d638731' -> /place/china//7d638731 (district with no city name)
    - 'japan/48e5965c' -> /country/japan/48e5965c (country-level, 2 segments)
    """
    parts = place.strip("/").split("/")
    if len(parts) == 2:
        # Country level: {country_url_key}/{country_id}
        return f"https://air-quality.com/country/{place}?lang=zh-Hans&standard={standard}"
    else:
        # Region/City/District level: {country}/{name}/{id}
        return f"https://air-quality.com/place/{place}?lang=zh-Hans&standard={standard}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    place = entry.data[CONF_PLACE]
    standard = entry.data.get(CONF_STANDARD, "aqi_cn")
    place_name = entry.data.get(CONF_PLACE_NAME, place)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    url = _build_url(place, standard)
    coordinator = AirQualityCoordinator(hass, url, scan_interval)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("首次数据刷新失败: %s，仍将创建实体。", e)

    entities = []
    sensor_defs = [
        ("aqi", "AQI", None, SensorDeviceClass.AQI, SensorStateClass.MEASUREMENT, "mdi:air-filter"),
        ("level", "空气质量等级", None, None, None, "mdi:numeric"),
        ("pm25", "PM2.5", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM25, SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("pm10", "PM10", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorDeviceClass.PM10, SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("o3", "臭氧 O3", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("no2", "二氧化氮 NO2", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("co", "一氧化碳 CO", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:molecule-co"),
        ("so2", "二氧化硫 SO2", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:smog"),
        ("pollen", "花粉浓度", None, None, None, "mdi:flower-pollen"),
        ("pollen_max", "花粉浓度最大值", "粒/千平方毫米", None, SensorStateClass.MEASUREMENT, "mdi:chart-line"),
        ("pollen_birch", "桦木花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:sprout"),
        ("pollen_grass", "草花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:grass"),
        ("pollen_alder", "桤木花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:flower"),
        ("pollen_olive", "橄榄树花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:tree"),
        ("pollen_ragweed", "豚草花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:weed"),
        ("pollen_mugwort", "艾蒿花粉", "粒/m³", None, SensorStateClass.MEASUREMENT, "mdi:flower-tulip"),
        ("allergy_risk", "过敏风险指数", None, None, SensorStateClass.MEASUREMENT, "mdi:allergy"),
        ("temperature", "温度", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer"),
        ("humidity", "湿度", PERCENTAGE, SensorDeviceClass.HUMIDITY, SensorStateClass.MEASUREMENT, "mdi:water-percent"),
        ("wind_speed", "风速", UnitOfSpeed.KILOMETERS_PER_HOUR, SensorDeviceClass.WIND_SPEED, SensorStateClass.MEASUREMENT, "mdi:weather-windy"),
        ("wind_direction", "风向", None, None, None, "mdi:compass"),
        ("wind_degrees", "风向角度", DEGREE, None, SensorStateClass.MEASUREMENT, "mdi:angle-acute"),
        ("uv_index", "紫外线指数", "UVI", None, SensorStateClass.MEASUREMENT, "mdi:sunglasses"),
        ("update_time", "数据更新时间", None, SensorDeviceClass.TIMESTAMP, None, "mdi:clock"),
    ]

    try:
        for key, name, unit, device_class, state_class, icon in sensor_defs:
            entities.append(
                AirQualitySensor(coordinator, key, name, unit, device_class, state_class, icon, place, place_name)
            )
        async_add_entities(entities)
        _LOGGER.info("已创建 %d 个传感器, 地点: %s", len(entities), place_name)
    except Exception as e:
        _LOGGER.exception("创建传感器失败: %s", e)
        raise


class AirQualityCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, url, scan_interval):
        self.url = url
        super().__init__(
            hass,
            _LOGGER,
            name="air_quality_cn",
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self):
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self.url, timeout=30) as resp:
                html = await resp.text()
        except Exception as e:
            _LOGGER.error("请求失败: %s", e)
            raise

        _LOGGER.debug("成功获取网页，长度: %d 字符", len(html))
        data = {}

        _q = r"""['"]"""

        # AQI — from JS Gauge() initialization
        aqi_match = re.search(r"Gauge\([\s\S]+?value:\s*(\d+)\s*\}", html)
        if not aqi_match:
            aqi_match = re.search(r"AQI \((?:美国|中国|澳大利亚)标准\)\s*(\d+)", html)
        data["aqi"] = _to_int(aqi_match.group(1)) if aqi_match else None

        # 等级 — includes "中等" for aqi_us moderate
        level_match = re.search(r"(优|良|中等|轻度污染|中度污染|重度污染|严重污染)", html)
        data["level"] = level_match.group(1) if level_match else None

        # 污染物
        for name in POLLUTANT_NAMES:
            match = re.search(
                rf"<div class={_q}name{_q}>{re.escape(name)}</div>.*?<div class={_q}value{_q}>{NUM_PATTERN}</div>",
                html, re.DOTALL
            )
            key = name.lower().replace(".", "")
            # CO is also in μg/m³ on the website (e.g., 600 μg/m³), not mg/m³
            data[key] = _to_float(match.group(1)) if match else None

        # 花粉
        pollen_match = re.search(rf"<div class={_q}name{_q}>花粉</div>.*?<div class={_q}value{_q}>([^<]+)</div>", html, re.DOTALL)
        pollen = pollen_match.group(1).strip() if pollen_match else None
        data["pollen"] = pollen

        pollen_max = None
        if pollen:
            range_match = re.search(r"(\d+)~(\d+)", pollen)
            if range_match:
                pollen_max = int(range_match.group(2))
            else:
                single_match = re.search(r"(\d+(?:\.\d+)?)", pollen)
                if single_match:
                    pollen_max = _to_float(single_match.group(1))
        data["pollen_max"] = pollen_max

        # 更新时间
        update_time = None
        time_match = re.search(r'<div[^>]*update-time[^>]*>\s*([\d\-: T]+)\s*</div>', html)
        if time_match:
            raw_time = time_match.group(1).strip()
            try:
                local_dt = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
                cst = timezone(timedelta(hours=8))
                update_time = local_dt.replace(tzinfo=cst).astimezone(timezone.utc)
            except ValueError:
                try:
                    dt = datetime.fromisoformat(raw_time)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                    update_time = dt.astimezone(timezone.utc)
                except Exception:
                    pass
        if not update_time:
            update_time = datetime.now(timezone.utc)
        data["update_time"] = update_time

        # 温度
        temp_match = re.search(rf"<div class={_q}temperature{_q}>(-?" + NUM_PATTERN + r")℃</div>", html)
        data["temperature"] = _to_float(temp_match.group(1)) if temp_match else None

        # 湿度
        hum_match = re.search(rf"<div class={_q}humidity{_q}>" + NUM_PATTERN + r"%</div>", html)
        data["humidity"] = _to_float(hum_match.group(1)) if hum_match else None

        # 风速
        wind_match = re.search(rf"<div class={_q}wind{_q}>" + NUM_PATTERN + r" kph</div>", html)
        data["wind_speed"] = _to_float(wind_match.group(1)) if wind_match else None

        # 风向 & UV from curWeatherData JS object
        wind_degrees = None
        wind_direction = None
        uv = None
        start_marker = "var curWeatherData = "
        start_idx = html.find(start_marker)
        if start_idx != -1:
            json_start = start_idx + len(start_marker)
            brace_count = 0
            json_end = -1
            for i in range(json_start, len(html)):
                if html[i] == "{":
                    brace_count += 1
                elif html[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            if json_end != -1:
                json_str = html[json_start:json_end].rstrip(";")
                try:
                    weather_data = json.loads(json_str)
                    if "wind_degrees" in weather_data:
                        wind_degrees = _to_float(weather_data["wind_degrees"])
                        if wind_degrees is not None:
                            idx = round(wind_degrees / 22.5) % 16
                            wind_direction = WIND_DIRECTIONS[idx]
                    uv = weather_data.get("UV") or weather_data.get("uv")
                    if uv is not None:
                        uv = _to_float(uv)
                except (json.JSONDecodeError, TypeError):
                    pass
        if uv is None:
            uv_match = re.search(rf"<div class={_q}uv{_q}>\s*" + NUM_PATTERN + r"\s+of\s+11\s*</div>", html)
            if uv_match:
                uv = _to_float(uv_match.group(1))
        data["wind_degrees"] = wind_degrees
        data["wind_direction"] = wind_direction
        data["uv_index"] = uv

        all_none = all(v is None for v in data.values())
        if all_none:
            _LOGGER.warning("所有解析字段均为空，请检查网页结构是否变化。URL: %s", self.url)
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
            "model": "网页抓取",
        }

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        if self._key == "update_time":
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except Exception:
                    return None
            return None
        return value

    @property
    def available(self):
        if not self.coordinator.last_update_success:
            return False
        value = self.coordinator.data.get(self._key)
        if self._key == "update_time":
            return value is not None
        return value is not None
