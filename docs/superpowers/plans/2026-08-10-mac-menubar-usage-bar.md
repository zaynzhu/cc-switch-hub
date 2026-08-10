# Mac 菜单栏用量条 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 cc-switch-hub 新增 macOS 菜单栏用量条（rumps），Windows 端代码不动。

**Architecture:** `main.py` 按 `sys.platform` 分支：`win32` 走现有 `UsageWidget`（PySide6 import 延迟进分支），`darwin` 走新 `mac_bar.py`（rumps App）。纯函数（算 title/进度环比例/菜单文本）放 `mac_text.py`，不依赖 rumps，Windows 可 TDD；rumps 集成与 NSImage 进度环放 `mac_bar.py`，盲写回家测。数据层 `usage_reader`/`quota_fetcher`/`display_text` 复用。

**Tech Stack:** Python 3.12、rumps（Mac）、pyobjc/AppKit（Mac，rumps 自带）、PyInstaller（Win 打包）、py2app（Mac 打包）、pytest

## Global Constraints

- Windows 用 tool python：`E:/program/tool/python/python.exe`（3.12.8），**不要用 Anaconda**（msvcp140.dll 与 PySide6 冲突）
- Mac 用 `pip install rumps`（自带 pyobjc），Python 3.10+
- 测试：`"E:/program/tool/python/python.exe" -m pytest tests/ -v`（根 conftest.py 已把 src/ 加进 sys.path）
- commit：`type: 中文描述`，`git config user.name zaynzhu`（不设邮箱）
- 风格：4 空格缩进、snake_case、中文注释、英文标识符
- Mac 端 rumps/AppKit 代码盲写（Windows 跑不了），回家测验证；纯函数必须在 Windows 测试通过
- 平台分支：Windows 路径不得 import rumps/AppKit，Mac 路径不得 import PySide6

## File Structure

- `src/mac_text.py`（新）：纯函数 `build_title` / `ring_ratio` / `build_menu_items`，依赖 `display_text` 的 `format_*`，**不 import rumps/AppKit**，Windows 可测
- `src/mac_bar.py`（新）：`MacUsageBar(rumps.App)` + `ring_image`（NSImage 矢量进度环）+ Timer + threading，import `mac_text`
- `src/main.py`（改）：拆 `run_windows()` / `run_mac()` + 平台分支入口，PySide6 import 延迟进 `run_windows`
- `tests/test_mac_text.py`（新）：纯函数测试，Windows 跑
- `tests/test_main_platform.py`（新）：平台分支测试，Windows 跑
- `build/win_build.ps1`（新）：Windows PyInstaller 打包脚本
- `build/mac_setup.py`（新）：py2app setup
- `README.md`（改）：加 Mac 章节 + Gatekeeper 绕过说明

---

### Task 1: mac_text 纯函数 + 测试

**Files:**
- Create: `src/mac_text.py`
- Test: `tests/test_mac_text.py`

**Interfaces:**
- Consumes: `display_text.format_tokens(n) -> str`、`format_cost(usd) -> str`、`format_quota(used, limit) -> str`
- Produces:
  - `build_title(total_tokens, total_cost, h5_used, h5_limit) -> str`：如 `'69.4M $0.03 58%'`，无额度 `'69.4M $0.00 --'`
  - `ring_ratio(used, limit) -> float | None`：`used/limit` 限 0-1，无额度返回 `None`
  - `build_menu_items(total_tokens, total_cost, last_model, quota, stale) -> list[str]`：菜单详情行

- [ ] **Step 1: 写失败测试**

