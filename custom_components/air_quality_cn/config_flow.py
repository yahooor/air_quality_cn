"""
New config_flow.py for air_quality_cn integration
Supports 6-level cascading selection:
  Continent → Country → Region → City → District → Street/Community
Also keeps the search API for quick lookup.
"""
import voluptuous as vol
import asyncio
import logging
import json
import os
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_STANDARD,
    DEFAULT_SCAN_INTERVAL,
    STANDARDS,
    CONF_PLACE,
    CONF_STANDARD,
    CONF_SCAN_INTERVAL,
    CONF_PLACE_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _load_locations_db(hass):
    """Load locations.json from the integration directory."""
    db_path = os.path.join(os.path.dirname(__file__), "locations.json")
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.warning("Failed to load locations database: %s", e)
    return None


class AirQualityCNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self._location_data = {}
        self._db = None
        self._search_results = []

    # ─── Entry point ──────────────────────────────────────────────
    async def async_step_user(self, user_input=None):
        """Choose between browsing hierarchy or searching."""
        if user_input is not None:
            if user_input.get("method") == "search":
                return await self.async_step_search()
            return await self.async_step_continent()

        schema = vol.Schema({
            vol.Required("method", default="search"): vol.In({
                "search": "搜索地点",
                "browse": "按层级浏览（洲→国家→地区→城市→区→街道）",
            }),
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    # ─── Search path ─────────────────────────────────────────────
    async def async_step_search(self, user_input=None):
        errors = {}
        if user_input is not None:
            query = user_input.get("query", "").strip()
            if query:
                session = async_get_clientsession(self.hass)
                try:
                    url = f"https://air-quality.com/data/search_places?term={query}&lang=zh-Hans"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            results = await resp.json(content_type=None)
                            if results:
                                self._search_results = results[:20]
                                return await self.async_step_search_select()
                            errors["query"] = "no_results"
                        else:
                            errors["query"] = "search_failed"
                except Exception as e:
                    _LOGGER.error("Search failed: %s", e)
                    errors["query"] = "search_failed"
            else:
                errors["query"] = "invalid_place"

        schema = vol.Schema({vol.Required("query"): str})
        return self.async_show_form(step_id="search", data_schema=schema, errors=errors)

    async def async_step_search_select(self, user_input=None):
        if user_input is not None:
            idx = user_input.get("place_selection", 0)
            if 0 <= idx < len(self._search_results):
                result = self._search_results[idx]
                self._location_data["search_place"] = result
                return await self.async_step_standard()

        options = {}
        for i, r in enumerate(self._search_results):
            desc = r.get("description", "")
            name = r.get("name", "")
            options[i] = f"{name} ({desc})" if desc else name

        schema = vol.Schema({
            vol.Required("place_selection", default=0): vol.In(options),
        })
        return self.async_show_form(step_id="search_select", data_schema=schema)

    # ─── Level 1: Continent ──────────────────────────────────────
    async def async_step_continent(self, user_input=None):
        if user_input is not None:
            self._location_data["continent"] = user_input["continent"]
            return await self.async_step_country()

        db = _load_locations_db(self.hass)
        if not db:
            return await self.async_step_search()
        self._db = db
        continents = {c["name"]: c["name"] for c in db}
        schema = vol.Schema({vol.Required("continent"): vol.In(continents)})
        return self.async_show_form(step_id="continent", data_schema=schema)

    # ─── Level 2: Country ────────────────────────────────────────
    async def async_step_country(self, user_input=None):
        if user_input is not None:
            self._location_data["country_name"] = user_input["country"]
            return await self.async_step_region()

        continent_name = self._location_data.get("continent", "")
        countries = {}
        for c in (self._db or []):
            if c["name"] == continent_name:
                for country in c["countries"]:
                    countries[country["name"]] = country["name"]
                break
        schema = vol.Schema({vol.Required("country"): vol.In(countries)})
        return self.async_show_form(step_id="country", data_schema=schema)

    # ─── Level 3: Region ─────────────────────────────────────────
    async def async_step_region(self, user_input=None):
        if user_input is not None:
            if user_input.get("region") == "__skip__":
                self._location_data["use_level"] = "country"
                return await self.async_step_standard()
            self._location_data["region_name"] = user_input["region"]
            return await self.async_step_city()

        regions = self._get_regions()
        if not regions:
            self._location_data["use_level"] = "country"
            return await self.async_step_standard()

        opts = {"__skip__": f"使用 {self._location_data.get('country_name', '')} 整体数据"}
        for r in regions:
            opts[r["name"]] = r["name"]
        schema = vol.Schema({vol.Required("region"): vol.In(opts)})
        return self.async_show_form(step_id="region", data_schema=schema)

    # ─── Level 4: City ───────────────────────────────────────────
    async def async_step_city(self, user_input=None):
        if user_input is not None:
            if user_input.get("city") == "__skip__":
                self._location_data["use_level"] = "region"
                return await self.async_step_standard()
            self._location_data["city_name"] = user_input["city"]
            return await self.async_step_district()

        cities = self._get_cities()
        if not cities:
            self._location_data["use_level"] = "region"
            return await self.async_step_standard()

        opts = {"__skip__": f"使用 {self._location_data.get('region_name', '')} 整体数据"}
        for c in cities:
            opts[c["name"]] = c["name"]
        schema = vol.Schema({vol.Required("city"): vol.In(opts)})
        return self.async_show_form(step_id="city", data_schema=schema)

    # ─── Level 5: District ───────────────────────────────────────
    async def async_step_district(self, user_input=None):
        if user_input is not None:
            if user_input.get("district") == "__skip__":
                self._location_data["use_level"] = "city"
                return await self.async_step_standard()
            self._location_data["district_name"] = user_input["district"]
            return await self.async_step_street()

        districts = self._get_districts()
        if not districts:
            self._location_data["use_level"] = "city"
            return await self.async_step_standard()

        opts = {"__skip__": f"使用 {self._location_data.get('city_name', '')} 整体数据"}
        for d in districts:
            opts[d["name"]] = d["name"]
        schema = vol.Schema({vol.Required("district"): vol.In(opts)})
        return self.async_show_form(step_id="district", data_schema=schema)

    # ─── Level 6: Street / Community ─────────────────────────────
    async def async_step_street(self, user_input=None):
        if user_input is not None:
            if user_input.get("street") == "__skip__":
                self._location_data["use_level"] = "district"
            else:
                self._location_data["street_name"] = user_input["street"]
            return await self.async_step_standard()

        streets = self._get_streets()
        if not streets:
            # No sub-districts, use district level
            self._location_data["use_level"] = "district"
            return await self.async_step_standard()

        opts = {"__skip__": f"使用 {self._location_data.get('district_name', '')} 整体数据"}
        for s in streets:
            opts[s["name"]] = s["name"]
        schema = vol.Schema({vol.Required("street"): vol.In(opts)})
        return self.async_show_form(step_id="street", data_schema=schema)

    # ─── Standard selection (final step before create_entry) ─────
    async def async_step_standard(self, user_input=None):
        if user_input is not None:
            standard = user_input.get("standard", DEFAULT_STANDARD)
            place, place_name = self._resolve_place_and_name()
            return self.async_create_entry(
                title=f"在意空气 ({place_name})",
                data={
                    CONF_PLACE: place,
                    CONF_PLACE_NAME: place_name,
                    CONF_STANDARD: standard,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        schema = vol.Schema({
            vol.Required("standard", default=DEFAULT_STANDARD): vol.In(STANDARDS),
        })
        return self.async_show_form(step_id="standard", data_schema=schema)

    # ─── Data access helpers ─────────────────────────────────────
    def _get_country_data(self):
        if not self._db:
            return None
        cn = self._location_data.get("continent", "")
        co = self._location_data.get("country_name", "")
        for c in self._db:
            if c["name"] == cn:
                for country in c["countries"]:
                    if country["name"] == co:
                        return country
        return None

    def _get_regions(self):
        country = self._get_country_data()
        return country.get("regions", []) if country else []

    def _get_cities(self):
        country = self._get_country_data()
        if not country:
            return []
        rn = self._location_data.get("region_name", "")
        for region in country.get("regions", []):
            if region["name"] == rn:
                return region.get("cities", [])
        return []

    def _get_districts(self):
        country = self._get_country_data()
        if not country:
            return []
        rn = self._location_data.get("region_name", "")
        cn = self._location_data.get("city_name", "")
        for region in country.get("regions", []):
            if region["name"] == rn:
                for city in region.get("cities", []):
                    if city["name"] == cn:
                        return city.get("districts", [])
        return []

    def _get_streets(self):
        """Get streets/communities for the selected district."""
        country = self._get_country_data()
        if not country:
            return []
        rn = self._location_data.get("region_name", "")
        cn = self._location_data.get("city_name", "")
        dn = self._location_data.get("district_name", "")
        for region in country.get("regions", []):
            if region["name"] == rn:
                for city in region.get("cities", []):
                    if city["name"] == cn:
                        for district in city.get("districts", []):
                            if district["name"] == dn:
                                return district.get("streets", [])
        return []

    def _resolve_place_and_name(self):
        """Resolve final place URL string and display name from current selection."""
        # Search path
        if "search_place" in self._location_data:
            result = self._location_data["search_place"]
            url_key = result.get("url_key", "").strip("/")
            place_id = result.get("place_id", "").strip("/")
            # 防御：url_key 或 place_id 为空时不拼接多余斜杠
            if url_key and place_id:
                place = f"{url_key}/{place_id}"
            elif url_key:
                place = url_key
            elif place_id:
                place = place_id
            else:
                place = ""
            name = result.get("name", place)
            return place, name

        # Browse path — walk from deepest to shallowest
        country = self._get_country_data()
        if not country:
            return "", "Unknown"

        street_name = self._location_data.get("street_name")
        district_name = self._location_data.get("district_name")
        city_name = self._location_data.get("city_name")
        region_name = self._location_data.get("region_name")
        use_level = self._location_data.get("use_level", "")

        ck = country["url_key"]

        # Street level (deepest)
        if street_name:
            for region in country.get("regions", []):
                if region["name"] == region_name:
                    for city in region.get("cities", []):
                        if city["name"] == city_name:
                            for district in city.get("districts", []):
                                if district["name"] == district_name:
                                    for street in district.get("streets", []):
                                        if street["name"] == street_name:
                                            return f"{ck}/{street['url_key']}/{street['id']}", street_name

        # District level
        if district_name or use_level == "district":
            for region in country.get("regions", []):
                if region["name"] == region_name:
                    for city in region.get("cities", []):
                        if city["name"] == city_name:
                            for district in city.get("districts", []):
                                if district["name"] == district_name:
                                    return f"{ck}/{district['url_key']}/{district['id']}", district_name

        # City level
        if city_name or use_level == "city":
            for region in country.get("regions", []):
                if region["name"] == region_name:
                    for city in region.get("cities", []):
                        if city["name"] == city_name:
                            return f"{ck}/{city['url_key']}/{city['id']}", city_name

        # Region level
        if region_name or use_level == "region":
            for region in country.get("regions", []):
                if region["name"] == region_name:
                    return f"{ck}/{region['url_key']}/{region['id']}", region_name

        # Country level
        return f"{ck}/{country['id']}", self._location_data.get("country_name", "")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AirQualityCNOptionsFlow(config_entry)


class AirQualityCNOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        current_interval = options.get(
            CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        schema = vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(int, vol.Range(min=1)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
