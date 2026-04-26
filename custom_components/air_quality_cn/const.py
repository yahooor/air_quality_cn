DOMAIN = "air_quality_cn"

DEFAULT_PLACE = ""
DEFAULT_STANDARD = "aqi_cn"
DEFAULT_SCAN_INTERVAL = 30  # minutes

CONF_PLACE = "place"
CONF_PLACE_NAME = "place_name"
CONF_STANDARD = "standard"
CONF_SCAN_INTERVAL = "scan_interval"

STANDARDS = {
    "aqi_cn": "AQI (中国标准)",
    "aqi_us": "AQI (美国标准)",
    "aqi_au": "AQC (澳大利亚标准)",
    "aqi_ca": "AQHI (加拿大标准)",
    "aqi_nl": "AQI (荷兰标准)",
    "caqi_eu": "CAQI (欧洲标准)",
    "daqi_uk": "AQI (英国标准)",
    "naqi_in": "AQI (印度标准)",
}