```python
# tests/test_mac_text.py
from mac_text import build_title, ring_ratio, build_menu_items

def test_build_title_with_quota():
    assert build_title(69411491, 0.03, 78, 100) == '69.4M $0.03 78%'

def test_build_title_without_quota():
    assert build_title(0, 0.0, None, None) == '0 $0.00 --'

def test_ring_ratio():
    assert ring_ratio(78, 100) == 0.78
    assert ring_ratio(0, 100) == 0.0
    assert ring_ratio(150, 100) == 1.0  # 超限封顶 1.0
    assert ring_ratio(None, 100) is None
    assert ring_ratio(78, 0) is None
    assert ring_ratio(78, None) is None

def test_build_menu_items_with_quota():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': '02:30'},
         'weekly': {'used': 68, 'limit': 100, 'reset': '周一'}}
    items = build_menu_items(69411491, 0.03, 'kimi-k3', q, False)
    assert items[0] == '今日: 69.4M tok'
    assert items[1] == '花费: $0.03'
    assert items[2] == '近用: kimi-k3'
    assert items[3] == '5h: 78% 重置 02:30'
    assert items[4] == '周: 68% 重置 周一'

def test_build_menu_items_without_quota():
    items = build_menu_items(0, 0.0, None, None, False)
    assert items[0] == '今日: 0 tok'
    assert items[1] == '花费: $0.00'
    assert items[2] == '近用: --'
    assert len(items) == 3  # 无额度不附 5h/周 行

def test_build_menu_items_stale():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': '02:30'},
         'weekly': {'used': 68, 'limit': 100, 'reset': '周一'}}
    items = build_menu_items(69411491, 0.03, 'kimi-k3', q, True)
    assert items[-1] == '(额度数据已过期)'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_mac_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mac_text'`

- [ ] **Step 3: 实现 mac_text.py**

```python
# src/mac_text.py
"""Mac 菜单栏用量条的纯函数：title 文本、进度环比例、菜单详情。
不依赖 rumps/AppKit，可在 Windows 单测。"""
from display_text import format_tokens, format_cost, format_quota


def build_title(total_tokens, total_cost, h5_used, h5_limit):
    """菜单栏 title：'{token} {cost} {h5_pct}'，如 '69.4M $0.03 58%'。"""
    tok = format_tokens(total_tokens)
    cost = format_cost(total_cost)
    h5 = format_quota(h5_used, h5_limit)  # 无额度返回 '--'
    return f'{tok} {cost} {h5}'


def ring_ratio(used, limit):
    """5h 额度使用比例 0-1，超限封顶 1.0；无额度返回 None。"""
    if used is None or limit is None or limit == 0:
        return None
    return min(used / limit, 1.0)


def build_menu_items(total_tokens, total_cost, last_model, quota, stale):
    """菜单详情行列表。无额度时只返回用量三行。"""
    items = [
        f'今日: {format_tokens(total_tokens)} tok',
        f'花费: {format_cost(total_cost)}',
        f'近用: {last_model or "--"}',
    ]
    if quota:
        h5 = quota['h5']
        wk = quota['weekly']
        items.append(
            f"5h: {format_quota(h5['used'], h5['limit'])} 重置 {h5['reset'] or '--'}")
        items.append(
            f"周: {format_quota(wk['used'], wk['limit'])} 重置 {wk['reset'] or '--'}")
        if stale:
            items.append('(额度数据已过期)')
    return items
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_mac_text.py -v`
Expected: 6 passed

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/ -q`
Expected: 36 passed（原 30 + 新 6）

- [ ] **Step 6: Commit**

```bash
git add src/mac_text.py tests/test_mac_text.py
git commit -m "feat: 添加 mac_text 纯函数算菜单栏 title 与进度环比例"
```

---

### Task 2: mac_bar rumps App 集成（盲写，回家测）

**Files:**
- Create: `src/mac_bar.py`

**Interfaces:**
- Consumes: `mac_text.build_title` / `ring_ratio` / `build_menu_items`；`usage_reader.get_today_usage(db_path)`；`quota_fetcher.get_current_provider(db_path, settings_path)` / `fetch_quota(base, token)`
- Produces: `MacUsageBar` 类，`main.py` 的 `run_mac()` 调 `MacUsageBar().run()`

> ⚠️ 本任务依赖 rumps/AppKit，**Windows 跑不了**，盲写。回家测按 spec 验证清单逐条验。代码里留好兜底与注释。

- [ ] **Step 1: 实现 mac_bar.py**

```python
# src/mac_bar.py
"""macOS 菜单栏用量条（rumps）。盲写，回家测。
- icon：单色进度环，NSImage 矢量，填充比例=5h 额度水位
- title：'{token} {cost} {h5_pct}'
- 菜单：详情 + 立即刷新 / 退出
- 30s 刷用量、5min 后台线程查额度，主线程刷 UI
"""
import os, threading
import rumps
from AppKit import NSImage, NSBezierPath, NSColor

