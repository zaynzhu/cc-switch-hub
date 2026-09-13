# AGENTS.md — cc-switch-hub 用量条

Windows 任务栏窄条 + macOS 菜单栏常驻用量条，显示 Claude Code（经 cc-switch）今日用量 / 花费 / 近用模型 + 套餐厂商额度。Windows 用 PySide6，macOS 用 rumps，按 `sys.platform` 分支。本文件是下次开发必须遵守的规则手册。

## 环境与命令（重要）

### Windows

- **必须用 tool python**：`E:/program/tool/python/python.exe`（3.12.8）。**不要用 Anaconda**——其 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。
- 运行：`"E:/program/tool/python/python.exe" src/main.py`
- 装包：`"E:/program/tool/python/python.exe" -m pip install PySide6`
- 打包：`pyinstaller` 已装则 `powershell -ExecutionPolicy Bypass -File build/win_build.ps1`，产物 `dist/cc-switch-hub.exe`（`--onefile --noconsole`，~47MB，图标 `build/ripple.ico`；**不用** `--collect-all PySide6`，靠 PyInstaller hook 自动收集，否则体积臃肿至 ~248MB）

### macOS

- 运行：`pip install rumps` 后 `python src/main.py`
- 打包：`pip install py2app rumps` → `cd build && python mac_setup.py py2app`（详见 README）。app 图标 `build/ripple.icns`（`mac_setup.py` iconfile），`LSUIElement=true` 纯菜单栏不 Dock

### 通用

- 测试：`"E:/program/tool/python/python.exe" -m pytest tests/ -v`（根 `conftest.py` 已把 `src/` 加进 sys.path；Mac 端 rumps/AppKit 代码 Windows 跑不了，纯函数 `mac_text` 可测）

## 模块结构

**数据层（平台无关，两边复用）**：
- `src/usage_reader.py`：只读 db 汇总今日 token / 花费 / 近用模型 → `get_today_usage(db_path)`
- `src/quota_fetcher.py`：`get_current_provider` 读当前厂商、`detect_provider_type` 判型、`fetch_kimi_quota` / `fetch_zhipu_quota` / `fetch_ollama_quota` / 统一入口 `fetch_quota`
- `src/display_text.py`：纯函数格式化（Windows 用）

**Windows UI**：
- `src/widget.py`：`UsageWidget` 无边框窗口（`update_data`、`RingWidget` 进度环自绘水位+档位色、`_stale` 变灰、`moved` / `refresh_requested` 信号）
- `src/main.py` 的 `run_windows()`：30s/5min QTimer、`QuotaWorker`(QThread) 后台额度、托盘、位置记忆、开机自启勾选项（写启动文件夹 `.lnk`，`frozen` 分叉：打包态指 exe / 脚本态 `pythonw.exe`）

**macOS UI**：
- `src/mac_text.py`：纯函数 `build_title` / `ring_ratio` / `build_menu_items`（不依赖 rumps，Windows 可测）
- `src/mac_bar.py`：`MacUsageBar(rumps.App)` + `ring_image`（NSImage 单色进度环）+ `@rumps.timer` + `threading` 后台额度 + 开机自启菜单项（LaunchAgent，写 `~/Library/LaunchAgents/` 不 load）；`run()` 入口，启动 1s timer 刷 icon
- `src/main.py` 的 `run_mac()`：调 `mac_bar.run()`

**入口**：
- `src/main.py`：顶部不 import PySide6（Mac 加载不崩）；`main()` 按 `sys.platform` 分支 `run_windows` / `run_mac`；`QuotaWorker` / `_make_tray_icon` 是 `run_windows` 内局部定义（依赖 PySide6）

## 数据与坑点（反复踩过的，勿再犯）

### 通用（数据层）
- db 路径 `~/.cc-switch/cc-switch.db`，**只读连接** `file:{path}?mode=ro` + `uri=True`。
- **`proxy_request_logs.provider_id` 是占位值 `'_session'`**，不存真实厂商标识 → 今日用量**全部汇总**，不要改回按厂商过滤。
- 当前激活厂商读 `~/.cc-switch/settings.json` 的 `currentProviderClaude`（id）→ db 查 base_url / token。**不要用 db 的 `is_current`**（实测动态变化、不可靠）。
- **智谱额度接口 Authorization 不加 Bearer**（Kimi 要加）。URL `{base}/api/monitor/usage/quota/limit`，解析 `data.limits[]` 里 `type==TOKENS_LIMIT`、`unit==3`→5h / `unit==6`→周。
- 厂商不识别（日日新 / Xiaomi MiMo 等）→ 额度显示 `--`；查询失败 → 保留上次数据变灰（stale），勿清空。

