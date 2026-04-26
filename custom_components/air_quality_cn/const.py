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

# Pollutant sensors (always shown when data available)
POLLUTANT_SENSORS = ["PM2.5", "PM10", "O3", "NO2", "CO", "SO2"]

# Pollen / Allergy sensors (shown when data available, seasonal)
POLLEN_SENSORS = {
    "pollen_birch": ("桦木花粉", "mdi:flower-pollen-outline"),
    "pollen_grass": ("草花粉", "mdi:grass"),
    "pollen_alder": ("桤木花粉", "mdi:flower"),
    "pollen_olive": ("橄榄树花粉", "mdi:tree"),
    "pollen_ragweed": ("豚草花粉", "mdi:weed"),
    "pollen_mugwort": ("蒿花粉", "mdi:flower-tulip"),
    "pollen_total": ("花粉总量", "mdi:flower-pollen"),
    "allergy_risk": ("过敏风险指数", "mdi:allergy"),
}
