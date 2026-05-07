"""
Air Quality CN - Home Assistant Custom Component
Supports air-quality.com data for any global location.

Features:
- Search-based location selection (supports Chinese/English)
- 8 AQI standards: CN, US, AU, CA, NL, EU, UK, IN
- 6 pollutants: PM2.5, PM10, O3, NO2, CO, SO2
- 8 pollen sensors + allergy risk index (available during pollen season)
- Weather: temperature, humidity, wind speed/direction, UV index
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta

import aiohttp

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity, UpdateFailed

from .const import DOMAIN, CONF_PLACE, CONF_PLACE_NAME, CONF_STANDARD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# 污染物名称
POLLUTANT_NAMES = ["PM2.5", "PM10", "O3", "NO2", "CO", "SO2"]

# 风向索引（0-360° 每 22.5° 一个方向）
WIND_DIRECTIONS = [
    "北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
    "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北",
]

# 花粉类型映射：HTML 中的 name → sensor key
# 注意：Python dict 不允许重复 key，重复 key 会被后者覆盖，务必保证每个 key 唯一
POLLEN_TYPES = {
    # 总花粉
    "花粉": "pollen_total",
    # 桦木花粉
    "桦木花粉": "pollen_birch",
    "桦树花粉": "pollen_birch",
    # 草花粉
    "草花粉": "pollen_grass",
    "禾草花粉": "pollen_grass",
    # 桤木花粉（alder）—— 与桦木是不同树种，勿混淆
    "桤木": "pollen_alder",
    "桤木花粉": "pollen_alder",
    "艾桤木": "pollen_alder",
    "艾桤木花粉": "pollen_alder",
    # 橄榄树花粉
    "橄榄树花粉": "pollen_olive",
    "橄榄花粉": "pollen_olive",
    # 豚草花粉
    "豚草花粉": "pollen_ragweed",
    "豚草": "pollen_ragweed",
    # 艾蒿花粉
    "艾蒿花粉": "pollen_mugwort",
    "艾蒿": "pollen_mugwort",
    "艾草花粉": "pollen_mugwort",
    "艾草": "pollen_mugwort",
    # 野草花粉（单独作为 ragweed 的备选，不再同时映射到 grass）
    "野草花粉": "pollen_ragweed",
    # 过敏风险
    "过敏风险指数": "allergy_risk",
    "过敏风险": "allergy_risk",
}

NUM_PATTERN = r"(\d+(?:\.\d+)?)"

# 花粉传感器 key 集合（模块级常量，避免 available 属性每次调用时重复创建）
POLLEN_KEYS = {
    "pollen", "pollen_max", "pollen_total", "pollen_birch", "pollen_grass",
    "pollen_alder", "pollen_olive", "pollen_ragweed",
    "pollen_mugwort", "allergy_risk",
}

# air-quality.com 默认时区（UTC+8，中国标准时间）
_CST = timezone(timedelta(hours=8))


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
    - 'china/haidian/7d638731'  -> /place/china/haidian/7d638731
    - 'china//7d638731'         -> /place/china//7d638731 (district, no city name)
    - 'japan/48e5965c'          -> /country/japan/48e5965c (country-level, 2 segments)
    """
    parts = place.strip("/").split("/")
    if len(parts) == 2:
        return f"https://air-quality.com/country/{place}?lang=zh-Hans&standard={standard}"
    else:
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

    # (key, 显示名, 单位, device_class, state_class, icon)
    sensor_defs = [
        ("aqi",             "AQI",                         None,                                      SensorDeviceClass.AQI,              SensorStateClass.MEASUREMENT, "mdi:air-filter"),
        ("level",           "空气质量等级",                  None,                                      None,                               None,                         "mdi:numeric"),
        ("pm25",            "PM2.5",                        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  SensorDeviceClass.PM25,             SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("pm10",            "PM10",                         CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  SensorDeviceClass.PM10,             SensorStateClass.MEASUREMENT, "mdi:blur"),
        ("o3",              "臭氧 O3",                      CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  None,                               SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("no2",             "二氧化氮 NO2",                   CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  None,                               SensorStateClass.MEASUREMENT, "mdi:gas-cylinder"),
        ("co",              "一氧化碳 CO",                    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  None,                               SensorStateClass.MEASUREMENT, "mdi:molecule-co"),
        ("so2",             "二氧化硫 SO2",                  CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  None,                               SensorStateClass.MEASUREMENT, "mdi:smog"),
        # 花粉（花粉季之外均为 None，属正常）
        ("pollen",          "花粉浓度",                      None,                                      None,                               None,                         "mdi:flower-pollen"),
        ("pollen_max",      "花粉浓度范围最大值",             None,                                  None,                               SensorStateClass.MEASUREMENT, "mdi:chart-line"),
        ("pollen_birch",    "桦木花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:sprout"),
        ("pollen_grass",    "草花粉",                        "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:grass"),
        ("pollen_alder",    "桤木花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:flower"),
        ("pollen_olive",    "橄榄树花粉",                    "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:tree"),
        ("pollen_ragweed",  "豚草花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:weed"),
        ("pollen_mugwort",  "艾蒿花粉",                      "粒/m³",                                  None,                               SensorStateClass.MEASUREMENT, "mdi:flower-tulip"),
        ("allergy_risk",   "过敏风险指数",                  None,                                      None,                               SensorStateClass.MEASUREMENT, "mdi:allergy"),
        # 天气
        ("temperature",     "温度",                          UnitOfTemperature.CELSIUS,                 SensorDeviceClass.TEMPERATURE,      SensorStateClass.MEASUREMENT, "mdi:thermometer"),
        ("humidity",        "湿度",                          PERCENTAGE,                                SensorDeviceClass.HUMIDITY,         SensorStateClass.MEASUREMENT, "mdi:water-percent"),
        ("wind_speed",      "风速",                          UnitOfSpeed.KILOMETERS_PER_HOUR,           SensorDeviceClass.WIND_SPEED,      SensorStateClass.MEASUREMENT, "mdi:weather-windy"),
        ("wind_direction",  "风向",                          None,                                      None,                               None,                         "mdi:compass"),
        ("wind_degrees",    "风向角度",                      DEGREE,                                    None,                               SensorStateClass.MEASUREMENT, "mdi:angle-acute"),
        ("uv_index",        "紫外线指数",                    "UVI",                                     None,                               SensorStateClass.MEASUREMENT, "mdi:sunglasses"),
        ("update_time",     "数据更新时间",                  None,                                      SensorDeviceClass.TIMESTAMP,        None,                         "mdi:clock"),
    ]

    entities = []
    for key, name, unit, device_class, state_class, icon in sensor_defs:
        entities.append(
            AirQualitySensor(coordinator, key, name, unit, device_class, state_class, icon, place, place_name)
        )

    async_add_entities(entities)
    _LOGGER.info("已创建 %d 个传感器, 地点: %s", len(entities), place_name)


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
            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                html = await resp.text()
        except Exception as e:
            _LOGGER.error("请求失败: %s", e)
            raise

        _LOGGER.debug("成功获取网页，长度: %d 字符", len(html))

        # ================================================================
        # 骨架页检测：无效/过期的 place_id 返回空骨架（1970时间 + 短页面）
        # 正常页面 > 35000 字符，骨架页约 18000-20000 字符
        # ================================================================
        if "1970-01-01" in html and len(html) < 25000:
            _LOGGER.warning(
                "检测到骨架页（place_id 可能无效或数据暂时不可用），URL: %s",
                self.url,
            )
            raise UpdateFailed("页面返回骨架数据，place_id 可能已失效")

        data = {}

        _QUOTE_RE = r"['\"]"

        # ================================================================
        # AQI — 从 JS Gauge() 初始化中提取 value
        # 格式: Gauge({ value: 58, ... })
        # ================================================================
        aqi_match = re.search(r"Gauge\([\s\S]+?value:\s*(\d+)\s*\}", html)
        if not aqi_match:
            aqi_match = re.search(
                r"AQI \((?:中国|中国香港|美国|澳大利亚|加拿大|英国|欧盟|法国|德国|意大利|西班牙|荷兰|波兰|俄罗斯|印度)标准\)\s*(\d+)",
                html
            )
        data["aqi"] = _to_int(aqi_match.group(1)) if aqi_match else None

        # ================================================================
        # 空气质量等级 — 从 AQI 数值推导（页面 HTML 只有英文，动态设置中文）
        # ================================================================
        if data["aqi"] is not None:
            _aqi = data["aqi"]
            if _aqi <= 50:
                data["level"] = "优"
            elif _aqi <= 100:
                data["level"] = "良"
            elif _aqi <= 150:
                data["level"] = "轻度污染"
            elif _aqi <= 200:
                data["level"] = "中度污染"
            elif _aqi <= 300:
                data["level"] = "重度污染"
            else:
                data["level"] = "严重污染"
        else:
            data["level"] = None

        # ================================================================
        # 污染物 + 花粉 — 统一用 all_pairs 提取所有 name-value 对
        # HTML 结构: <div class="name">PM2.5</div><div class="value">25</div>
        #            <div class="name">花粉</div><div class="value">301~500</div>
        # ================================================================
        all_pairs = re.findall(
            rf"<div class={_QUOTE_RE}name{_QUOTE_RE}>([^<]+)</div>.*?<div class={_QUOTE_RE}value{_QUOTE_RE}>([^<]+)</div>",
            html, re.DOTALL
        )

        # 初始化花粉传感器为 None（花粉季之外均为空，属正常）
        for _pk in ["pollen_total", "pollen_birch", "pollen_grass",
                     "pollen_alder", "pollen_olive", "pollen_ragweed",
                     "pollen_mugwort", "allergy_risk"]:
            data[_pk] = None

        pollen_raw_str = None
        pollen_max_value = None

        for name_raw, value_raw in all_pairs:
            name = name_raw.strip()
            value = value_raw.strip()

            # 污染物（6种）
            if name in POLLUTANT_NAMES:
                key = name.lower().replace(".", "")
                num_m = re.search(NUM_PATTERN, value)
                data[key] = _to_float(num_m.group(1)) if num_m else None

            # 花粉类型（通过 POLLEN_TYPES 映射）
            elif name in POLLEN_TYPES:
                sensor_key = POLLEN_TYPES[name]
                range_m = re.search(r"(\d+)\s*~\s*(\d+)", value)
                num_m = re.search(NUM_PATTERN, value) if not range_m else None

                if range_m:
                    data[sensor_key] = int(range_m.group(2))
                elif num_m:
                    data[sensor_key] = _to_float(num_m.group(1))
                else:
                    data[sensor_key] = value

                # 记录总花粉的原始字符串和最大值（仅首次遇到时）
                if sensor_key == "pollen_total" and pollen_raw_str is None:
                    pollen_raw_str = value
                    if range_m:
                        pollen_max_value = int(range_m.group(2))
                    elif num_m:
                        pollen_max_value = _to_float(num_m.group(1))

        # pollen: 原始字符串（如 "301~500"），用于显示
        data["pollen"] = pollen_raw_str
        # pollen_max: 范围最大值（数值），用于历史记录和仪表盘
        data["pollen_max"] = pollen_max_value

        # ================================================================
        # 更新时间
        # air-quality.com 页面中 update-time 的时间字符串为中国时区 (UTC+8)。
        # 保留时区信息，让 HA 根据用户系统时区自动转换显示。
        # ================================================================
        update_time = None
        time_match = re.search(rf"<div[^>]*class={_QUOTE_RE}update-time{_QUOTE_RE}[^>]*>\s*([\d\-: T+Z]+)\s*</div>", html)
        if time_match:
            raw_time = time_match.group(1).strip()
            try:
                update_time = datetime.fromisoformat(raw_time)
                if update_time.tzinfo is None:
                    update_time = update_time.replace(tzinfo=_CST)
            except ValueError:
                try:
                    update_time = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
                    update_time = update_time.replace(tzinfo=_CST)
                except Exception:
                    pass
        if update_time is None:
            update_time = datetime.now(_CST)
        data["update_time"] = update_time

        # ================================================================
        # 天气：温度、湿度、风速
        # 注：部分字段值与单位之间可能有空格或特殊字符
        # ================================================================
        temp_match = re.search(rf"<div class={_QUOTE_RE}temperature{_QUOTE_RE}>\s*(-?\d+(?:\.\d+)?)[^<]*</div>", html)
        data["temperature"] = _to_float(temp_match.group(1)) if temp_match else None

        hum_match = re.search(rf"<div class={_QUOTE_RE}humidity{_QUOTE_RE}>\s*{NUM_PATTERN}\s*%</div>", html)
        data["humidity"] = _to_float(hum_match.group(1)) if hum_match else None

        wind_match = re.search(rf"<div class={_QUOTE_RE}wind{_QUOTE_RE}>\s*{NUM_PATTERN}\s*kph</div>", html)
        data["wind_speed"] = _to_float(wind_match.group(1)) if wind_match else None

        # ================================================================
        # 风向角度 + UV — 从 curWeatherData JS 对象提取
        # ================================================================
        wind_degrees = None
        wind_direction = None
        uv = None
        start_marker = "var curWeatherData = "
        start_idx = html.find(start_marker)
        if start_idx != -1:
            json_start = start_idx + len(start_marker)
            # 跳过空白，检查是否为 null（骨架页返回 null; 而非 JSON 对象）
            remaining = html[json_start:].lstrip()
            if not remaining.startswith("null"):
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

        # UV 备选：从 HTML 提取（部分页面无 curWeatherData）
        if uv is None:
            # 最大值不固定（各地区 UV 上限不同），不硬编码
            uv_match = re.search(rf"<div class={_QUOTE_RE}uv{_QUOTE_RE}>\s*{NUM_PATTERN}\s+of\s+\d+\s*</div>", html)
            if uv_match:
                uv = _to_float(uv_match.group(1))

        data["wind_degrees"] = wind_degrees
        data["wind_direction"] = wind_direction
        data["uv_index"] = uv

        # ================================================================
        # 健康警告（排除 update_time，因为回退值为当前时间，不影响判断）
        # ================================================================
        all_none = all(v is None for k, v in data.items() if k != "update_time")
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
                # 确保有时区信息供 HA 使用
                if value.tzinfo is None:
                    value = value.replace(tzinfo=_CST)
                return value
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_CST)
                    return dt
                except Exception:
                    return None
            return None
        return value

    @property
    def available(self):
        if not self.coordinator.last_update_success:
            return False
        # 花粉类传感器在非花粉季时值为 None，属于正常现象，视为"可用但无数据"
        if self._key in POLLEN_KEYS:
            return True
        return self.coordinator.data.get(self._key) is not None
