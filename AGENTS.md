# AGENTS.md — cc-switch-hub 任务栏用量条

Windows 任务栏常驻窄条，显示 Claude Code（经 cc-switch）今日用量 / 花费 / 近用模型 + 套餐厂商额度。PySide6 单进程。本文件是下次开发必须遵守的规则手册。

## 环境与命令（重要）

- **必须用 tool python**：`E:/program/tool/python/python.exe`（3.12.8）。**不要用 Anaconda**——其 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。
- 运行：`"E:/program/tool/python/python.exe" src/main.py`
- 测试：`"E:/program/tool/python/python.exe" -m pytest tests/ -v`（根 `conftest.py` 已把 `src/` 加进 sys.path）
- 装包：`"E:/program/tool/python/python.exe" -m pip install <pkg>`
- 命令行直接调 src 模块（非 pytest）需加 `PYTHONPATH=src` 前缀

## 模块结构

- `src/usage_reader.py`：只读 db 汇总今日 token / 花费 / 近用模型 → `get_today_usage(db_path)`
- `src/quota_fetcher.py`：`get_current_provider` 读当前厂商、`detect_provider_type` 判型、`fetch_kimi_quota` / `fetch_zhipu_quota` / 统一入口 `fetch_quota`
- `src/display_text.py`：纯函数格式化（无 I/O，可无 GUI 测试）
- `src/widget.py`：`UsageWidget` 无边框窗口（`update_data`、`_stale` 变灰、`moved` / `refresh_requested` 信号）
- `src/main.py`：入口调度（30s/5min 定时器、`QuotaWorker` 后台线程、托盘、位置记忆）

## 数据与坑点（反复踩过的，勿再犯）

- db 路径 `~/.cc-switch/cc-switch.db`，**只读连接** `file:{path}?mode=ro` + `uri=True`。
- **`proxy_request_logs.provider_id` 是占位值 `'_session'`**，不存真实厂商标识 → 今日用量**全部汇总**，不要改回按厂商过滤。
- 当前激活厂商读 `~/.cc-switch/settings.json` 的 `currentProviderClaude`（id）→ db 查 base_url / token。**不要用 db 的 `is_current`**（实测动态变化、不可靠）。
- **智谱额度接口 Authorization 不加 Bearer**（Kimi 要加）。URL `{base}/api/monitor/usage/quota/limit`，解析 `data.limits[]` 里 `type==TOKENS_LIMIT`、`unit==3`→5h / `unit==6`→周。
- 厂商不识别（ollama / 日日新 / Xiaomi MiMo 等）→ 额度显示 `--`；查询失败 → 保留上次数据变灰（stale），勿清空。
- QThread 必须用集合（`_workers`）持有引用直到 `finished`，否则被 GC 触发 `QThread destroyed while running` 启动崩溃。

## 规范

- commit：`type: 中文描述`（feat / fix / docs / test 等），`git config user.name zaynzhu`（不设邮箱）。
- 每个独立改动验证后单独 commit，保持原子性。
- 风格：4 空格缩进、snake_case、中文注释、英文标识符。

## 文档指针

- 设计文档：`docs/superpowers/specs/`
- 实现计划：`docs/superpowers/plans/`
- 面向人说明：`README.md`
