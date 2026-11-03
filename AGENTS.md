# AGENTS.md — air_quality_cn

> 给 AI 会话与新协作者的项目约定。状态类信息（版本、待办）看 README 与仓库根外的工作区记忆，
> 本文件只记「怎么干活」。

## 一句话

Home Assistant 自定义集成，抓 air-quality.com（在意空气）的 AQI / 污染物 / 天气数据，
每个地点生成一套传感器。当前 v2026.11.3-1。

## 跑测试

```bash
pip install -r requirements-dev.txt   # pytest / jsonschema / aiohttp / ruff
pytest -q                             # 期望 30 passed
ruff check .                          # 必须全绿
```

`tests/test_api.py` 不需要 HA；`tests/test_contracts.py` 需要 `jsonschema`（契约校验上游响应结构）。

## 发版（用户固定流程，五步不能省）

```bash
# 1 改 manifest.json 的 version（CalVer: 2026.M.D-N，用户主导该方案，勿改）
# 2 提交并推送
git commit -am "..." && git push
# 3 打 tag + GitHub release（HACS 版本号取自 tag）
git tag v2026.M.D-N && git push origin v2026.M.D-N
gh release create v2026.M.D-N --title "..." --notes "..."
# 4 HACS 更新
haops hacs update yahooor/air_quality_cn --version v2026.M.D-N
# 5 读日志 + 实机实体状态验证（不能只看下载 success）
haops ping && haops logs -n 40 --level ERROR && haops states zhao_yang
```

## 架构要点

| 文件 | 作用 | 注意 |
|---|---|---|
| `api.py` | 上游接口层，**不依赖 homeassistant**（可独立单测） | 改解析必跑 pytest；`readings_kinds` 记录上游实际提供哪些字段 |
| `sensor.py` | 传感器与 `available` / `extra_state_attributes` | **`available` 只表达协调器状态**，不要用它表达「这个字段没值」——HA 不渲染不可用实体的属性，说明会被吞（见 `docs/FAILURE_MODES.md` FM-14） |
| `docs/FAILURE_MODES.md` | 已知 14 条失效模式 | 新功能先对照它，别重复踩坑 |

- 两个实例：永定新区（5 参数站，无 CO/SO2）、朝阳区（7 参数站）。**上游不提供的字段属数据源限制，不是 bug**
- 花粉类字段中国站点一律没有（仅欧洲站点提供）

## 红线

- **不要跑 `ruff format`**：仓库只启用 lint，未启用 format。本地 ruff 版本差异会把 11 个文件重排成假 diff
- 不要为「让测试好看」而删测试；契约测试是防上游改结构的唯一屏障
- 实体 ID 依赖拼音转换（朝 = `zhao` 不是 `chao`），查实体前先 `haops ws config_entity_registry/list`
