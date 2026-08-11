<div align="center">

# 📊 cc-switch-hub

**Windows 任务栏 / macOS 菜单栏常驻用量条，一眼看穿 Claude Code 今日用量与套餐额度**

[中文](README.md) | [English](README_EN.md)

![GitHub stars](https://img.shields.io/github/stars/zaynzhu/cc-switch-hub?style=social)
![GitHub forks](https://img.shields.io/github/forks/zaynzhu/cc-switch-hub?style=social)
![GitHub issues](https://img.shields.io/github/issues/zaynzhu/cc-switch-hub)
![GitHub last commit](https://img.shields.io/github/last-commit/zaynzhu/cc-switch-hub)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)

</div>

> [!TIP]
> cc-switch-hub 是 [cc-switch](https://github.com/farion1231/cc-switch) 的伴侣可视化工具。cc-switch 把第三方厂商接入 Claude Code 并记录请求日志，cc-switch-hub 读取这些日志 + 厂商额度接口，在 Windows 任务栏窄条 / macOS 菜单栏常驻显示今日 token、花费、近用模型与套餐额度水位。**不装 cc-switch 则无数据。**

---

## ✨ Features

- **Windows 任务栏窄条** —— 无边框置顶，状态圆点（绿/琥珀/红/灰）+ 用量文字，贴任务栏上沿
- **macOS 菜单栏** —— rumps 实现，单色进度环 icon（填充比例 = 5h 额度水位）+ 用量文字，点击看完整详情
- **今日用量** —— token 数、估算花费、近用模型，30 秒刷新
- **套餐额度水位** —— Kimi / 智谱 GLM 的 5 小时窗口与周额度百分比，5 分钟刷新
- **状态指示** —— Windows 圆点颜色 / Mac 进度环填充比例，一眼判断额度水位
- **数据复用 cc-switch** —— 读 cc-switch.db + settings.json + 厂商额度接口，不重复造轮子
- **额度失败容错** —— 接口失败保留上次数据并标记过期（stale），不清零
- **位置记忆** —— Windows 窄条可拖动、位置记忆；Mac 菜单栏原生常驻

## 🚀 Quick Start

### Windows

```bash
# 必须用 tool python（Anaconda 的 msvcp140.dll 与 PySide6 冲突）
"E:/program/tool/python/python.exe" -m pip install PySide6
"E:/program/tool/python/python.exe" src/main.py
```

无边框置顶窄条出现在屏幕顶部居中、贴上沿。可拖动（位置记忆）、右键有「立即刷新 / 退出」。

### macOS

```bash
pip install rumps
python src/main.py
```

菜单栏出现用量条：进度环 icon（填充 = 5h 额度水位）+ `69.4M $0.03 58%` 文字，点击看完整详情。

## 📦 Installation

### 依赖

| 平台 | 依赖 | 安装 |
|---|---|---|
| Windows | PySide6 | `"E:/program/tool/python/python.exe" -m pip install PySide6` |
| macOS | rumps | `pip install rumps` |
| 开发 | pytest | `pip install pytest` |

> ⚠️ **Windows 不要用 Anaconda 的 python**：其 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。必须用 tool python `E:/program/tool/python.exe`（3.12.8）。

### 打包

**Windows exe**：

```bash
powershell -ExecutionPolicy Bypass -File build/win_build.ps1
# 产物 dist/cc-switch-hub.exe
```

**macOS dmg**：

```bash
pip install py2app rumps
cd build && python mac_setup.py py2app
codesign --sign - --force --deep dist/cc-switch-hub.app
hdiutil create -volname "cc-switch-hub" -srcfolder dist/cc-switch-hub.app -ov -format UDZO dist/cc-switch-hub.dmg
```

> dmg 仅 ad-hoc 签名、未公证，双击会被 Gatekeeper 拦。右键点 app →「打开」→「仍要打开」；或「系统设置 → 隐私与安全性 → 仍要打开」。

### 开机自启（可选）

**Windows**：创建启动文件夹快捷方式，用 `pythonw.exe` 无控制台启动，见 `docs/superpowers/plans/2026-08-07-taskbar-usage-widget.md` 的 Task 6。

**macOS**：菜单栏点击进度环图标 → 「开机自启」（在「立即刷新」下）切换。写入 `~/Library/LaunchAgents/com.zaynzhu.cc-switch-hub.plist`，下次登录自动启动。需打包 .app 后使用（`python src/main.py` 运行时无 bundle）。

## 💡 Usage

### Windows 窄条

- 拖动改位置（位置记忆），右键「立即刷新 / 退出」
- 状态圆点：🟢 充足 / 🟡 接近上限 / 🔴 超限 / ⚪ 无数据或过期
- 鼠标悬停看完整 tooltip（今日 / 花费 / 近用 / 5h / 周 / 重置时间）

### macOS 菜单栏

- 进度环 icon 填充比例 = 5h 额度水位
- 点击 icon 弹出菜单：今日 / 花费 / 近用 / 5h / 周 详情 + 立即刷新 / 开机自启 / 退出

## 🧩 项目结构

| 文件 | 职责 |
|---|---|
| `src/usage_reader.py` | 只读 cc-switch.db，汇总今日 token / 花费 / 近用模型 |
| `src/quota_fetcher.py` | 跟随当前厂商查套餐额度（Kimi / 智谱分发） |
| `src/display_text.py` | 纯函数：格式化 token / 花费 / 额度文本与颜色阈值（Windows） |
| `src/widget.py` | Windows 无边框置顶窄条窗口 |
| `src/mac_text.py` | Mac 纯函数：菜单栏 title / 进度环比例 / 菜单文本 |
| `src/mac_bar.py` | macOS rumps 菜单栏 App + 单色进度环 |
| `src/main.py` | 入口：按 `sys.platform` 分支（`run_windows` / `run_mac`） |

## 📊 数据来源

- 今日用量 / 花费 / 近用模型：`~/.cc-switch/cc-switch.db`（只读）的 `proxy_request_logs` 表
- 当前激活厂商：`~/.cc-switch/settings.json` 的 `currentProviderClaude`
- 套餐额度：Kimi `api.kimi.com/coding/v1/usages`、智谱 `{base}/api/monitor/usage/quota/limit`

## ❓ FAQ

<details>
<summary>不装 cc-switch 能用吗？</summary>

不能。本项目数据 100% 来自 cc-switch 本地库（`~/.cc-switch/cc-switch.db` + `settings.json`）。不装 cc-switch 且没用它接入第三方厂商，窄条 / 菜单栏只显示占位 `--`。本项目是 cc-switch 的伴侣可视化工具。

</details>

<details>
<summary>macOS 菜单栏为什么不显示彩色圆点？</summary>

macOS 菜单栏 status item 的 icon 默认是 template image（单色，随深浅模式反色）。彩色需直接操作 NSStatusItem 关 template，盲写风险高。改用单色进度环——填充比例本身表达水位，比彩色圆点更克制地道。

</details>

<details>
<summary>Windows 为什么必须用 tool python？</summary>

Anaconda 的 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。tool python `E:/program/tool/python.exe`（3.12.8）无此冲突。

</details>

## 📚 Documentation

| 文档 | 说明 |
|---|---|
| `AGENTS.md` | agent 规则手册（环境、模块、坑点） |
| `docs/superpowers/specs/` | 设计文档 |
| `docs/superpowers/plans/` | 实现计划 |

## 🤝 Contributing

```bash
git clone https://github.com/zaynzhu/cc-switch-hub.git
cd cc-switch-hub
"E:/program/tool/python/python.exe" -m pip install PySide6 pytest
"E:/program/tool/python/python.exe" -m pytest tests/ -v
```

Fork → Branch → Commit（`type: 中文描述`）→ PR。

## ⭐ Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=zaynzhu/cc-switch-hub&type=Date&theme=dark">
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=zaynzhu/cc-switch-hub&type=Date">
  <img alt="Star History" src="https://api.star-history.com/svg?repos=zaynzhu/cc-switch-hub&type=Date">
</picture>

## 🙏 Contributors

<a href="https://github.com/zaynzhu/cc-switch-hub/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=zaynzhu/cc-switch-hub" />
</a>

## 📄 License

暂无 LICENSE 文件。如需开源使用，建议添加（如 MIT）。

---

<div align="center">

<sub>Built with ❤️ for Claude Code + cc-switch users</sub>

</div>