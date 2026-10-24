# 失效模式清单（Failure Modes）

> 本文件是"上游会怎么变 / 集成会怎么坏"的系统清单。每条含：触发条件、症状、当前缓解、残余风险。
> 按项目纪律，**新功能只允许从本清单中挑选**（缓解某条失效模式），不做凭空设想。

## 上游（air-quality.com）侧

### FM-1 响应结构变更（字段改名/嵌套变化）
- **触发**：站点改版（历史上已多次：Gauge→单引号 class、name/value 结构变化）。
- **症状**：所有解析字段为空（"所有解析字段均为空"告警）；实体 unknown。
- **缓解**：契约测试（`tests/test_contracts.py`）用未裁剪原始响应锁定结构；CI 每日 canary 实测线上接口校验 jsonschema 契约（`.github/workflows/canary.yml`）；运行时"全空字段"告警。
- **残余**：渐进式变更（值域变宽、新增字段）不会触发 schema 违约——schema 有意宽松（additionalProperties: true）。

### FM-2 响应字段存在性差异（同结构不同字段）
- **实测例**：bulletins 中"降雨提醒"条目无 `type` 字段，仅 MAIN_POLLUTANT 有（契约测试第一版因此修正）。
- **缓解**：解析代码一律 `.get()` 防御；契约以原始数据为准而非想象。

### FM-3 慢链路超时
- **实测**：HA 容器到站点 10s+ 常态，nearby 响应 150KB。
- **缓解**：全接口 30s 超时；nearby 与读数独立获取、失败 info 记录下次重试；坐标解析失败 1h 退避；HTML 回退只补缺失字段。
- **残余**：回退路径依赖 HTML 结构（FM-1 的旧式风险仍在回退通道存在）。

### FM-4 骨架页 / place_id 失效
- **特征**：`1970-01-01` + 页面 <25KB。
- **缓解**：`SkeletonPageError` 显式抛出 → UpdateFailed → 实体 unavailable（诚实语义）。

### FM-5 时区语义
- **实测**：站点全部时间串为 UTC（页面 JS 用 moment.utc().local()）。
- **缓解**：统一 `timezone.utc` 解析；曾修复误标 UTC+8 的 bug（v3.0.0）。

### FM-6 数据源能力差异
- **实测**：5 参数站（永定新区：无 co/so2/bulletins）vs 7 参数站（朝阳区）；花粉 kind 仅欧洲监测点提供；UV 夜间为 0。
- **缓解**：`readings_kinds` 记录实际能力 → 无数据传感器属性给出原因说明（note）。

## Home Assistant 平台侧

### FM-7 HA 版本移除枚举/常量（已发生 3 次）
- **实测**：`UnitOfUVIndex`、`SensorDeviceClass.UV_INDEX`、`SensorDeviceClass.CARBON_MONOXIDE` 在 2026.10 被移除。
- **缓解**：`_dc()`/`_unit()`/`_const()` 按名动态获取 + 等值字符串回退；hacs.json 声明最低版本。

### FM-8 recorder 统计单位漂移
- **实测**：v3.0.0 单位 "UVI"→"UV index" 触发统计抑制告警。
- **缓解**：已修元数据（WS `recorder/update_statistics_metadata`）。未来任何单位变更必须视为破坏性变更，发版说明标注并给修复步骤。

### FM-9 首刷阻塞 setup
- **实测**：慢链路下首刷 >10s 触发 "Setup ... taking over 10 seconds" 告警。
- **缓解**：无（首刷在 setup 内 await）。
- **候选修复（下轮）**：首刷改后台任务，实体先以 unavailable 创建。**注意**：会改变"启动即有数据"行为，属行为变更，需独立评估。

### FM-10 平台并发加载竞态（已修）
- coordinator 上移集成级创建，两平台共享。

## 发布与协作流程侧

### FM-11 已发布 tag 不可变（事故已发生）
- v3.0.0/3.0.1 曾因未推送/并行会话而移动 tag。
- **纪律**：tag 一经发布绝不移动；修发一律新 tag；release.py 有未推送防护。

### FM-12 并行会话写冲突
- 同仓库曾有并行会话同时改代码。
- **纪律**：动手前 `git fetch`；编辑后 grep 函数名确认无重复定义（曾发生桩函数覆盖完整 setup 的事故）。

### FM-13 验证通道失效（本次实测）
- **实测**：日志文件读取四路全阻（supervisor 透传 unknown_error / Filebrowser ingress iframe / 8124 waxgourd 需登录 / Samba 无凭据）；WAQI demo token `/feed/beijing` 返回上海站。
- **缓解**：DB 证据（recorder）替代日志文件；第三方仲裁必须验证其自身可信度（时间戳/站名）后才能采信。

## 本轮依据证据的处置结论

| 失效模式 | 本轮证据 | 处置 |
|---|---|---|
| FM-1 | canary 四端点 PASS（本机 + CI） | 缓解已建，持续监控 |
| FM-2 | bulletins 无 type——schema 修正 | 契约以原始数据为准 |
| FM-8 | 56 实体单位 0 漂移；UV 统计恢复 | 无需行动 |
| FM-9 | 刷新窗口内 0 告警 | 下轮候选 |
| FM-13 | WAQI demo 返回上海站 | 仲裁用 aqicn.org 页面通道 |
| 端点覆盖 | 5 端点中 4 个已用；get_ranking/config/change_lang 未用 | 无缺口；get_ranking 仅在 FM 清单外需求出现时评估 |
