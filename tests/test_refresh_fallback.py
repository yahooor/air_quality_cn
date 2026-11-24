"""Drive the real coordinator and parsers with offline HA and HTTP stand-ins."""
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class FakeUpdateFailed(Exception):
    pass


class FakeCoordinator:
    def __init__(self, hass, _logger, **kwargs):
        self.hass = hass


class FakeResponse:
    def __init__(self, status=200, body=""):
        self.status = status
        self.body = body
        self.text_read = False

    async def text(self):
        self.text_read = True
        return self.body


class FakeSession:
    def __init__(self, html_response):
        self.html_response = html_response
        self.calls = []

    @asynccontextmanager
    async def post(self, url, **kwargs):
        self.calls.append(("POST", url))
        yield FakeResponse(status=502)

    @asynccontextmanager
    async def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if isinstance(self.html_response, Exception):
            raise self.html_response
        yield self.html_response


@pytest.fixture
def load_coordinator(monkeypatch):
    def bind(name, **attrs):
        mod = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, mod)
        for key, value in attrs.items():
            setattr(mod, key, value)
        return mod

    bind("homeassistant", __path__=[], const=SimpleNamespace())
    bind("homeassistant.components", __path__=[])
    bind("homeassistant.components.sensor", SensorDeviceClass=object, SensorEntity=type("SensorEntity", (), {}),
         SensorStateClass=object)
    bind("homeassistant.config_entries", ConfigEntry=object)
    bind("homeassistant.core", HomeAssistant=object)
    bind("homeassistant.helpers", __path__=[])
    bind("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: hass.session)
    bind("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    bind("homeassistant.helpers.update_coordinator", CoordinatorEntity=type("CoordinatorEntity", (), {}),
         DataUpdateCoordinator=FakeCoordinator, UpdateFailed=FakeUpdateFailed)
    package = "_aq_refresh_under_test"
    root = Path(__file__).resolve().parents[1] / "custom_components" / "air_quality_cn"
    bind(package, __path__=[str(root)])  # do not execute integration-level service registration
    sensor = import_module(f"{package}.sensor")

    def make(html_response, nearby=None):
        session = FakeSession(html_response)
        hass = SimpleNamespace(data={}, session=session)
        entry = SimpleNamespace(entry_id="test-entry", data={"lat": 30.0, "lon": 100.0})
        coordinator = sensor.AirQualityCoordinator(hass, entry, "test/region/site", "site", "Test", "aqi_cn", 30)
        coordinator._nearby_data = AsyncMock(return_value=nearby)
        return coordinator, session

    try:
        yield make
    finally:
        for key in ("api", "const", "sensor"):
            sys.modules.pop(f"{package}.{key}", None)


def test_map_502_falls_back_to_html_and_preserves_nearby_values(load_coordinator):
    coordinator, session = load_coordinator(FakeResponse(body=(
        "<p>AQI (中国标准) 0</p><div class='name'>PM2.5</div><div class='value'>9</div>"
        "<div class='temperature'>12</div>"
    )), nearby={"temperature": 21})
    data = asyncio.run(coordinator._async_update_data())
    assert [method for method, _url in session.calls] == ["POST", "GET"]
    assert data["aqi"] == 0 and data["pm25"] == 9
    assert data["temperature"] == 21
    assert data.get("co") is None  # A missing optional pollutant is not a failed update.


def test_map_502_and_html_timeout_fail_the_refresh(load_coordinator):
    coordinator, session = load_coordinator(TimeoutError("offline sample"))
    with pytest.raises(FakeUpdateFailed, match="页面请求失败"):
        asyncio.run(coordinator._async_update_data())
    assert [method for method, _url in session.calls] == ["POST", "GET"]
    assert coordinator._update_count == 0


def test_html_http_error_is_not_read_or_counted_as_data(load_coordinator):
    response = FakeResponse(status=503, body="<p>AQI (中国标准) 91</p>")
    coordinator, _session = load_coordinator(response)
    with pytest.raises(FakeUpdateFailed, match="页面请求失败.*503"):
        asyncio.run(coordinator._async_update_data())
    assert not response.text_read and coordinator._update_count == 0


@pytest.mark.parametrize("nearby", [None, {"wf_hourly": [], "readings_kinds": [], "temperature": None}])
def test_timestamp_only_html_is_not_a_successful_update(load_coordinator, nearby):
    response = FakeResponse(body="<div class='update-time'>2026-11-24T00:00:00</div>")
    coordinator, _session = load_coordinator(response, nearby=nearby)
    with pytest.raises(FakeUpdateFailed, match="所有解析字段均为空"):
        asyncio.run(coordinator._async_update_data())
    assert coordinator._update_count == 0


@pytest.mark.parametrize("nearby", [None, {"temperature": None}])
def test_html_with_valid_weather_only_remains_usable(load_coordinator, nearby):
    response = FakeResponse(body=("<div class='temperature'>0</div>"
                                  "<div class='update-time'>2026-11-24T00:00:00</div>"))
    coordinator, _session = load_coordinator(response, nearby=nearby)
    data = asyncio.run(coordinator._async_update_data())
    assert data["temperature"] == 0 and data["aqi"] is None
    assert data["update_time"] == datetime(2026, 11, 24, tzinfo=timezone.utc)


def test_fallback_aqi_prefers_the_html_timestamp_to_cached_nearby_time(load_coordinator):
    response = FakeResponse(body=("<p>AQI (中国标准) 37</p>"
                                  "<div class='update-time'>2040-04-05T13:00:00</div>"))
    cached = datetime(2040, 4, 5, 10, tzinfo=timezone.utc)
    coordinator, _ = load_coordinator(response, nearby={"nearby_update_time": cached, "temperature": 21})
    data = asyncio.run(coordinator._async_update_data())
    assert data["update_time"] == datetime(2040, 4, 5, 13, tzinfo=timezone.utc)
    assert data["aqi"] == 37 and data["temperature"] == 21


def test_fallback_without_its_timestamp_can_use_the_same_station_time(load_coordinator):
    response = FakeResponse(body="<p>AQI (中国标准) 37</p>")
    cached = datetime(2040, 4, 5, 10, tzinfo=timezone.utc)
    coordinator, _ = load_coordinator(response, nearby={"nearby_update_time": cached})
    data = asyncio.run(coordinator._async_update_data())
    assert data["update_time"] == cached
    assert "nearby_update_time" not in data
