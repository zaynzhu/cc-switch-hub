# Mac 菜单栏用量条设计

## 背景与目标

cc-switch-hub 现有 Windows 任务栏窄条（PySide6 `UsageWidget`）。本设计新增 macOS 支持：在 Mac 顶部菜单栏显示用量条。**Windows 端代码不动**，Mac 新开独立模块。

用户在 Mac 上也用 cc-switch 接入第三方厂商，数据层可复用。开发方式：Windows 上盲写，用户回家测迭代。

## 非目标

- 不改 Windows 端功能与代码
- 不做"常驻完整长文字条"（方案2）：macOS 菜单栏空间有限，40+ 字符 title 挤占系统图标，已红队否决
- 不做彩色图标：rumps `App.icon` 默认 template 模式强制单色，彩色需直接操作 `NSStatusItem.button.image.setTemplate_(False)`，盲写黑盒。改用单色进度环承载水位信息

## 架构：平台分支

`src/main.py` 入口按 `sys.platform` 分支：

- `win32`：现有 `UsageWidget` 窗口 + 托盘。PySide6 import **延迟进分支函数内**，Mac 不加载 PySide6
- `darwin`：新 `src/mac_bar.py`，rumps 菜单栏应用

数据层平台无关，两边复用：`usage_reader` / `quota_fetcher` / `display_text`。

## Mac 模块 `src/mac_bar.py`

### rumps App 结构

`MacUsageBar(rumps.App)`：

- `icon`：单色进度环（NSImage 矢量）
- `title`：`69.4M $0.03 58%`（今日 token + 花费 + 5h 额度 %）
- `menu`：今日 / 花费 / 近用模型 / 5h(重置) / 周(重置) / 立即刷新 / 退出

### 进度环 icon

- NSImage 矢量画圆弧，填充比例 = 5h 额度 `used/limit`
- 连续填充（非离散档位）：低 → 中 → 高 → 满
- 单色 template 模式：菜单栏自动按深浅模式反色，**不关 template、不用 Pillow**
- 无额度数据：空环
- 额度过期（stale）：环加缺口或变虚线
- 矢量绘制：`NSBezierPath` 画圆弧 + `NSColor` 填充，retina 清晰
- **兜底**：NSImage 绘制失败 → 显示空环；title 本就含 `58%` 数字，水位信息不丢

### title

- 格式：`{token} {cost} {h5_pct}`，如 `69.4M $0.03 58%`（约 15 字符）
- 复用 `display_text` 的 `format_tokens` / `format_cost` / `format_quota`
- 无额度时：`69.4M $0.03 --`

### 菜单详情

```
今日: {token} tok
花费: {cost}
近用: {model}
5h:  {pct}% 重置 {reset}
周:  {pct}% 重置 {reset}
立即刷新
退出
```

菜单项文本随刷新更新（`rumps.MenuItem.title` 赋值，回家验证；不生效则点开时重算）。

### 刷新机制

- `rumps.Timer` 30s：`get_today_usage` → 更新 title + 菜单用量项
- `rumps.Timer` 5min：`threading.Thread` 后台 `fetch_quota` → 存 `self._quota` → 主线程 Timer 更新 icon + title% + 菜单额度项
- **线程同步**：后台线程整体替换 `self._quota` 引用（Python 赋值原子），主线程读引用，不加锁
- **主线程刷 UI**：rumps.Timer 回调在主线程（NSTimer），直接改 `self.title` / `self.icon` / menu item

### 额度查询

- 复用 `get_current_provider` + `fetch_quota`（`quota_fetcher`）
- 不用 `QuotaWorker(QThread)`（绑 PySide6），改 `threading.Thread`

## `main.py` 平台分支改造

- 顶部不再直接 `import PySide6`
- `run_windows()`：延迟 `import PySide6` + 现有 `UsageWidget` 逻辑（原样移入，行为不变）
- `run_mac()`：`from mac_bar import MacUsageBar; MacUsageBar().run()`
- `if sys.platform == 'darwin': run_mac() else: run_windows()`

## 打包

### Windows exe（本地验证）

- `PyInstaller --noconsole --onefile src/main.py`
- 处理 PySide6 依赖（hooks / hiddenimports）
- 产物 `dist/cc-switch-hub.exe`

### Mac dmg（回家验证）

- `py2app` setup.py：`packages` 预置 `objc` / `rumps` / `pyobjc.framework.*`
- 产物 `.app`
- `hdiutil` 打 dmg
- `codesign --sign -`（ad-hoc 签名，无需开发者账号）
- README 写 Gatekeeper 绕过：右键打开 / 系统设置"仍要打开"

## 错误处理

- 复用数据层兜底：db 不存在 → `(0, 0.0, None)`，quota 失败 → `None`
- Mac 无 cc-switch：title `0 $0.00 --`，进度环空，菜单 `--`
- rumps 仅 darwin 可用：`main.py` 平台分支保证 Windows 不 import rumps
- icon 绘制失败：显示空环；title 含 `58%` 数字，水位不丢

## 测试策略

- 数据层现有 30 测试复用
- `mac_bar` 抽纯函数测试：算 title 文本、算进度环填充比例、算菜单项文本——不依赖 rumps 事件循环
- Windows exe 打包本地验证
- Mac dmg + rumps 运行回家验证

## 盲写回家测验证清单

1. `pip install rumps` 成功
2. `rumps.App` 跑起来，菜单栏出现 icon + title
3. title 显示 `69.4M $0.03 58%` 正确
4. 进度环 icon 渲染（单色，填充随水位）
5. 30s 后 title 刷新用量
6. 点击菜单显示完整信息
7. 菜单项文本刷新生效
8. `py2app` 打包出 `.app`
9. `hdiutil` 出 dmg
10. ad-hoc 签名后双击（右键打开）能跑

## 风险与回退

- rumps icon 动态刷新不生效 → 直接操作 `NSStatusItem.button.image`
- 菜单文本不刷新 → 点开时重算
- `py2app` 漏 pyobjc 包 → `--packages` 手动补
- 进度环绘制失败 → 显示空环；title 含 `58%` 数字水位不丢
- 15 字符 title 偏挤 → 砍到 `69.4M·58%`（花费进菜单）