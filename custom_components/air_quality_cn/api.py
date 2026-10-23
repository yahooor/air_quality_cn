"""
air-quality.com 数据接口层。

不依赖 homeassistant，可独立单元测试。

数据获取优先使用站点自身的 JSON 接口（其网页前端同样调用这些接口）：
- data/get_map_data      小范围窗口内各地点的最新读数（含按所选标准计算的等级、花粉）
- data/get_history_data  某地点按小时的 AQI 历史（提供数据更新时间与趋势）
- data/get_nearby_data   最近地点的天气、公告（首要污染物）与 5 天预报

JSON 接口不可用时回退到 HTML 页面解析（parse_html）。

注意：站点所有时间字符串均为 UTC（页面 JS 用 moment.utc(...).local() 转换），
解析时统一附加 timezone.utc。
"""
import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import aiohttp

BASE_URL = "https://air-quality.com/"
EP_SEARCH = "data/search_places"
EP_MAP = "data/get_map_data"
EP_HISTORY = "data/get_history_data"
EP_NEARBY = "data/get_nearby_data"

# 地图窗口跨度（度）。0.15° ≈ 17km，足够覆盖地点自身标记点
MAP_SPAN = 0.15

# 污染物/AQI/花粉 kind → 传感器 key
KIND_TO_KEY = {
    "aqi": "aqi",
    "pm25": "pm25",
    "pm10": "pm10",
    "o3": "o3",
    "no2": "no2",
    "co": "co",
    "so2": "so2",
    # 花粉
    "pollen": "pollen_total",
    "betu": "pollen_birch",
    "poac": "pollen_grass",
    "alnu": "pollen_alder",
    "olea": "pollen_olive",
    "ambr": "pollen_ragweed",
    "arte": "pollen_mugwort",
    "ar": "allergy_risk",
}

# HTML 回退解析用：污染物名称
POLLUTANT_NAMES = ["PM2.5", "PM10", "O3", "NO2", "CO", "SO2"]

# 风向索引（0-360° 每 22.5° 一个方向）
WIND_DIRECTIONS = [
    "北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
    "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北",
]

# HTML 回退解析用：花粉名称 → sensor key（每个 key 必须唯一）
POLLEN_TYPES = {
    "花粉": "pollen_total",
    "桦木花粉": "pollen_birch",
    "桦树花粉": "pollen_birch",
    "草花粉": "pollen_grass",
    "禾草花粉": "pollen_grass",
    # 桤木（alder）与桦木是不同树种，勿混淆
    "桤木": "pollen_alder",
    "桤木花粉": "pollen_alder",
    "艾桤木": "pollen_alder",
    "艾桤木花粉": "pollen_alder",
    "橄榄树花粉": "pollen_olive",
    "橄榄花粉": "pollen_olive",
    "豚草花粉": "pollen_ragweed",
    "豚草": "pollen_ragweed",
    "野草花粉": "pollen_ragweed",
    "艾蒿花粉": "pollen_mugwort",
    "艾蒿": "pollen_mugwort",
    "艾草花粉": "pollen_mugwort",
    "艾草": "pollen_mugwort",
    "过敏风险指数": "allergy_risk",
    "过敏风险": "allergy_risk",
}

# 站点天气状况文本（英文）→ 中文
WEATHER_TEXT_ZH = {
    "clear sky": "晴", "mostly clear": "晴", "clear": "晴",
    "few clouds": "少云", "scattered clouds": "局部多云",
    "partly cloudy": "多云", "broken clouds": "多云", "cloudy": "多云",
    "overcast": "阴",
    "light rain": "小雨", "moderate rain": "中雨", "heavy rain": "大雨",
    "rain": "雨", "drizzle": "毛毛雨", "shower": "阵雨",
    "light snow": "小雪", "heavy snow": "大雪", "snow": "雪",
    "sleet": "雨夹雪",
    "mist": "薄雾", "fog": "雾", "haze": "霾", "smoke": "烟尘", "dust": "沙尘",
    "thunderstorm": "雷雨", "windy": "大风",
}

NUM_PATTERN = r"(\d+(?:\.\d+)?)"
_QUOTE_RE = r"['\"]"
_UTC = timezone.utc


class ApiError(Exception):
    """JSON 接口请求/响应异常。"""


class SkeletonPageError(Exception):
    """HTML 页面为骨架页（place_id 可能无效或数据暂不可用）。"""


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


