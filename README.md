# Air Quality CN (在意空气)

Home Assistant 自定义集成，通过抓取 [air-quality.com](https://air-quality.com) 获取全球空气质量数据。

## 功能

- 📊 AQI（中国/美国/澳大利亚/加拿大/英国/欧盟/印度/荷兰标准）
- 🌫️ PM2.5、PM10、O3、NO2、CO、SO2
- 🌸 花粉浓度（桦木/草/桤木/橄榄树/豚草/艾蒿）+ 过敏风险指数
- 🌡️ 天气：温度、湿度、风速、风向、紫外线指数
- 🍃 两种地点选择：搜索 或 6级层级浏览（洲→国家→地区→城市→区→街道）
- 🔄 可配置刷新间隔

## 安装

### HACS（推荐）
1. HACS → 集成 → 添加自定义仓库：`https://github.com/yahooor/air_quality_cn`
2. 搜索 "Air Quality CN" 安装
3. 重启 Home Assistant

### 手动安装
1. 下载 [air_quality_cn.zip](https://github.com/yahooor/air_quality_cn/releases/latest)
2. 解压到 `custom_components/` 目录
3. 重启 Home Assistant

## 配置

设置 → 设备与服务 → 添加集成 → 搜索 "Air Quality CN"

## 传感器

| 传感器 | 说明 |
|--------|------|
| AQI | 空气质量指数（可配置标准）|
| 空气质量等级 | 优/良/中等/轻度污染等 |
| PM2.5 / PM10 | 颗粒物（μg/m³）|
| O3 / NO2 / SO2 / CO | 气态污染物（μg/m³）|
| 花粉浓度 | 总花粉（原始范围字符串）|
| 花粉浓度范围最大值 | 花粉范围最大值（数值，用于历史图表）|

### v2.3.6
- 修复：搜索结果选择器选项处理问题

### v2.3.5
- 修复：搜索结果选择器UI问题

### v2.3.4
- 修复：花粉浓度单位冲突，`粒/千平方毫米` vs `粒/m³`

### v2.3.3
- 修复：数据更新时间时区问题，移除UTC转换，使用本地时间显示

### v2.3.2
- 优化：数据源更新，sitemap 入口支持更稳定的 AQI 数据获取
- 优化：中国数据覆盖提升至 **97.7%**（8,475/8,491 地点有 AQI 数据）

### v2.3.1
- 修复 `POLLEN_TYPES` 映射表 key 重复冲突：桤木花粉此前误映射到 `pollen_birch`，已修正为 `pollen_alder`；`野草花粉` 重复 key 已去重
- 修复 `aiohttp` 请求 `timeout` 参数：改为传入 `aiohttp.ClientTimeout(total=30)`，避免 `ValueError`
- 修复 `update_time` 时区处理：页面时间无时区标注时统一视为 UTC，不再强制加 +8，解决部分环境下"9小时偏差"问题
- 修复搜索路径 URL 拼接：防御 `url_key` 或 `place_id` 为空时产生双斜杠导致 404 的问题
- 修复花粉传感器 `available` 属性：非花粉季花粉值为 `None` 时传感器仍显示为"可用"，HA 显示"未知"而非"不可用"
- 修复 README 层级描述：更新为正确的 6 级层级（洲→国家→地区→城市→区→街道）

### v2.3.0
- 修复花粉传感器：pollen 显示原始范围（如 "301~500"），pollen_max 显示数值（500）
- 修复温度传感器：兼容数值与单位之间含特殊字符的页面
- 修复紫外线传感器：不再硬编码最大值为 11

## License

MIT