from mac_text import build_title, ring_ratio, build_menu_items
from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
USAGE_INTERVAL = 30        # 秒
QUOTA_INTERVAL = 5 * 60    # 秒


def ring_image(ratio, stale=False, size=18):
    """NSImage 矢量画单色进度环。ratio=None 画空环；stale 加缺口。
    template 模式单色，随深浅模式自动反色。绘制失败抛异常由调用方兜底。"""
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSColor.controlTextColor().set()
    r = size / 2 - 2
    center = (size / 2, size / 2)
    # 背景整环（细）
    bg = NSBezierPath.bezierPath()
    bg.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
        center, r, 0, 360)
    bg.setLineWidth_(1.5)
    bg.stroke()
    # 前景填充比例（粗，从 12 点顺时针）
    if ratio is not None:
        fill = ratio if not stale else max(0.0, ratio - 0.08)
        end_angle = 90 - 360 * fill
        fg = NSBezierPath.bezierPath()
        fg.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
            center, r, 90, end_angle)
        fg.setLineWidth_(2.5)
        fg.stroke()
    img.unlockFocus()
    img.setTemplate_(True)  # 单色 template，菜单栏自动反色
    return img


class MacUsageBar(rumps.App):
    def __init__(self):
        super().__init__(name='cc-switch 用量条', title='0 $0.00 --', icon=None)
        # 菜单：5 详情行 + 分隔 + 立即刷新 + 退出
        self.menu = ['今日: --', '花费: --', '近用: --', '5h: --', '周: --',
                     None, '立即刷新', '退出']
        self._usage = (0, 0.0, None)
        self._quota = None
        self._stale = False
        self._quota_dirty = False  # 后台线程查完置 True，主线程 timer 检测刷 UI
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_usage()
        self._refresh_quota_async()

    def _refresh_usage(self):
        self._usage = get_today_usage(DB_PATH)
        self._update_ui()

    def _refresh_quota_async(self):
        threading.Thread(target=self._fetch_quota, daemon=True).start()

    def _fetch_quota(self):
        """后台线程：查额度，整体引用替换 self._quota（原子），置 dirty 标志。
        不直接刷 UI（Cocoa UI 须主线程）。"""
        prov = get_current_provider(DB_PATH, SETTINGS_JSON_PATH)
        q = fetch_quota(prov[0], prov[1]) if prov else None
        if q is None and self._quota is not None:
            self._stale = True  # 曾有数据但本次失败 → 过期
        elif q is not None:
            self._stale = False
            self._quota = q
        self._quota_dirty = True

    def _update_ui(self):
        u = self._usage
        q = self._quota
        h5 = q['h5'] if q else None
        h5_used = h5['used'] if h5 else None
        h5_limit = h5['limit'] if h5 else None
        self.title = build_title(u[0], u[1], h5_used, h5_limit)
        ratio = ring_ratio(h5_used, h5_limit)
        try:
            self.icon = ring_image(ratio, self._stale)
        except Exception:
            self.icon = None  # 兜底：title 已含 58% 数字，水位不丢
        # 菜单详情文本（前 5 行）
        items = build_menu_items(u[0], u[1], u[2], q, self._stale)
        for i, text in enumerate(items):
            self.menu[i].title = text  # 待回家验证动态刷新

    @rumps.timer(USAGE_INTERVAL)
    def _usage_timer(self, _sender):
        self._refresh_usage()
        # 顺带把后台完成的额度刷出来（延迟 ≤30s）
        if self._quota_dirty:
            self._quota_dirty = False
            self._update_ui()

    @rumps.timer(QUOTA_INTERVAL)
    def _quota_timer(self, _sender):
        self._refresh_quota_async()

    @rumps.clicked('立即刷新')
    def _refresh_now(self, _):
        self._refresh_all()

    @rumps.clicked('退出')
    def _quit(self, _):
        rumps.quit_application()


