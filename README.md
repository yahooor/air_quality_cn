# 在意空气 (Air Quality CN)

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant 集成，通过抓取 [air-quality.com](https://air-quality.com) 网页获取空气质量数据。

## 功能

- 实时 AQI 数据（支持中国、美国、澳大利亚标准）
- 六大污染物监测：PM2.5、PM10、O3、NO2、CO、SO2
- 花粉浓度
- 天气数据：温度、湿度、风速、风向、紫外线指数
- 数据更新时间

## 安装

### HACS（推荐）
1. 安装 [HACS](https://hacs.xyz/)
2. 进入 HACS → 集成 → ... → 添加自定义仓库
3. 填入：`https://github.com/yahooor/air_quality_cn`
4. 搜索并安装「在意空气」

### 手动安装
1. 下载 release 中的 `air_quality_cn.zip`
2. 解压到 `custom_components/air_quality_cn/`
3. 重启 Home Assistant

## 配置

1. Home Assistant → 设置 → 设备与服务
2. 点击「添加集成」
3. 搜索「在意空气」或「Air Quality CN」
4. 按提示填写地点和 AQI 标准

## 调试

```yaml
logger:
  default: info
  logs:
    custom_components.air_quality_cn: debug
```

## 支持的城市

中国：北京、上海、广州、深圳、成都、杭州、武汉、西安、南京、重庆、天津、苏州等

亚太：东京、首尔、曼谷、新加坡、悉尼、墨尔本、台北、香港、澳门、雅加达、吉隆坡

欧洲：伦敦、巴黎、柏林、罗马、马德里、阿姆斯特丹、维也纳、布拉格、华沙、莫斯科、斯德哥尔摩

美洲：纽约、洛杉矶、旧金山、温哥华、多伦多、墨西哥城、圣保罗

## 许可证

MIT License
