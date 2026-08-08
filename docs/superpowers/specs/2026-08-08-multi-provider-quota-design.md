# 多厂商额度跟随 + 细节打磨 设计文档

日期：2026-08-08
状态：已确认范围，待实现

## 背景

任务栏用量条 v1 已上线（Kimi 额度 + 今日用量/花费 + 近用模型）。本阶段做两件增强：

1. **多厂商额度跟随**：额度从"固定查 Kimi"改为"跟随 cc-switch 当前激活厂商"，支持 Kimi + 智谱 GLM 两类套餐制厂商
2. **细节打磨**：终审遗留的三项小问题（托盘图标兜底、退出线程竞态、测试边界+代码清理）

## 一、多厂商额度跟随

### 范围

- 实现 detect 机制 + **Kimi**（现有）+ **智谱 GLM**（新增）两个接口
- 不实现 MiniMax / ZenMux / 火山方舟（用户无这些厂商，YAGNI），留 detect 扩展点
- 不在 Kimi/智谱范围内的厂商（ollama、日日新、go、Xiaomi MiMo 等）→ 额度部分显示 `--`

### 当前激活厂商读取（权威来源）

- **首选**：读 `~/.cc-switch/settings.json` 的 `currentProviderClaude` 字段（provider id），再用该 id 查 db `providers` 表取 `settings_config.env.ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
- **原因**：实测 db 的 `is_current` 标志会动态变化且语义不稳定；settings.json 的 `currentProviderClaude` 是 cc-switch 用户设置里的权威当前厂商 id
- **兜底**：settings.json 缺失/无此字段时，退回 db `providers WHERE is_current=1 AND app_type='claude'`

### detect 厂商类型（复刻 cc-switch）

按 base_url 子串判断（与 cc-switch `coding_plan.rs::detect_provider` 一致）：

| 类型 | base_url 匹配 |
|---|---|
| kimi | `api.kimi.com/coding` |
| zhipu | `open.bigmodel.cn` 或 `bigmodel.cn`（CN）、`api.z.ai`（EN） |
| 其他 | 返回 None（显示 `--`） |

### Kimi 接口（现有，不变）

- `GET https://api.kimi.com/coding/v1/usages`，`Authorization: Bearer {api_key}`
- 响应：`limits[]`（duration=300 的 detail = 5h）+ 顶层 `usage` = weekly；used = limit - remaining
- 已实测可用

### 智谱 GLM 接口（新增，复刻 cc-switch，无实测）

- URL：`GET {zhipu_base}/api/monitor/usage/quota/limit`
  - zhipu_base：CN 用 `https://open.bigmodel.cn`，EN 用 `https://api.z.ai`（按用户配置的 base_url 域名判定）
- 请求头：`Authorization: {api_key}`（**注意：不加 Bearer 前缀**）、`Content-Type: application/json`、`Accept-Language: en-US,en`
- 响应解析（`body.data`）：
  - `limits[]` 数组，筛 `type == "TOKENS_LIMIT"`（大小写不敏感）的条目
  - 每条取 `percentage`（使用率，0-100）、`nextResetTime`（毫秒时间戳 → ISO）
  - 窗口分类按 `unit` 字段：`unit == 3` → 5h 窗口，`unit == 6` → weekly 窗口
- **无法实测**（用户无智谱厂商/key），按 cc-switch `coding_plan.rs` 精确复刻，mock 单测验证解析逻辑
- 401/403 → 视为 key 失效（返回 None 走 stale 逻辑）

### 统一返回格式

各厂商查询统一返回（与现有 widget/display_text 兼容）：

```python
{'h5': {'used': int, 'limit': int, 'reset': str|None},
 'weekly': {'used': int, 'limit': int, 'reset': str|None}}
```

- used/limit 均为百分比语义（0-100）：智谱 `percentage` 直接作 used、limit=100；Kimi 沿用现有 used/limit
- 厂商不识别 / 查询失败 → 返回 None（走现有 stale 变灰 / `--` 逻辑）

### 显示

窄条额度部分显示**当前激活厂商**的额度：`... | 5h X% · 周 Y%`。切换厂商后下次刷新（30s/5min）自动跟随。不识别厂商显示 `--`。颜色阈值沿用现有 80/95。

## 二、细节打磨

### 1. 托盘图标兜底

- 现状：`QIcon.fromTheme('dialog-information')` 在 Windows 无图标主题，可能返回空白图标
- 修复：程序生成一个纯色 `QPixmap`（如 16x16 圆角色块）作为托盘图标，不依赖系统主题

### 2. 退出线程竞态

- 现状：托盘「退出」时若有 QuotaWorker 正在网络查询，进程退出可能报 `QThread destroyed while running`
- 修复：`app.aboutToQuit` 信号里对 `_workers` 中的 worker 调 `wait(超时)`（如 2000ms），等其结束再退出

### 3. 测试边界 + 代码清理

- 补测试边界：`format_tokens(1000)` 精确 1K、`quota_color(used, 0)`、format_quota/quota_color 非对称 None
- 清理 unused import：`src/main.py` 的 `Qt`、`tests/test_widget.py` 的 `QApplication`
- `save_settings` 加 `try/except OSError` 兜底（load 侧已有）

## 架构改动

- `quota_fetcher.py` 重构：新增 `get_current_provider(db_path, settings_path)`、`detect_provider_type(base_url)`、`fetch_zhipu_quota(base_url, api_key)`；`fetch_kimi_quota` 保留；新增统一入口 `fetch_quota(base_url, api_key)` 按 detect 分发
- `main.py`：refresh_quota 改用 `get_current_provider` + `fetch_quota`（替代原 get_kimi_config + fetch_kimi_quota）；加托盘图标兜底、aboutToQuit 竞态处理
- `widget.py`：不变（显示逻辑兼容统一返回格式）
- 测试：quota_fetcher 新增 detect/get_current_provider/zhipu 解析单测；补测试边界

## 错误处理

- 当前厂商读不到（settings.json + db 都无）→ 额度显示 `--`
- 厂商不识别（非 kimi/zhipu）→ 额度显示 `--`
- 查询失败/超时 → 沿用现有 stale 变灰（保留上次数据）
- 401/403 → 视为 key 失效，走 stale 逻辑

## 测试

- `get_current_provider`：临时 settings.json + db，验证 id→base_url/token 解析、兜底到 is_current
- `detect_provider_type`：各 base_url 命中/不命中
- `fetch_zhipu_quota`：mock 响应，验证 TOKENS_LIMIT 筛选、percentage 提取、unit 3/6 窗口分类、nextResetTime 转换
- 统一入口 `fetch_quota`：kimi/zhipu 分发、不识别返回 None
- 细节打磨项的回归测试

## 不做（YAGNI）

- MiniMax / ZenMux / 火山方舟接口（用户无这些厂商）
- 第三方余额查询（DeepSeek/SiliconFlow 等，用户未要求）
- 多厂商同时显示（只跟随当前激活厂商，一行）
- 自定义 js 脚本引擎（用户用内置两类即可）