def run():
    """main.py 的 darwin 分支调用。"""
    MacUsageBar().run()
```

- [ ] **Step 2: 静态检查 import 路径**

Run: `"E:/program/tool/python/python.exe" -c "import ast; ast.parse(open('src/mac_bar.py').read()); print('syntax ok')"`
Expected: `syntax ok`（只验语法，不 import rumps）

- [ ] **Step 3: Commit**

```bash
git add src/mac_bar.py
git commit -m "feat: 添加 mac_bar rumps 菜单栏用量条与单色进度环"
```

- [ ] **Step 4: 回家测验证清单（spec 第 10 节）**

逐条验，失败回报报错：
1. `pip install rumps` 成功
2. `python src/main.py`（Mac 分支）跑起来，菜单栏出现 icon + title
3. title 显示 `69.4M $0.03 58%` 正确
4. 进度环 icon 渲染（单色，填充随水位）
5. 30s 后 title 刷新用量
6. 点击菜单显示完整信息
7. 菜单项文本刷新生效（若 `self.menu[i].title` 不生效，回退：菜单 callback 里重算）
8. 额度查询后台线程不卡 UI

---

### Task 3: main.py 平台分支改造

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_main_platform.py`

**Interfaces:**
- Consumes: `mac_bar.run()`（Mac 分支）
- Produces: `run_windows()` / `run_mac()` / `main()` 平台分支入口

- [ ] **Step 1: 写失败测试**

```python
# tests/test_main_platform.py
import sys, importlib

def test_main_exposes_run_windows_run_mac(monkeypatch):
    import main
    assert hasattr(main, 'run_windows')
    assert hasattr(main, 'run_mac')
    assert hasattr(main, 'main')

def test_windows_path_does_not_import_pyside6_at_module_level(monkeypatch):
    """main.py 顶部不得 import PySide6，保证 Mac 加载不崩。"""
    monkeypatch.setattr(sys, 'platform', 'darwin')
    # 重新加载 main，确认不因 PySide6 缺失而崩
    if 'main' in sys.modules:
        del sys.modules['main']
    import main  # noqa
    # Mac 平台不应触发 PySide6 import
    assert 'PySide6' not in sys.modules or sys.platform != 'darwin'

def test_run_mac_calls_mac_bar(monkeypatch):
    """darwin 平台 main() 调 mac_bar.run，不碰 PySide6。"""
    called = {}
    import types
    fake_mac = types.ModuleType('mac_bar')
    fake_mac.run = lambda: called.setdefault('ran', True)
    monkeypatch.setitem(__import__('sys').modules, 'mac_bar', fake_mac)
    monkeypatch.setattr(sys, 'platform', 'darwin')
    import main
    main.main()
    assert called.get('ran') is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_main_platform.py -v`
Expected: FAIL（`main` 无 `run_windows`/`run_mac`）

- [ ] **Step 3: 改造 main.py**

把现有 `main()` 函数体原样移进 `run_windows()`，顶部 PySide6 import 延迟到 `run_windows` 内，新增 `run_mac()` 和平台分支 `main()`：

