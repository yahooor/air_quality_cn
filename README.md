# 在意空气 (Air Quality CN)

Home Assistant 集成，通过抓取 [air-quality.com](https://air-quality.com) 网页获取空气质量数据。

## 功能

- 实时 AQI 数据（支持中国、美国、澳大利亚标准）
- 六大污染物监测：PM2.5、PM10、O3、NO2、CO、SO2
- 花粉浓度
- 天气数据：温度、湿度、风速、风向、紫外线指数
- 数据更新时间

## 安装

### 方法一：HACS（推荐）

1. 安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中搜索「在意空气」或「Air Quality CN」
3. 点击安装

### 方法二：手动安装

1. 下载 `air_quality_cn.zip`
2. 解压到 `custom_components/air_quality_cn/`
3. 重启 Home Assistant

## 配置

1. 进入 Home Assistant → 设置 → 设备与服务
2. 点击「添加集成」
3. 搜索「在意空气」或「Air Quality CN」
4. 按提示填写地点和 AQI 标准

## AQI 标准说明

| 标准 | 说明 |
|------|------|
| aqi_cn | 中国标准（GB 3096-2012）|
| aqi_us | 美国标准（EPA）|
| aqi_au | 澳大利亚标准 |

## 支持的城市

全球 100+ 城市，包括：
- 中国：北京、上海、广州、深圳、成都、杭州、武汉、西安等
- 亚太：东京、首尔、曼谷、新加坡、悉尼、墨尔本
- 欧洲：伦敦、巴黎、柏林、罗马、马德里、阿姆斯特丹
- 美洲：纽约、洛杉矶、旧金山、温哥华

## 调试

查看 Home Assistant 日志：

```yaml
logger:
  default: info
  logs:
    custom_components.air_quality_cn: debug
```

## 许可证

MIT License
