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
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    DEGREE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_PLACE, CONF_STANDARD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

POLLUTANT_NAMES = ["PM2.5", "PM10", "O3", "NO2", "CO", "SO2"]
WIND_DIRECTIONS = [
    "北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
    "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北",
]

NUM_PATTERN = r"(\d+(?:\.\d+)?)"


def _to_float(value, default=None):
    """Safely convert a value to float, return default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_int(value, default=None):
    """Safely convert a value to int, return default on failure."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    place = entry.data[CONF_PLACE]
    standard = entry.data[CONF_STANDARD]
    # 优先从 options 取，其次从 data 取，最后用默认值
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    url = f"https://air-quality.com/place/{place}?lang=zh-Hans&standard={standard}"
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
        ("co", "一氧化碳 CO", CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:molecule-co"),
        ("so2", "二氧化硫 SO2", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorStateClass.MEASUREMENT, "mdi:smog"),
        ("pollen", "花粉浓度", None, None, None, "mdi:flower-pollen"),
        ("pollen_max", "花粉浓度最大值", "粒/千平方毫米", None, SensorStateClass.MEASUREMENT, "mdi:chart-line"),
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
                AirQualitySensor(coordinator, key, name, unit, device_class, state_class, icon, place)
            )
        async_add_entities(entities)
        _LOGGER.info("已创建 %d 个传感器, 地点: %s", len(entities), place)
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

        # 兼容单引号和双引号的正则辅助
        _q = r"""['"]"""  # 匹配 ' 或 "

        # AQI — 网站已改版，数据在 JS 的 Gauge() 初始化里，不再是 HTML 文本
        aqi_match = re.search(r"Gauge\([\s\S]+?value:\s*(\d+)\s*\}", html)
        if not aqi_match:
            # 备选：从 meta description 提取（格式如 "AQI (美国标准) 70 中等"）
            aqi_match = re.search(r"AQI \((?:美国|中国)标准\)\s*(\d+)", html)
        data["aqi"] = _to_int(aqi_match.group(1)) if aqi_match else None

        # 等级
        level_match = re.search(r"(优|良|中等|轻度污染|中度污染|重度污染|严重污染)", html)
        data["level"] = level_match.group(1) if level_match else None

        # 污染物 — 兼容单/双引号
        for name in POLLUTANT_NAMES:
            match = re.search(
                rf"<div class={_q}name{_q}>{re.escape(name)}</div>.*?<div class={_q}value{_q}>{NUM_PATTERN}</div>",
                html, re.DOTALL
            )
            key = name.lower().replace(".", "")
            # CO 的值是 mg/m³ 量级（如 0.8），需要 float；其他污染物是整数
            if key == "co":
                data[key] = _to_float(match.group(1)) if match else None
            else:
                data[key] = _to_int(match.group(1)) if match else None

        # 花粉
        pollen_match = re.search(rf"<div class={_q}name{_q}>花粉</div>.*?<div class={_q}value{_q}>([^<]+)</div>", html, re.DOTALL)
        pollen = pollen_match.group(1).strip() if pollen_match else None
        data["pollen"] = pollen

        # 花粉最大值
        pollen_max = None
        if pollen:
            range_match = re.search(r"(\d+)~(\d+)", pollen)
            if range_match:
                pollen_max = int(range_match.group(2))
            else:
                single_match = re.search(r"(\d+)", pollen)
                if single_match:
                    pollen_max = int(single_match.group(1))
        data["pollen_max"] = pollen_max

        # 更新时间（返回 UTC datetime 对象，HA 负责按用户时区显示）
        update_time = None
        time_match = re.search(r'<div[^>]*update-time[^>]*>\s*([\d\-: T]+)\s*</div>', html)
        if time_match:
            raw_time = time_match.group(1).strip()
            try:
                # 网站返回的通常是北京时间，解析后标记为 UTC+8 再转 UTC
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

        # 风向 & UV
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
        data["uv_index"] = uv  # None if no data, numeric if available

        all_none = all(v is None for v in data.values())
        if all_none:
            _LOGGER.warning("所有解析字段均为空，请检查网页结构是否变化。地点: %s", self.url)
        return data


class AirQualitySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit, device_class, state_class, icon, place):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        safe_place = place.replace("/", "_")
        self._attr_unique_id = f"air_quality_cn_{safe_place}_{key}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {(DOMAIN, place)},
            "name": f"在意空气 {place}",
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
                    dt = datetime.fromisoformat(value)
                    return dt
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
