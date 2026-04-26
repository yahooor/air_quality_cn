# Air Quality CN (在意空气)

Home Assistant 自定义集成，通过抓取 [air-quality.com](https://air-quality.com) 获取全球空气质量数据。

## 功能

- 🌍 支持全球 195+ 国家、2000+ 地区、33000+ 城市、**248000+ 区**的空气质量数据
- 📊 AQI（中国/美国/澳大利亚/加拿大/英国/欧盟/印度/荷兰标准）
- 🌫️ PM2.5、PM10、O3、NO2、CO、SO2
- 🌸 花粉浓度（桦木/草/桤木/橄榄树/豚草/艾蒿）+ 过敏风险指数
- 🌡️ 天气：温度、湿度、风速、风向、紫外线指数
- 🔍 两种地点选择：搜索 或 5级层级浏览（洲→国家→地区→城市→区）
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

### v2.3.1
- 修复空气质量等级：从 AQI 数值推导等级，解决部分页面 HTML 无中文等级文本的问题

### v2.3.0
- 修复花粉传感器：pollen 显示原始范围（如 "301~500"），pollen_max 显示数值（500）
- 修复温度传感器：兼容数值与单位之间含特殊字符的页面
- 修复紫外线传感器：不再硬编码最大值为 11

## License

MIT
