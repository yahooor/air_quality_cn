"""api.py 解析逻辑单元测试。

fixtures 均为 2026-10-24 抓取的 air-quality.com 真实响应快照，
用于站点结构变化时的回归保护。
"""
import importlib.util
import json
import os
from datetime import datetime, timezone, timedelta

import pytest

# api.py 设计为零 homeassistant 依赖，按文件路径直接加载，
# 避免触发包 __init__.py 中的 HA 导入
_API_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "air_quality_cn", "api.py"
)
_spec = importlib.util.spec_from_file_location("aq_api", os.path.abspath(_API_PATH))
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def find_row(payload, place_id):
    for row in payload["data"]["map"]:
        if row["place"]["place_id"] == place_id:
            return row
    return None


# ─── 基础工具 ─────────────────────────────────────────────────────

def test_parse_numeric():
    assert api.parse_numeric("71") == 71.0
    assert api.parse_numeric("301~500") == 500.0
    assert api.parse_numeric(" 3.0 ") == 3.0
    assert api.parse_numeric(None) is None
    assert api.parse_numeric("无数据") is None


def test_parse_site_time_utc():
    dt = api.parse_site_time("2026-10-23 17:51")
    assert dt == datetime(2026, 10, 23, 17, 51, tzinfo=timezone.utc)
    assert api.parse_site_time("2026-10-23 17:51:00") == dt
    assert api.parse_site_time("") is None
    assert api.parse_site_time(None) is None


def test_wind_direction_text():
    assert api.wind_direction_text(0) == "北"
    assert api.wind_direction_text(90) == "东"
    assert api.wind_direction_text(220) == "西南"
    assert api.wind_direction_text(None) is None


def test_weather_text_zh():
    # 精确匹配
    assert api.weather_text_zh("clear sky") == "晴"
    assert api.weather_text_zh("Overcast Clouds") == "阴"
    # OpenWeatherMap 风格变体（前缀兜底）
    assert api.weather_text_zh("thunderstorm with heavy rain") == "雷雨"
    assert api.weather_text_zh("light intensity drizzle") == "毛毛雨"
    assert api.weather_text_zh("heavy intensity rain") == "大雨"
    assert api.weather_text_zh("scattered clouds") == "局部多云"
    # 未知文本原样返回；空值 None
    assert api.weather_text_zh("unknown phenomenon") == "unknown phenomenon"
    assert api.weather_text_zh(None) is None


# ─── 地图数据解析 ────────────────────────────────────────────────

def test_parse_place_row_beijing():
    payload = load_fixture("map_beijing.json")
    row = find_row(payload, "ec8399ca")
    assert row is not None
    data = api.parse_place_row(row)
    assert data["aqi"] == 110
    assert data["level"] == "轻度污染"
    assert data["pm25"] == 71.0
    assert data["pm25_level"] == "轻度污染"
    assert data["pm10"] == 98.0
    assert data["no2"] == 41.0
    assert data["co"] == 800.0
    assert data["o3"] == 22.0
    assert data["so2"] == 3.0
    # readings_kinds 记录实际提供的 kind（用于"上游无数据"说明属性）
    assert isinstance(data["readings_kinds"], list)
    assert set(data["readings_kinds"]) == {"aqi", "pm25", "pm10", "no2", "co", "o3", "so2"}
    # 北京无花粉数据：相关 key 不应存在
    assert data.get("pollen_birch") is None
    assert data.get("allergy_risk") is None


def test_parse_place_row_zurich_pollen():
    payload = load_fixture("map_zurich.json")
    row = find_row(payload, "4686dc2b")
    assert row is not None
    data = api.parse_place_row(row)
    assert data["aqi"] == 24
    assert data["level"] == "优"
    # 花粉 kind 全覆盖（非花粉季数值为 0）
    assert data["pollen_birch"] == 0.0
    assert data["pollen_birch_level"] == "无"
    assert data["pollen_grass"] == 3.0
    assert data["pollen_grass_level"] == "低"
    assert data["pollen_alder"] == 0.0
    assert data["pollen_mugwort"] == 0.0
    assert data["allergy_risk"] == 3.0
    assert data["allergy_risk_level"] == "低"


# ─── 历史数据解析 ────────────────────────────────────────────────

def test_parse_history_beijing():
    payload = load_fixture("history_beijing.json")
    points = api.parse_history(payload)
    # 73 个点中 2 个空值点应被跳过
    assert len(points) == 71
    last_time, last_value = points[-1]
    assert last_time == datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc)
    assert last_value == 110.0

    summary = api.summarize_history(points)
    assert summary["update_time"] == last_time
    assert summary["aqi_max_24h"] == 110
    assert summary["aqi_avg_24h"] is not None
    assert summary["aqi_trend"] in ("上升", "下降", "持平")


def test_summarize_history_synthetic():
    base = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
    points = [(base + timedelta(hours=i), 10.0 + 10 * i) for i in range(7)]
    summary = api.summarize_history(points)
    assert summary["aqi_trend"] == "上升"
    assert summary["trend_delta"] > 0
    assert summary["aqi_max_24h"] == 70

    points_down = [(base + timedelta(hours=i), 70.0 - 10 * i) for i in range(7)]
    assert api.summarize_history(points_down)["aqi_trend"] == "下降"

    flat = [(base + timedelta(hours=i), 42.0) for i in range(5)]
    assert api.summarize_history(flat)["aqi_trend"] == "持平"

    assert api.summarize_history([])["update_time"] is None


