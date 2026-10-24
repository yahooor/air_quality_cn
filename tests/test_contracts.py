"""契约测试：录制的上游全量原始响应必须匹配 jsonschema 契约。

fixtures/raw/ 下为 2026-10-25 抓取的未裁剪响应。
上游字段变更会在这里爆红，而不是在生产 HA 里静默坏掉。
"""
import importlib.util
import json
import os

import pytest

spec = importlib.util.spec_from_file_location(
    "canary", os.path.join(os.path.dirname(__file__), "canary.py")
)
canary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)

RAW = os.path.join(os.path.dirname(__file__), "fixtures", "raw")
SCHEMAS = os.path.join(os.path.dirname(__file__), "schemas")

RAW_FIXTURES = {
    "search_places": ("search_places_full.json", "search_places.schema.json"),
    "get_map_data": ("get_map_data_full.json", "get_map_data.schema.json"),
    "get_history_data": ("get_history_data_full.json", "get_history_data.schema.json"),
    "get_nearby_data": ("get_nearby_data_full.json", "get_nearby_data.schema.json"),
}


def _load(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return json.load(f)


def _schema(name):
    with open(os.path.join(SCHEMAS, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("endpoint", list(RAW_FIXTURES), ids=list(RAW_FIXTURES))
def test_raw_fixture_matches_contract(endpoint):
    raw_name, schema_name = RAW_FIXTURES[endpoint]
    payload = _load(raw_name)
    schema = _schema(schema_name)
    errors = canary.validate_payload(endpoint, payload, schema)
    assert not errors, f"{endpoint} 契约违约: {errors}"


def test_map_fixture_contains_place_row():
    """北京页面地点必须在 map 响应中有读数行——保证 canary/解析假设成立。"""
    payload = _load(RAW_FIXTURES["get_map_data"][0])
    rows = payload["data"]["map"]
    assert any(r["place"]["place_id"] == "ec8399ca" for r in rows)


def test_history_fixture_has_values():
    payload = _load(RAW_FIXTURES["get_history_data"][0])
    points = payload["data"]["history"][0]["data"]
    assert len(points) > 24
    assert sum(1 for p in points if p.get("value") not in (None, "")) > 20


def test_nearby_fixture_has_forecast_sections():
    payload = _load(RAW_FIXTURES["get_nearby_data"][0])
    first = payload["data"]["nearby"][0]
    wf = first.get("weather_forecast") or {}
    assert len(wf.get("hourly", [])) >= 24
    assert len(wf.get("daily", [])) >= 5
