# Air Quality CN (在意空气)

Home Assistant 自定义集成，通过 [air-quality.com](https://air-quality.com) 获取全球空气质量数据。

v3.0 起数据获取优先使用站点自身的 JSON 数据接口（读数、按标准计算的等级、花粉、历史趋势、天气、预报一次拿全），接口异常时自动回退到页面解析，稳定性大幅提升。

## 功能

| 功能类别 | 具体内容 |
|--------|----------|
| 🌍 全球覆盖 | 支持全球 195+ 国家、248000+ 监测点的空气质量数据 |
| 📊 AQI 标准 | 中国/美国/澳大利亚/加拿大/英国/欧盟/印度/荷兰标准，**添加后可随时在选项中切换** |
| 🏷️ 等级 | 各污染物与 AQI 等级由站点按所选标准计算返回（不再按中国标准硬编码推导） |
| 🌫️ 污染物 | PM2.5、PM10、O3、NO2、CO、SO2（附各自等级与健康首要污染物） |
| 🌸 花粉 | 桦木/草/桤木/橄榄树/豚草/艾蒿 + 过敏风险指数 |
| 🌡️ 天气 | 温度、体感温度、湿度、风速、风向、紫外线指数、天气状况 |
| 📈 趋势 | 24 小时 AQI 趋势（上升/下降/持平）、均值与峰值 |
| 📅 预报 | 5 天 AQI 预报（附在 AQI 传感器属性中） |
| 🔍 搜索 | 支持中文/英文地点搜索添加 |
| 🔄 更新 | 可配置刷新间隔 |
| 🚫 防重复 | 同一地点不可重复添加 |
| 🛡️ 双通道 | JSON 接口为主，页面解析自动回退 |

## 安装

### HACS（推荐）

1. HACS → 集成 → 添加自定义仓库：`https://github.com/yahooor/air_quality_cn`
2. 搜索 "Air Quality CN" 安装
3. 重启 Home Assistant

### 手动安装

1. 下载 [最新版本](https://github.com/yahooor/air_quality_cn/releases/latest)
2. 解压到 `custom_components/` 目录
3. 重启 Home Assistant

## 配置

设置 → 设备与服务 → 添加集成 → 搜索 "Air Quality CN"

### 添加流程（两步）

1. **搜索地点**：输入城市、地区或监测站名称（支持中文或英文，如"北京"、"朝阳区"、"奥体中心"）
2. **选择 AQI 标准**：选择你要使用的空气质量指数标准（中国用户推荐 AQI 中国标准）

### 选项配置

已添加的集成 → 配置，可随时修改：

- **AQI 标准**：切换后自动重新加载数据，无需删除重加
- **刷新间隔**：默认 30 分钟，最小 5 分钟

## 传感器

| 传感器 | 说明 |
|--------|------|
| aqi | 空气质量指数（可配置标准）。属性中附 5 天预报、24h 趋势/均值/峰值、首要污染物 |
| air_quality_level | 空气质量等级（优/良/轻度污染/中度污染等，按所选标准计算） |
| primary_pollutant | 首要污染物 |
| aqi_trend | 24 小时 AQI 趋势（上升/下降/持平） |
| pm25 / pm10 | 颗粒物（μg/m³，附各自等级） |
| o3 / no2 / so2 / co | 气态污染物（μg/m³，附各自等级） |
| pollen | 花粉浓度（原始范围字符串） |
| pollen_max | 花粉范围最大值（数值，用于历史图表） |
| pollen_birch / grass / alder / olive / ragweed / mugwort | 各类花粉浓度（粒/m³） |
| allergy_risk | 过敏风险指数 |
| weather_condition | 天气状况（晴/多云/雨等） |
| temperature / feel_like | 温度 / 体感温度 |
| humidity / wind_speed / wind_direction / wind_degrees / uv_index | 湿度、风速、风向、风向角度、紫外线指数 |
| update_time | 数据更新时间（站点时间为 UTC，HA 自动转换为本机时区显示） |

## 更新日志

### v3.0.0 (2026-10-24)

**数据源重构**：优先使用站点 JSON 数据接口，接口异常时自动回退页面解析。

- **新增**：5 天 AQI 预报（AQI 传感器属性）
- **新增**：首要污染物传感器
- **新增**：24 小时 AQI 趋势传感器（上升/下降/持平，附均值/峰值/变化量）
- **新增**：体感温度、天气状况传感器
- **新增**：各污染物等级属性（由站点按所选 AQI 标准计算，非中国标准下的等级不再错误套用中国分级）
- **新增**：选项中可直接切换 AQI 标准，无需删除重加
- **修复**：update_time 时区错误——站点原始时间为 UTC，此前误标为 UTC+8 导致显示偏差 8 小时
- **修复**：解析失败时 update_time 不再回退为"当前时间"，避免掩盖数据过期
- **优化**：花粉数值直接来自结构化数据（含等级），欧洲花粉监测点全覆盖
- **优化**：O3/NO2/SO2/CO/UV 使用标准 device_class，支持长期统计
- **优化**：刷新间隔最小值 1 → 5 分钟
- **工程**：新增单元测试（12 项，真实站点响应快照作回归夹具）、GitHub Actions CI（测试 + hassfest + HACS 校验）、LICENSE 文件

> 升级提示：O3/NO2/SO2/CO/UV 的单位与 device_class 有调整，个别实体的历史统计可能提示单位变更，属预期行为；如有需要删除受影响实体让其重建即可。旧配置条目首次刷新时会自动补全地点坐标，无需重新添加。

### v2.6.3 (2026-05-07)
- **优化**：`curWeatherData` 解析前增加 `null` 检查，避免骨架页时遍历整个页面
- **优化**：`update_time` 正则简化，避免过度匹配
- **修复**：`all_none` 健康警告排除 `update_time`，使警告在所有数据为空时正确触发

### v2.6.2 (2026-05-07)
- **修复**：移除 `hacs.json` 中的 `zip_release` 配置，修复 HACS 安装报错 `NoneType object has no attribute 'endswith'`

### v2.6.1 (2026-05-06)
- **修复**：`hacs.json` 中 `zip_release` 类型错误（字符串→布尔值）

### v2.6.0 (2026-05-06)
- **优化**：移除未使用的 `import asyncio`
- **修复**：`POLLEN_KEYS` 中补充缺失的 `pollen_total`
- **优化**：简化 `update_time` 冗余判断
- **优化**：合并花粉赋值重复逻辑（3处→1处）
- **文档**：README 补充 v2.5.1/v2.5.2/v2.5.3 更新日志
- **配置**：`hacs.json` 添加 `zip_release`

### v2.5.3 (2026-05-05)
- **修复**：HACS 商店图标不显示（`brand/icon.png` 需在仓库根目录）

### v2.5.2 (2026-05-05)
- **修复**：无效/过期 place_id 导致所有传感器无数据（新增骨架页检测）

### v2.5.1 (2026-05-01)
- **修复**：`dt` 变量未初始化导致 NameError
- **修复**：迁移函数无条件写库（添加早期返回）
- **优化**：变量 `_q` 重命名为 `_QUOTE_RE`
- **优化**：提取 `_build_search_options()` 方法减少重复代码
- **优化**：搜索结果上限 20→50

### v2.5.0 (2026-04-29)
- **修复**：`ConfigFlow.VERSION` 类型错误（字符串→整数），符合 HA 官方规范
- **修复**：迁移函数改为 HA 标准 `async_migrate_entry`，彻底解决 `Migration handler not found` 警告
- **修复**：搜索关键词中文 URL 编码，避免请求失败
- **修复**：update_time 时区处理，统一使用 UTC+8 时区信息
- **新增**：同一地点不可重复添加（unique_id 去重）
- **优化**：POLLEN_KEYS 提取为模块级常量，减少重复创建
- **清理**：删除 `__pycache__/`、`.backup_redundant/`，新增 `.gitignore`

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
