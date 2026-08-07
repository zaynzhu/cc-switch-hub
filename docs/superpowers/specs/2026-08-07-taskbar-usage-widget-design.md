# cc-switch-hub 任务栏用量条 设计文档

日期：2026-08-07
状态：已确认，待实现

## 背景与目标

用户通过 cc-switch 接入第三方厂商（当前为 Kimi For Coding）使用 Claude Code。cc-switch 已能在点开托盘时显示额度和用量，但用户希望**不点开托盘**就能常驻看到：

- 当前厂商 / 模型
- 今日 token 用量
- 今日估算花费
- 厂商套餐额度（5 小时窗口 + 周额度）

这些数据 cc-switch 已经在本地维护，本工具复用其数据库与配置，不重复造轮子。

## 数据源（已验证）

cc-switch 本地数据库路径：`C:\Users\OMEN\.cc-switch\cc-switch.db`（WAL 模式）。

### 1. 今日用量与花费 —— `proxy_request_logs` 表（全部汇总）

明细表，每条请求已算好成本。关键字段：`created_at`（Unix 秒）、`model`、`input_tokens`、`output_tokens`、`cache_read_tokens`、`cache_creation_tokens`、`total_cost_usd`。

> **重要**：该表 `provider_id` 字段对 session_log 来源的记录是占位值 `'_session'`，不存真实厂商标识（实测近 7 天 623 条全为 `'_session'` / `'_opencode_session'`），无法按厂商过滤用量。故今日用量**全部汇总**（跨所有厂商），反映"今天 Claude Code 总共用了多少 token、花了多少"。

查询：按"今天"过滤（`date(created_at, 'unixepoch', 'localtime') = date('now', 'localtime')`），聚合 `SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens)` 作为今日 token 总量，`SUM(total_cost_usd)` 作为今日花费。各厂商的 total_cost 已各自按其价格表算好，汇总即真实总花费。

> 不使用 `usage_daily_rollups` 表——实测该表停在 2026-07-08，已停止更新；明细表实时同步（data_source=session_log）。

### 2. 最近使用的模型 —— `proxy_request_logs` 表

取最近一条记录的 `model` 字段（如 "kimi-k3"），作为"近用"模型名显示。不取 cc-switch 当前激活 provider——实测 `is_current` 动态变化，且与最近实际活动不一致（当前激活 ollama 但最近仍在用 kimi-k3）。

### 3. Kimi 套餐额度 —— Kimi For Coding 接口（固定源）

`GET <base_url>/v1/usages`，Header `Authorization: Bearer <ANTHROPIC_AUTH_TOKEN>`。

**固定按 `name='Kimi For Coding' AND app_type='claude'` 从 providers 表读配置**（不依赖 is_current），取 `env.ANTHROPIC_AUTH_TOKEN` 和 `env.ANTHROPIC_BASE_URL`，拼接 `base_url.rstrip('/') + '/v1/usages'`。

> 额度源固定为 Kimi，不随当前激活厂商变化。原因：Kimi 是用户主要关心且唯一有额度接口的厂商（v1）；即使切到其他厂商，Kimi 额度窗口仍在走，显示有意义。其他厂商额度接口后续按需支持。

已验证响应结构（套餐制，返回百分比，非余额）：

```json
{
  "usage": {"limit": "100", "used": "68", "remaining": "32", "resetTime": "..."},
  "limits": [
    {"window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
     "detail": {"limit": "100", "used": "78", "remaining": "22", "resetTime": "..."}}
  ]
}
```

- 顶层 `usage` = 周额度（68/100）
- `limits[0]`（duration=300 分钟 = 5 小时）= 5h 窗口（78/100）

## 架构

单 Python 进程（PySide6），四个模块，职责分离：

| 模块 | 职责 |
|---|---|
| `usage_reader.py` | 只读连接 db，全部汇总今日 token / 花费；取最近一条 model 名 |
| `quota_fetcher.py` | 按 name 读 Kimi 配置，后台线程查额度接口，解析 5h 窗口 + 周额度百分比 |
| `widget.py` | 无边框置顶窄条窗口，绘制显示文本、颜色阈值 |
| `main.py` | 启动、定时刷新调度、托盘退出菜单、窗口位置记忆 |

模块间通过 Qt 信号通信，额度查询在独立线程，不阻塞 UI。

## 显示效果

```
[今日 69.4M tok · $60.73 · 近用 kimi-k3 | 5h 78% · 周 68%]
```

一行窄条，贴在屏幕右下角任务栏上沿。额度超 80% 变橙、95% 变红。
鼠标悬停 tooltip 显示完整数字：精确 token 数、美元花费、5h/周额度的重置时间。

## 窗口行为

- 无边框、不抢焦点、不出现在任务栏和 Alt-Tab（`Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`）
- 默认可拖动调整位置，位置写入本地 `settings.json` 记忆，下次启动恢复
- 右键菜单：立即刷新 / 退出

## 数据流与刷新策略

- 每 **30 秒**查一次本地 db（只读，WAL 模式不影响 cc-switch 运行）
- 每 **5 分钟**在后台线程查一次额度接口（对齐 cc-switch 的 autoQueryInterval=5）
- 额度查询结果通过信号回主线程更新 UI，避免跨线程直接操作 widget

## 错误处理

- db 文件不存在或表缺失 → 显示 `今日 -- tok · $-- | 5h -- · 周 --`，不弹窗不崩溃
- Kimi 配置查不到（name='Kimi For Coding' 不存在）→ 额度部分隐藏，仍显示今日用量/花费
- 额度接口超时/失败 → 保留上次数据，额度部分颜色变灰表示过期
- token 失效（401）→ 额度部分显示 `需检查 key`

## 测试

- `usage_reader`：用临时 sqlite 构造几条 `proxy_request_logs` 明细，验证按"今天"过滤、token/花费聚合正确、跨天不串
- `quota_fetcher`：mock 响应 JSON，验证 5h 窗口与周额度百分比解析、重置时间解析
- 窗口/定时部分手动验证

## 交付与自启

- 开发期：`pythonw main.py` 直接运行
- 满意后加开机自启（启动文件夹放快捷方式），暂不做 PyInstaller 打包

## 依赖

- Python（Anaconda，已具备）
- PySide6（`pip install PySide6`，装进 anaconda）

## 不做（YAGNI）

- 不支持多厂商额度接口（v1 只 Kimi）
- 不做打包成 exe（后续按需）
- 不做历史曲线/图表
- 不写回 cc-switch 的数据库