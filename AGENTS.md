# AGENTS.md — cc-switch-hub 用量条

Windows 任务栏窄条 + macOS 菜单栏常驻用量条，显示 Claude Code（经 cc-switch）今日用量 / 花费 / 近用模型 + 套餐厂商额度。Windows 用 PySide6，macOS 用 rumps，按 `sys.platform` 分支。本文件是下次开发必须遵守的规则手册。

## 环境与命令（重要）

### Windows

- **必须用 tool python**：`E:/program/tool/python/python.exe`（3.12.8）。**不要用 Anaconda**——其 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。
- 运行：`"E:/program/tool/python/python.exe" src/main.py`
- 装包：`"E:/program/tool/python/python.exe" -m pip install PySide6`

### macOS

- 运行：`pip install rumps` 后 `python src/main.py`
- 打包：`pip install py2app rumps` → `cd build && python mac_setup.py py2app`（详见 README）

### 通用

- 测试：`"E:/program/tool/python/python.exe" -m pytest tests/ -v`（根 `conftest.py` 已把 `src/` 加进 sys.path；Mac 端 rumps/AppKit 代码 Windows 跑不了，纯函数 `mac_text` 可测）

## 模块结构

**数据层（平台无关，两边复用）**：
- `src/usage_reader.py`：只读 db 汇总今日 token / 花费 / 近用模型 → `get_today_usage(db_path)`
- `src/quota_fetcher.py`：`get_current_provider` 读当前厂商、`detect_provider_type` 判型、`fetch_kimi_quota` / `fetch_zhipu_quota` / 统一入口 `fetch_quota`
- `src/display_text.py`：纯函数格式化（Windows 用）

**Windows UI**：
- `src/widget.py`：`UsageWidget` 无边框窗口（`update_data`、`_stale` 变灰、`moved` / `refresh_requested` 信号）
- `src/main.py` 的 `run_windows()`：30s/5min QTimer、`QuotaWorker`(QThread) 后台额度、托盘、位置记忆

**macOS UI**：
- `src/mac_text.py`：纯函数 `build_title` / `ring_ratio` / `build_menu_items`（不依赖 rumps，Windows 可测）
- `src/mac_bar.py`：`MacUsageBar(rumps.App)` + `ring_image`（NSImage 单色进度环）+ `@rumps.timer` + `threading` 后台额度；`run()` 入口
- `src/main.py` 的 `run_mac()`：调 `mac_bar.run()`

**入口**：
- `src/main.py`：顶部不 import PySide6（Mac 加载不崩）；`main()` 按 `sys.platform` 分支 `run_windows` / `run_mac`；`QuotaWorker` / `_make_tray_icon` 是 `run_windows` 内局部定义（依赖 PySide6）

## 数据与坑点（反复踩过的，勿再犯）

### 通用（数据层）
- db 路径 `~/.cc-switch/cc-switch.db`，**只读连接** `file:{path}?mode=ro` + `uri=True`。
- **`proxy_request_logs.provider_id` 是占位值 `'_session'`**，不存真实厂商标识 → 今日用量**全部汇总**，不要改回按厂商过滤。
- 当前激活厂商读 `~/.cc-switch/settings.json` 的 `currentProviderClaude`（id）→ db 查 base_url / token。**不要用 db 的 `is_current`**（实测动态变化、不可靠）。
- **智谱额度接口 Authorization 不加 Bearer**（Kimi 要加）。URL `{base}/api/monitor/usage/quota/limit`，解析 `data.limits[]` 里 `type==TOKENS_LIMIT`、`unit==3`→5h / `unit==6`→周。
- 厂商不识别（ollama / 日日新 / Xiaomi MiMo 等）→ 额度显示 `--`；查询失败 → 保留上次数据变灰（stale），勿清空。

### Windows
- QThread 必须用集合（`_workers`）持有引用直到 `finished`，否则被 GC 触发 `QThread destroyed while running` 启动崩溃。
- 富文本 QLabel 会拦截鼠标事件导致拖不动 → `WA_TransparentForMouseEvents`；富文本不支持 `AlignVCenter` → 圆点与文字拆双纯文本 label。

### macOS
- rumps `App.icon` 默认 template 模式（单色），彩色需直接操作 `NSStatusItem.button.image.setTemplate_(False)` → 改用单色进度环，填充比例承载水位。
- Cocoa UI 更新必须在主线程 → 后台 `threading.Thread` 查额度只做整体引用替换 `self._quota`（原子）+ dirty 标志，主线程 `rumps.timer` 检测后刷 UI。
- `mac_bar.py` 菜单动态文本 `self.menu[i].title` 是否生效待真机验证；stale 行用第 6 占位 menu 项避免索引越界。
- py2app `APP` 路径用 `__file__` 基准（`os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'main.py')`），不依赖 cwd。
- `mac_bar.py` 依赖 rumps/AppKit，**Windows 跑不了**，只 `ast.parse` 验语法；真机验证靠 Mac。

## 规范

- commit：`type: 中文描述`（feat / fix / docs / test 等），`git config user.name zaynzhu`（不设邮箱）。
- 每个独立改动验证后单独 commit，保持原子性。
- 风格：4 空格缩进、snake_case、中文注释、英文标识符。

## 文档指针

- 设计文档：`docs/superpowers/specs/`
- 实现计划：`docs/superpowers/plans/`
- 面向人说明：`README.md`（中文）/ `README_EN.md`（英文）

## 运行时文件

- `src/settings.json` 是窄条位置记忆，运行时生成，**不应入库**（当前仍被 git 跟踪，建议 `git rm --cached src/settings.json` + `.gitignore` 加 `src/settings.json`）。