def parse_numeric(value):
    """数值或范围字符串 → 数值（范围取最大值，如 '301~500' → 500）。"""
    if value is None:
        return None
    text = str(value)
    m = re.search(r"(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)", text)
    if m:
        return _to_float(m.group(2))
    m = re.search(NUM_PATTERN, text)
    return _to_float(m.group(1)) if m else None


def parse_site_time(raw):
    """站点时间字符串（UTC，如 '2026-10-23 17:51' / '2026-10-23 17:51:00'）→ aware datetime。"""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=_UTC)
        except ValueError:
            continue
    return None


def wind_direction_text(degrees):
    if degrees is None:
        return None
    return WIND_DIRECTIONS[round(degrees / 22.5) % 16]


def weather_text_zh(text):
    if not text:
        return None
    return WEATHER_TEXT_ZH.get(str(text).strip().lower(), text)


# ─── HTTP 请求 ────────────────────────────────────────────────────

async def post_json(session, endpoint, params, timeout=30):
    """POST 表单并解析 JSON，失败抛 ApiError。"""
    url = f"{BASE_URL}{endpoint}"
    try:
        async with session.post(
            url, data=params, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                raise ApiError(f"{endpoint} HTTP {resp.status}")
            try:
                payload = await resp.json(content_type=None)
            except Exception as e:
                raise ApiError(f"{endpoint} 响应非 JSON: {e}") from e
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(f"{endpoint} 请求失败: {e}") from e
    if not isinstance(payload, dict) or not payload.get("success", False):
        raise ApiError(f"{endpoint} 返回 success=false")
    return payload


async def get_search_results(session, term, timeout=20):
    """地点搜索，返回结果列表。"""
    url = f"{BASE_URL}{EP_SEARCH}?term={quote(term)}&lang=zh-Hans"
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                raise ApiError(f"{EP_SEARCH} HTTP {resp.status}")
            results = await resp.json(content_type=None)
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(f"{EP_SEARCH} 请求失败: {e}") from e
    if not isinstance(results, list):
        raise ApiError(f"{EP_SEARCH} 响应格式异常")
    return results


# ─── 地图数据（最新读数） ─────────────────────────────────────────

async def fetch_map_row(session, lat, lon, standard, place_id, timeout=30):
    """取地图窗口数据并返回 place_id 匹配的行，未匹配返回 None。"""
    payload = await post_json(session, EP_MAP, {
        "center_lat": lat, "center_lon": lon,
        "span_lat": MAP_SPAN, "span_lon": MAP_SPAN,
        "standard": standard, "lang": "zh-Hans",
    }, timeout=timeout)
    rows = (payload.get("data") or {}).get("map") or []
    for row in rows:
        if ((row.get("place") or {}).get("place_id") or "").strip("/") == str(place_id).strip("/"):
            return row
    return None


def parse_place_row(row):
    """地图行 → 传感器数据字典（读数 + 各自等级）。"""
    data = {}
    pollen_raw = None
    for r in (row.get("latest") or {}).get("readings") or []:
        key = KIND_TO_KEY.get(r.get("kind"))
        if not key:
            continue
        raw = r.get("value")
        data[key] = parse_numeric(raw)
        if r.get("level"):
            data[f"{key}_level"] = r["level"]
        if key == "pollen_total":
            pollen_raw = str(raw) if raw is not None else None
    if data.get("aqi_level"):
        data["level"] = data["aqi_level"]
    data["pollen"] = pollen_raw
    data["pollen_max"] = data.get("pollen_total")
    return data


# ─── 历史数据（更新时间 + 趋势） ─────────────────────────────────

async def fetch_history(session, place_id, standard, timeout=30):
    return await post_json(session, EP_HISTORY, {
        "place_id": place_id, "kind": "aqi",
        "standard": standard, "interval": "hourly", "lang": "zh-Hans",
    }, timeout=timeout)


def parse_history(payload):
    """历史响应 → 按时间升序的 [(aware datetime, float)] 列表（跳过空值点）。"""
    points = []
    for series in (payload.get("data") or {}).get("history") or []:
        for p in series.get("data") or []:
            value = _to_float(p.get("value"))
            when = parse_site_time(p.get("time"))
            if value is not None and when is not None:
                points.append((when, value))
    points.sort(key=lambda x: x[0])
    return points


def summarize_history(points):
    """历史点 → update_time / 趋势 / 24h 统计。"""
    out = {
        "update_time": None, "aqi_trend": None, "trend_delta": None,
        "aqi_avg_24h": None, "aqi_max_24h": None,
    }
    if not points:
        return out
    last_time, last_value = points[-1]
    out["update_time"] = last_time
    window = [v for t, v in points if t >= last_time - timedelta(hours=24)]
    out["aqi_avg_24h"] = round(sum(window) / len(window), 1) if window else None
    out["aqi_max_24h"] = _to_int(max(window)) if window else None
    if len(points) >= 2:
        recent = [v for _, v in points[-3:]]
        prior = [v for _, v in points[-6:-3]] or [points[0][1]]
        delta = round(sum(recent) / len(recent) - sum(prior) / len(prior), 1)
        out["trend_delta"] = delta
        out["aqi_trend"] = "上升" if delta >= 5 else ("下降" if delta <= -5 else "持平")
    return out


# ─── 附近数据（天气 / 首要污染物 / 预报） ─────────────────────────

async def fetch_nearby(session, lat, lon, standard, timeout=30):
    return await post_json(session, EP_NEARBY, {
        "lat": lat, "lon": lon, "standard": standard, "lang": "zh-Hans",
    }, timeout=timeout)


def parse_nearby(payload):
    """附近数据响应 → 天气字段、首要污染物、5 天预报、最近地点更新时间。"""
    data = {}
    nearby = (payload.get("data") or {}).get("nearby") or []
    if not nearby:
        return data
    latest = nearby[0].get("latest") or {}
    data.update(parse_weather(latest.get("weather") or {}))
    for b in latest.get("bulletins") or []:
        if b.get("type") == "MAIN_POLLUTANT" and b.get("text2"):
            data["primary_pollutant"] = b["text2"]
            break
    if latest.get("update_time"):
        data["nearby_update_time"] = parse_site_time(latest["update_time"])
    forecast = []
    for series in nearby[0].get("forecast") or []:
        for p in series.get("data") or []:
            forecast.append({
                "time": (p.get("time") or "")[:10],
                "value": p.get("value"),
                "level": p.get("level"),
                "color": p.get("color"),
            })
    if forecast:
        data["forecast"] = forecast
    return data


def parse_weather(weather):
    """天气对象 → 传感器字段。"""
    if not weather:
        return {}
    data = {}
    temp = _to_float(weather.get("temp_c"))
    humidity = _to_float(str(weather.get("humidity", "")).strip().rstrip("%"))
    wind_speed = _to_float(weather.get("wind_kph"))
    wind_degrees = _to_float(weather.get("wind_degrees"))
    uv = _to_float(weather.get("UV", weather.get("uv")))
    feel_like = _to_float(weather.get("feel_like"))
    if temp is not None:
        data["temperature"] = temp
    if humidity is not None:
        data["humidity"] = humidity
    if wind_speed is not None:
        data["wind_speed"] = wind_speed
    if wind_degrees is not None:
        data["wind_degrees"] = wind_degrees
        data["wind_direction"] = wind_direction_text(wind_degrees)
    if uv is not None:
        data["uv_index"] = uv
    if feel_like is not None:
        data["feel_like"] = feel_like
    condition = weather_text_zh(weather.get("weather"))
    if condition:
        data["weather_condition"] = condition
    if weather.get("icon"):
        data["weather_icon"] = weather["icon"]
    return data


# ─── 坐标解析（旧配置条目引导） ──────────────────────────────────

async def resolve_coords(session, place_id, place_name):
    """通过地点搜索按 place_id 精确匹配经纬度（用于缺少坐标的旧条目）。"""
    results = await get_search_results(session, place_name)
    for r in results:
        if str(r.get("place_id", "")).strip("/") == str(place_id).strip("/"):
            return r.get("lat"), r.get("lon")
    return None, None


# ─── HTML 回退路径 ────────────────────────────────────────────────

def build_place_url(place, standard):
    """place 路径 → 页面 URL。

    - 'china/haidian/7d638731'  -> /place/china/haidian/7d638731
    - 'china//7d638731'         -> /place/china//7d638731
    - 'japan/48e5965c'          -> /country/japan/48e5965c
    """
    parts = place.strip("/").split("/")
    if len(parts) == 2:
        return f"{BASE_URL}country/{place}?lang=zh-Hans&standard={standard}"
    return f"{BASE_URL}place/{place}?lang=zh-Hans&standard={standard}"


async def fetch_html(session, place, standard, timeout=30):
    url = build_place_url(place, standard)
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            html = await resp.text()
    except Exception as e:
        raise ApiError(f"页面请求失败: {e}") from e
    return html


def parse_html(html):
    """HTML 页面 → 传感器数据字典（JSON 接口不可用时的回退路径）。

    等级按中国标准 AQI 分段推导（HTML 中无按标准计算的等级文本）。
    抛出 SkeletonPageError 表示骨架页。
    """
    # 骨架页检测：无效/过期的 place_id 返回空骨架（1970时间 + 短页面）
    if "1970-01-01" in html and len(html) < 25000:
        raise SkeletonPageError("页面返回骨架数据，place_id 可能已失效")

    data = {}

    # AQI — JS Gauge() 初始化中的 value，回退到标准文本
    aqi_match = re.search(r"Gauge\([\s\S]+?value:\s*(\d+)\s*\}", html)
    if not aqi_match:
        aqi_match = re.search(
            r"AQI \((?:中国|中国香港|美国|澳大利亚|加拿大|英国|欧盟|法国|德国|意大利|西班牙|荷兰|波兰|俄罗斯|印度)标准\)\s*(\d+)",
            html,
        )
    data["aqi"] = _to_int(aqi_match.group(1)) if aqi_match else None

    # 等级 — 中国标准分段
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

    # 污染物 + 花粉 — name/value 节点对
    all_pairs = re.findall(
        rf"<div class={_QUOTE_RE}name{_QUOTE_RE}>([^<]+)</div>(?:(?!<div class={_QUOTE_RE}name{_QUOTE_RE}>).)*?<div class={_QUOTE_RE}value{_QUOTE_RE}>([^<]+)</div>",
        html, re.DOTALL
    )

    for _pk in ("pollen_total", "pollen_birch", "pollen_grass",
                "pollen_alder", "pollen_olive", "pollen_ragweed",
                "pollen_mugwort", "allergy_risk"):
        data[_pk] = None

    pollen_raw_str = None
    pollen_max_value = None

    for name_raw, value_raw in all_pairs:
        name = name_raw.strip()
        value = value_raw.strip()
        if name in POLLUTANT_NAMES:
            key = name.lower().replace(".", "")
            num_m = re.search(NUM_PATTERN, value)
            data[key] = _to_float(num_m.group(1)) if num_m else None
        elif name in POLLEN_TYPES:
            sensor_key = POLLEN_TYPES[name]
            num = parse_numeric(value)
            data[sensor_key] = num
            if sensor_key == "pollen_total" and pollen_raw_str is None:
                pollen_raw_str = value
                pollen_max_value = num

    data["pollen"] = pollen_raw_str
    data["pollen_max"] = pollen_max_value

    # 更新时间 — 站点原始时间为 UTC
    time_match = re.search(
        rf"<div[^>]*class={_QUOTE_RE}update-time{_QUOTE_RE}[^>]*>\s*([\d\-: T+Z]+)\s*</div>",
        html,
    )
    update_time = None
    if time_match:
        raw_time = time_match.group(1).strip()
        try:
            update_time = datetime.fromisoformat(raw_time)
            if update_time.tzinfo is None:
                update_time = update_time.replace(tzinfo=_UTC)
        except ValueError:
            update_time = parse_site_time(raw_time[:16])
    data["update_time"] = update_time

    # 天气：温度/湿度/风速节点
    temp_match = re.search(rf"<div class={_QUOTE_RE}temperature{_QUOTE_RE}>\s*(-?\d+(?:\.\d+)?)[^<]*</div>", html)
    data["temperature"] = _to_float(temp_match.group(1)) if temp_match else None

    hum_match = re.search(rf"<div class={_QUOTE_RE}humidity{_QUOTE_RE}>\s*{NUM_PATTERN}\s*%</div>", html)
    data["humidity"] = _to_float(hum_match.group(1)) if hum_match else None

    wind_match = re.search(rf"<div class={_QUOTE_RE}wind{_QUOTE_RE}>\s*{NUM_PATTERN}\s*kph</div>", html)
    data["wind_speed"] = _to_float(wind_match.group(1)) if wind_match else None

    # 风向角度 + UV + 体感/天气文本 — curWeatherData JS 对象
    start_marker = "var curWeatherData = "
    start_idx = html.find(start_marker)
    if start_idx != -1:
        json_start = start_idx + len(start_marker)
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
                    data.update(parse_weather(json.loads(json_str)))
                except (json.JSONDecodeError, TypeError):
                    pass

    # UV 备选：HTML 节点（最大值各地区不同，不硬编码）
    if data.get("uv_index") is None:
        uv_match = re.search(rf"<div class={_QUOTE_RE}uv{_QUOTE_RE}>\s*{NUM_PATTERN}\s+of\s+\d+\s*</div>", html)
        if uv_match:
            data["uv_index"] = _to_float(uv_match.group(1))

    return data
