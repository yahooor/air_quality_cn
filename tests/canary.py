#!/usr/bin/env python3
"""Canary：对 air-quality.com 线上接口做契约校验（CI 定时任务 / 手工运行）。

仅用标准库 + jsonschema，独立于 homeassistant。
用法: python tests/canary.py  → 全部通过退出 0，任何违约退出 1。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")
BASE = "https://air-quality.com/"
UA = "Mozilla/5.0 (X11; Linux x86_64) canary/air_quality_cn"
TIMEOUT = 45

# 北京页面地点（ec8399ca）——canary 锚点
PLACE_ID = "ec8399ca"
LAT, LON = 39.906214, 116.3977

try:
    import jsonschema
except ImportError:  # pragma: no cover
    print("canary 需要 jsonschema: pip install jsonschema", file=sys.stderr)
    raise


def validate_payload(endpoint, payload, schema):
    """返回违约错误列表（可被离线契约测试复用）。"""
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{list(err.absolute_path)}: {err.message}"
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    ]


def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post(endpoint, params, timeout=TIMEOUT):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        BASE + endpoint, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _schema(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def fetch_all():
    return {
        "search_places": _get(f"{BASE}data/search_places?term=beijing&lang=zh-Hans"),
        "get_map_data": _post("data/get_map_data", {
            "center_lat": LAT, "center_lon": LON,
            "span_lat": 0.15, "span_lon": 0.15,
            "standard": "aqi_cn", "lang": "zh-Hans",
        }),
        "get_history_data": _post("data/get_history_data", {
            "place_id": PLACE_ID, "kind": "aqi",
            "standard": "aqi_cn", "interval": "hourly", "lang": "zh-Hans",
        }),
        "get_nearby_data": _post("data/get_nearby_data", {
            "lat": LAT, "lon": LON, "standard": "aqi_cn", "lang": "zh-Hans",
        }),
    }


SCHEMA_FILES = {
    "search_places": "search_places.schema.json",
    "get_map_data": "get_map_data.schema.json",
    "get_history_data": "get_history_data.schema.json",
    "get_nearby_data": "get_nearby_data.schema.json",
}


def main():
    failures = []
    payloads = fetch_all()
    for endpoint, payload in payloads.items():
        schema = _schema(SCHEMA_FILES[endpoint])
        errors = validate_payload(endpoint, payload, schema)
        if errors:
            failures.append((endpoint, errors))
            print(f"FAIL {endpoint}: {len(errors)} 处违约")
            for e in errors[:5]:
                print(f"   - {e}")
        else:
            print(f"PASS {endpoint}")
    # 业务锚点：map 必须包含锚点地点读数
    rows = payloads["get_map_data"]["data"]["map"]
    if not any(r["place"]["place_id"] == PLACE_ID for r in rows):
        failures.append(("anchor", [f"map 响应中无锚点地点 {PLACE_ID}"]))
        print(f"FAIL anchor: map 无 {PLACE_ID}")
    if failures:
        print(f"\n{len(failures)} 个端点违约")
        return 1
    print("\n全部契约通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