```python
# src/main.py 顶部：去掉 from PySide6...，只留标准库 + 数据层
import sys, os, json
from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
USAGE_INTERVAL = 30 * 1000
QUOTA_INTERVAL = 5 * 60 * 1000
_workers = set()


class QuotaWorker:
    # 原样保留（Windows 用 QThread；Mac 不走这里）
    # ... 现有 QuotaWorker 代码不动 ...


def load_settings(): ...      # 原样
def save_settings(pos): ...   # 原样
def place_default(widget): ... # 原样
def _make_tray_icon(): ...     # 原样


def run_windows():
    """Windows 路径：PySide6 延迟 import，Mac 不加载。"""
    from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu)
    from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
    from PySide6.QtCore import QTimer, Qt, QThread, Signal
    from widget import UsageWidget
    # ... 原 main() 函数体原样移入（app/widget/定时器/托盘/app.exec）...


def run_mac():
    """Mac 路径：rumps 菜单栏。"""
    from mac_bar import run as mac_run
    mac_run()


def main():
    if sys.platform == 'darwin':
        run_mac()
    else:
        run_windows()


if __name__ == '__main__':
    main()
```

> 注意：`QuotaWorker` 原本继承 `QThread`，顶部不再 import PySide6 后，`QuotaWorker` 类定义需要 PySide6。把 `QuotaWorker` 的 import 也延迟——最干净的做法是把 `QuotaWorker` 整个移进 `run_windows()` 内部定义，或在 `run_windows` 顶部 import 后定义。实现时把 `QuotaWorker` 类移进 `run_windows` 函数体内（局部类），Mac 路径不定义它。

- [ ] **Step 4: 跑测试确认通过**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_main_platform.py -v`
Expected: 3 passed

- [ ] **Step 5: 跑全量测试 + Windows 实跑确认无回归**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/ -q`
Expected: 39 passed

实跑 Windows（手动启一下确认还能跑）：
Run: `"E:/program/tool/python/python.exe" src/main.py`（应弹出现有窄条，行为不变）

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_main_platform.py
git commit -m "feat: main.py 按平台分支拆分 run_windows/run_mac"
```

---

### Task 4: Windows PyInstaller exe 打包

**Files:**
- Create: `build/win_build.ps1`

**Interfaces:**
- Produces: `dist/cc-switch-hub.exe`（Windows 可双击运行）

- [ ] **Step 1: 装 PyInstaller**

Run: `"E:/program/tool/python/python.exe" -m pip install pyinstaller`

- [ ] **Step 2: 写打包脚本**

```powershell
# build/win_build.ps1
# Windows exe 打包。在项目根目录运行：powershell -File build/win_build.ps1
$ErrorActionPreference = 'Stop'
$py = "E:/program/tool/python/python.exe"
& $py -m PyInstaller --noconfirm --noconsole --onefile `
    --name cc-switch-hub `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtCore `
    --collect-all PySide6 `
    src/main.py
Write-Host "产物：dist/cc-switch-hub.exe"
```

- [ ] **Step 3: 本地打包验证**

Run: `powershell -ExecutionPolicy Bypass -File build/win_build.ps1`
Expected: 生成 `dist/cc-switch-hub.exe`，无 fatal error

- [ ] **Step 4: 实跑 exe 确认**

双击 `dist/cc-switch-hub.exe`，确认窄条出现、行为与 `python src/main.py` 一致。

- [ ] **Step 5: Commit**

```bash
git add build/win_build.ps1
git commit -m "build: 添加 Windows PyInstaller exe 打包脚本"
```

---

### Task 5: Mac py2app dmg 打包 + README

**Files:**
- Create: `build/mac_setup.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `dist/cc-switch-hub.app` + `dist/cc-switch-hub.dmg`（Mac，回家验证）

> ⚠️ py2app 只能在 Mac 跑，盲写配置，回家验证。

- [ ] **Step 1: 写 py2app setup**