# ─── 附近数据解析 ────────────────────────────────────────────────

def test_parse_nearby_beijing():
    payload = load_fixture("nearby_beijing.json")
    data = api.parse_nearby(payload)
    # 天气（来自最近地点）
    assert data["temperature"] == 11.0
    assert data["humidity"] == 69.0
    assert data["wind_speed"] == 4.0
    assert data["wind_degrees"] == 220.0
    assert data["wind_direction"] == "西南"
    assert data["uv_index"] == 0.0
    assert data["feel_like"] == 9.87
    assert data["weather_condition"] == "晴"
    assert data["weather_icon"] == "nt_clear"
    # 首要污染物公告
    assert data["primary_pollutant"] == "PM2.5"
    # 更新时间（UTC）
    assert data["nearby_update_time"] == datetime(2026, 10, 23, 17, 51, tzinfo=timezone.utc)
    # 5 天预报
    forecast = data["forecast"]
    assert len(forecast) == 5
    assert forecast[0]["value"] == "140~160"
    assert forecast[0]["level"] == "中度污染"
    assert forecast[3]["level"] == "优"


# ─── HTML 回退解析 ───────────────────────────────────────────────

def test_parse_html_beijing():
    with open(os.path.join(FIXTURES, "page_beijing.html"), encoding="utf-8") as f:
        html = f.read()
    data = api.parse_html(html)
    assert data["aqi"] == 110
    assert data["level"] == "轻度污染"
    assert data["pm25"] == 71.0
    assert data["pm10"] == 98.0
    assert data["no2"] == 41.0
    assert data["co"] == 800.0
    assert data["o3"] == 22.0
    assert data["so2"] == 3.0
    assert data["temperature"] == 11.0
    assert data["humidity"] == 68.0
    assert data["wind_speed"] == 5.0
    assert data["wind_degrees"] == 207.0
    assert data["wind_direction"] == "南西南"
    assert data["uv_index"] == 0.0
    assert data["feel_like"] == 9.87
    assert data["weather_condition"] == "晴"
    assert data["weather_icon"] == "nt_clear"
    # 站点原始时间为 UTC（修复点：此前误标为 UTC+8）
    assert data["update_time"] == datetime(2026, 10, 23, 17, 51, tzinfo=timezone.utc)


def test_parse_html_skeleton():
    html = "<html><body>1970-01-01 00:00 skeleton page</body></html>"
    with pytest.raises(api.SkeletonPageError):
        api.parse_html(html)


def test_build_place_url():
    assert api.build_place_url("china/haidian/7d638731", "aqi_cn") == \
        "https://air-quality.com/place/china/haidian/7d638731?lang=zh-Hans&standard=aqi_cn"
    assert api.build_place_url("china//7d638731", "aqi_us") == \
        "https://air-quality.com/place/china//7d638731?lang=zh-Hans&standard=aqi_us"
    assert api.build_place_url("japan/48e5965c", "aqi_cn") == \
        "https://air-quality.com/country/japan/48e5965c?lang=zh-Hans&standard=aqi_cn"


def test_parse_weather_empty():
    assert api.parse_weather({}) == {}
    assert api.parse_weather(None) == {}


# ─── weather 平台数据 ────────────────────────────────────────────

def test_weather_condition():
    assert api.weather_condition(icon="clear") == "sunny"
    assert api.weather_condition(icon="nt_clear") == "clear-night"
    assert api.weather_condition(icon="rain") == "rainy"
    assert api.weather_condition(icon="tstorms") == "lightning-rainy"
    assert api.weather_condition(icon="partly_cloudy") == "partly-cloudy"
    # 未知图标回退到文本推断
    assert api.weather_condition(icon="mystery", text="moderate rain") == "rainy"
    assert api.weather_condition(icon="mystery", text="sky is clear") == "sunny"
    # 都未知 → None；无参 → None
    assert api.weather_condition(icon="mystery", text="weird stuff") is None
    assert api.weather_condition() is None


def test_parse_weather_forecast():
    payload = load_fixture("nearby_beijing.json")
    wf = api.parse_weather_forecast(payload)
    assert len(wf["hourly"]) == 48
    assert len(wf["daily"]) == 11

    h0 = wf["hourly"][0]
    # 站点时间为 UTC，datetime 必须带时区
    assert h0["datetime"].endswith("+00:00")
    assert h0["datetime"].startswith("2026-10-23T19:00:00")
    assert h0["condition"] == "clear-night"  # nt_clear 且 is_daytime=False
    assert h0["is_daytime"] is False
    assert h0["native_temperature"] == 12.0
    assert h0["native_apparent_temperature"] == 10.67
    assert h0["humidity"] == 69.0
    assert h0["native_wind_speed"] == 5.0
    assert h0["wind_bearing"] == 208.0

    d1 = wf["daily"][0]
    assert d1["native_temperature"] == 18.0  # high
    assert d1["native_templow"] == 10.0  # low
    assert d1["condition"] == "sunny"  # clear + "sky is clear"
    assert d1["is_daytime"] is True
    assert d1["uv_index"] == 0.0

    # 含降水的日期带降水概率
    d2 = wf["daily"][1]
    assert d2["condition"] == "rainy"
    assert d2["precipitation_probability"] == 100


def test_parse_weather_forecast_empty():
    assert api.parse_weather_forecast({"success": True, "data": {"nearby": []}}) == {"hourly": [], "daily": []}
    assert api.parse_weather_forecast({"success": True, "data": {"nearby": [{}]}}) == {"hourly": [], "daily": []}
