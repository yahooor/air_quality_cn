# Air Quality CN (在意空气)

Home Assistant 自定义集成，通过抓取 [air-quality.com](https://air-quality.com) 获取全球空气质量数据。

## 功能

| 功能类别 | 具体内容 |
|--------|----------|
| 🌍 全球覆盖 | 支持全球 195+ 国家、248000+ 监测点的空气质量数据 |
| 📊 AQI 标准 | 中国/美国/澳大利亚/加拿大/英国/欧盟/印度/荷兰标准 |
| 🌫️ 污染物 | PM2.5、PM10、O3、NO2、CO、SO2 |
| 🌸 花粉 | 桦木/草/桤木/橄榄树/豚草/艾蒿 + 过敏风险指数 |
| 🌡️ 天气 | 温度、湿度、风速、风向、紫外线指数 |
| 🔍 搜索 | 支持中文/英文地点搜索添加 |
| 🔄 更新 | 可配置刷新间隔 |

## 安装

### HACS（推荐）

1. HACS → 集成 → 添加自定义仓库：`https://github.com/yahooor/air_quality_cn`
2. 搜索 "Air Quality CN" 安装
3. 重启 Home Assistant

### 手动安装

1. 下载 [air_quality_cn_v2.4.6.zip](https://github.com/yahooor/air_quality_cn/releases/latest)
2. 解压到 `custom_components/` 目录
3. 重启 Home Assistant

## 配置

设置 → 设备与服务 → 添加集成 → 搜索 "Air Quality CN"

### 添加流程（两步）

1. **搜索地点**：输入城市、地区或监测站名称（支持中文或英文，如"北京"、"朝阳区"、"奥体中心"）
2. **选择 AQI 标准**：选择你要使用的空气质量指数标准（中国用户推荐 AQI 中国标准）

## 传感器

| 传感器 | 说明 |
|--------|------|
| aqi | 空气质量指数（可配置标准）|
| air_quality_level | 空气质量等级（优/良/中等/轻度污染等）|
| pm25 / pm10 | 颗粒物（μg/m³）|
| o3 / no2 / so2 / co | 气态污染物（μg/m³）|
| pollen | 花粉浓度（原始范围字符串）|
| pollen_max | 花粉范围最大值（数值，用于历史图表）|

## 更新日志

### v2.4.5 (2026-04-30)
- **修复**：选项里找不到"刷新间隔"设置
- manifest.json 添加 `"options_flow": true`

### v2.4.4 (2026-04-29)
- **修复**：版本迁移错误 `Migration handler not found`
- 添加版本迁移函数 `_migrate_entry`

### v2.4.3 (2026-04-29)
- **清理**：删除 locations.json（44MB，代码无引用）
- 集成大小从 44MB 精简至 23KB

### v2.4.2 (2026-04-29)
- **清理**：删除根目录冗余文件（icon.png/logo.png、__pycache__/、info.md、test_url_bypass.py）
- 更新 README.md

### v2.4.1 (2026-04-29)
- **修复**：Logo/Icon 图片加载，按 HA 2026.3 Brands Proxy API 规范
- 新增 `brand/` 目录

### v2.4.0 (2026-04-29)
- **重构**：简化添加条目流程，删除 6 级层级浏览，只保留搜索
- 新增 `strings.json` + `translations/zh-Hans.json`，UI 全面汉化
- 代码精简：`config_flow.py` 从 431 行减至 164 行（-62%）

### v2.3.9
- 修复：层级浏览数据访问使用错误的 key 名称 (n/c/r/d/s)

### v2.3.8
- 修复：icon 配置路径

## License

MIT