```python
# build/mac_setup.py
"""py2app 打包配置。在 Mac 上运行：
    pip install py2app rumps
    cd build && python mac_setup.py py2app
产物 build/mac/dist/cc-switch-hub.app
"""
from setuptools import setup

APP = ['src/main.py']
OPTIONS = {
    'argv_emulation': False,
    'packages': ['rumps', 'objc', 'AppKit', 'Foundation',
                 'mac_text', 'usage_reader', 'quota_fetcher', 'display_text'],
    'includes': ['rumps', 'AppKit', 'Foundation'],
    'plist': {
        'LSUIElement': True,  # 不在 Dock 显示，纯菜单栏 app
        'CFBundleName': 'cc-switch-hub',
    },
}

setup(
    app=APP,
    name='cc-switch-hub',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

- [ ] **Step 2: 写 dmg 打包命令（回家执行）**

```bash
# 在 Mac 上，py2app 产物后打 dmg + ad-hoc 签名
cd build
python mac_setup.py py2app
# ad-hoc 签名（无需开发者账号）
codesign --sign - --force --deep dist/cc-switch-hub.app
# 打 dmg
hdiutil create -volname "cc-switch-hub" -srcfolder dist/cc-switch-hub.app \
    -ov -format UDZO dist/cc-switch-hub.dmg
```

- [ ] **Step 3: 更新 README 加 Mac 章节**

在 `README.md` 末尾追加：

```markdown
## macOS 使用

\`\`\`bash
pip install rumps
python src/main.py
\`\`\`

菜单栏出现用量条：进度环 icon（填充=5h 额度水位）+ `69.4M $0.03 58%` 文字，点击看完整详情。

### 打包成 dmg（Mac）

\`\`\`bash
pip install py2app rumps
cd build && python mac_setup.py py2app
codesign --sign - --force --deep dist/cc-switch-hub.app
hdiutil create -volname "cc-switch-hub" -srcfolder dist/cc-switch-hub.app -ov -format UDZO dist/cc-switch-hub.dmg
\`\`\`

### 首次打开 dmg（Gatekeeper 绕过）

dmg 仅 ad-hoc 签名、未公证，双击会被拦。右键点 app →「打开」→「仍要打开」；或「系统设置 → 隐私与安全性 → 仍要打开」。
```

- [ ] **Step 4: Commit**

```bash
git add build/mac_setup.py README.md
git commit -m "build: 添加 Mac py2app dmg 打包配置与 README 说明"
```

- [ ] **Step 5: 回家验证打包**

逐条验：
1. `pip install py2app rumps` 成功
2. `python build/mac_setup.py py2app` 产出 `.app`
3. `codesign` ad-hoc 签名成功
4. `hdiutil` 产出 `.dmg`
5. 右键打开 `.app`/`.dmg` 能跑（Gatekeeper 绕过后）

---

## Self-Review

**1. Spec coverage:**
- 平台分支 + PySide6 延迟 import → Task 3 ✓
- mac_bar rumps App + 进度环 icon + title + 菜单 → Task 2 ✓
- 纯函数（title/比例/菜单文本）+ 测试 → Task 1 ✓
- threading 后台额度 + 整体引用替换 → Task 2 `_fetch_quota` ✓
- Win PyInstaller exe → Task 4 ✓
- Mac py2app dmg + ad-hoc 签名 + README 绕过 → Task 5 ✓
- 错误处理（无 cc-switch、icon 兜底）→ Task 2 `_update_ui` 兜底 ✓
- 回家测验证清单 → Task 2 Step 4 + Task 5 Step 5 ✓

**2. Placeholder scan:** 无 TBD/TODO；所有代码步骤含完整代码；盲写部分含完整代码 + 回家测清单。✓

**3. Type consistency:**
- `build_title(total_tokens, total_cost, h5_used, h5_limit)` — Task 1 定义，Task 2 `_update_ui` 调用签名一致 ✓
- `ring_ratio(used, limit) -> float|None` — Task 1 定义，Task 2 调用一致 ✓
- `build_menu_items(total_tokens, total_cost, last_model, quota, stale)` — 一致 ✓
- `MacUsageBar().run()` — Task 2 定义 `run()`，Task 3 `run_mac` 调 `from mac_bar import run as mac_run; mac_run()` ✓

**注：** Task 3 把 `QuotaWorker` 移进 `run_windows` 内部（局部类），因顶部不再 import PySide6。实现者注意保留 `QuotaWorker` 的 `fetched` 信号与 `refresh_quota` 连接逻辑原样。