- Ollama Cloud legacy：仅识别 `ollama.com` 主机，复用当前 Provider 的真实 `ANTHROPIC_AUTH_TOKEN`，Bearer 请求固定 `https://ollama.com/api/usage`。`limits.session/weekly.usage` 为 0～1 已用比例，映射 `used=usage*100, limit=100`；缺字段、非数值、越界或请求失败返回 None。新增请求按服务限流，两秒内重复调用返回 None，沿用 stale。
- Ollama 接口不提供 reset：session 为 None；weekly 按下一次周一 00:00 UTC（北京时间周一 08:00）本地推算，现有 reset 文本明确带“本地推算”，不得当成 API 返回时间。

### Windows
- QThread 必须用集合（`_workers`）持有引用直到 `finished`，否则被 GC 触发 `QThread destroyed while running` 启动崩溃。
- 富文本 QLabel 会拦截鼠标事件导致拖不动 → `WA_TransparentForMouseEvents`；富文本不支持 `AlignVCenter` → 圆点与文字拆双纯文本 label。
- 开机自启用 `getattr(sys,'frozen',False)` 分叉：打包态（PyInstaller onefile）`sys.executable` 即 exe，快捷方式直接指它、无 Arguments；脚本态才找 `pythonw.exe` + `main.py`。写 `.lnk` 走 PowerShell `WScript.Shell` COM（`subprocess` 调 `powershell -NoProfile -Command`），无新依赖。
- 进度环 `RingWidget` 用 QPainter 画弧（`QRectF`+`drawArc`，从 12 点 90° 顺时针），填充=`ring_ratio`（5h 水位），色=档位；对齐 `mac_bar.ring_image` 几何。无额度画空环、stale 灰弧保留上次水位。
- 托盘图标用 `ripple.ico`，`_resource_path` 定位：打包态从 `sys._MEIPASS` 读、脚本态从 `build/` 读；`win_build.ps1` 必须 `--add-data` 把 ico 打进 exe，否则打包态 `QIcon` 加载不到。
- 位置记忆 `SETTINGS_PATH` 必须 frozen 分叉：打包态（onefile）`__file__` 指向 `_MEIPASS` 临时解压目录、退出即删，记忆写那里等于每次启动清零（用户"拖了白拖"）；打包态改存 exe 同目录（`settings.json` 已被 .gitignore 全局忽略）。记忆带 `screen` 屏幕归属，恢复时校验坐标仍归属记忆屏（`resolve_restore_pos`），布局变化回主屏默认；无有效记忆时 `place_default` 固定用 `QApplication.primaryScreen()` 顶部居中，**不要用 `screenAt(窗口当前位置)` 判屏**（启动时序漂移会吸附到错误的屏）。

### macOS
- rumps `App.icon` setter **只收文件路径、不接受 NSImage**；动态 NSImage icon 要直接写内部 `_icon_nsimage` + 调 `_nsapp.setStatusBarIcon()`（构造阶段 `_nsapp` 未就绪会 AttributeError 吞，`_icon_nsimage` 已存，run loop 启动自动用）。默认 template 单色，填充比例承载水位。
- Cocoa UI 更新必须在主线程 → 后台 `threading.Thread` 查额度只做整体引用替换 `self._quota`（原子）+ dirty 标志，主线程 `rumps.timer` 检测后刷 UI。
- `mac_bar.py` 菜单动态文本：已真机验证 `self.menu[i]` 整数索引会 `KeyError`（rumps `Menu` 按 title 做 key），改用 `__init__` 持有 `MenuItem` 引用改 `.title`；stale 行用第 6 占位 menu 项避免索引越界。
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

- `src/settings.json` 是窄条位置记忆，运行时生成，已被 `.gitignore` 忽略、不入版本控制。