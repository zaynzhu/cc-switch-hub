<div align="center">

# 📊 cc-switch-hub

**A resident usage bar on the Windows taskbar / macOS menubar — see your Claude Code daily usage and quota at a glance**

[中文](README.md) | [English](README_EN.md)

![GitHub stars](https://img.shields.io/github/stars/zaynzhu/cc-switch-hub?style=social)
![GitHub forks](https://img.shields.io/github/forks/zaynzhu/cc-switch-hub?style=social)
![GitHub issues](https://img.shields.io/github/issues/zaynzhu/cc-switch-hub)
![GitHub last commit](https://img.shields.io/github/last-commit/zaynzhu/cc-switch-hub)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)

</div>

> [!TIP]
> cc-switch-hub is a companion visualizer for [cc-switch](https://github.com/farion1231/cc-switch). cc-switch routes third-party providers into Claude Code and logs requests; cc-switch-hub reads those logs + provider quota APIs to show today's tokens, cost, recent model, and package quota level on a Windows taskbar strip / macOS menubar item. **Without cc-switch, there's no data.**

---

## ✨ Features

- **Windows taskbar strip** — frameless always-on-top, status dot (green/amber/red/grey) + usage text, hugging the taskbar
- **macOS menubar** — built with rumps, monochrome progress-ring icon (fill ratio = 5h quota level) + usage text, click for full details
- **Today's usage** — tokens, estimated cost, recent model, refreshes every 30s
- **Package quota level** — Kimi / Zhipu GLM 5-hour window & weekly quota %, refreshes every 5min
- **Status indicator** — Windows dot color / Mac ring fill ratio, gauge quota level at a glance
- **Reuses cc-switch data** — reads cc-switch.db + settings.json + provider quota APIs, no reinvented wheels
- **Quota failure tolerance** — keeps last data on API failure and marks it stale, never zeroes out
- **Position memory** — Windows strip is draggable with position memory; Mac menubar is native

## 🚀 Quick Start

### Windows

```bash
# Must use tool python (Anaconda's msvcp140.dll conflicts with PySide6)
"E:/program/tool/python/python.exe" -m pip install PySide6
"E:/program/tool/python/python.exe" src/main.py
```

A frameless always-on-top strip appears at the top-center of the screen. Draggable (position memory), right-click for "Refresh now / Quit".

### macOS

```bash
pip install rumps
python src/main.py
```

A menubar item appears: progress-ring icon (fill = 5h quota level) + `69.4M $0.03 58%` text, click for full details.

## 📦 Installation

### Dependencies

| Platform | Dependency | Install |
|---|---|---|
| Windows | PySide6 | `"E:/program/tool/python/python.exe" -m pip install PySide6` |
| macOS | rumps | `pip install rumps` |
| Dev | pytest | `pip install pytest` |

> ⚠️ **Windows: do not use Anaconda's python** — its `Library/bin/msvcp140.dll` (VS2019) conflicts with the VS2022 runtime PySide6 needs; `PySide6.QtWidgets` won't load. You must use tool python `E:/program/tool/python.exe` (3.12.8).

### Packaging

**Windows exe**:

```bash
powershell -ExecutionPolicy Bypass -File build/win_build.ps1
# Output: dist/cc-switch-hub.exe
```

**macOS dmg**:

```bash
pip install py2app rumps
cd build && python mac_setup.py py2app
codesign --sign - --force --deep dist/cc-switch-hub.app
hdiutil create -volname "cc-switch-hub" -srcfolder dist/cc-switch-hub.app -ov -format UDZO dist/cc-switch-hub.dmg
```

> The dmg is only ad-hoc signed and notarization-free; double-clicking will be blocked by Gatekeeper. Right-click the app → "Open" → "Open anyway"; or "System Settings → Privacy & Security → Open anyway".

### Autostart (optional)

**Windows**: Create a shortcut in the Startup folder, launching with `pythonw.exe` (no console). See Task 6 in `docs/superpowers/plans/2026-08-07-taskbar-usage-widget.md`.

**macOS**: Click the progress-ring icon in the menubar → "Launch at login" (below "Refresh now") to toggle. Writes `~/Library/LaunchAgents/com.zaynzhu.cc-switch-hub.plist`; auto-starts at next login. Requires the packaged .app (`python src/main.py` has no bundle).

## 💡 Usage

### Windows strip

- Drag to reposition (position memory), right-click for "Refresh now / Quit"
- Status dot: 🟢 healthy / 🟡 near limit / 🔴 over limit / ⚪ no data or stale
- Hover for full tooltip (today / cost / recent model / 5h / weekly / reset time)

### macOS menubar

- Progress-ring icon fill ratio = 5h quota level
- Click the icon for a menu: today / cost / recent model / 5h / weekly details + Refresh now / Launch at login / Quit

## 🧩 Project Structure

| File | Responsibility |
|---|---|
| `src/usage_reader.py` | Read-only cc-switch.db, aggregates today's tokens / cost / recent model |
| `src/quota_fetcher.py` | Follows the active provider to query package quota (Kimi / Zhipu dispatch) |
| `src/display_text.py` | Pure functions: format token / cost / quota text and color thresholds (Windows) |
| `src/widget.py` | Windows frameless always-on-top strip window |
| `src/mac_text.py` | Mac pure functions: menubar title / ring ratio / menu text |
| `src/mac_bar.py` | macOS rumps menubar App + monochrome progress ring |
| `src/main.py` | Entry: branches on `sys.platform` (`run_windows` / `run_mac`) |

## 📊 Data Sources

- Today's usage / cost / recent model: `~/.cc-switch/cc-switch.db` (read-only), `proxy_request_logs` table
- Active provider: `~/.cc-switch/settings.json`, `currentProviderClaude`
- Package quota: Kimi `api.kimi.com/coding/v1/usages`, Zhipu `{base}/api/monitor/usage/quota/limit`

## ❓ FAQ

<details>
<summary>Can I use it without cc-switch?</summary>

No. This project's data comes 100% from cc-switch's local store (`~/.cc-switch/cc-switch.db` + `settings.json`). Without cc-switch (and without using it to route a third-party provider), the strip / menubar item only shows `--` placeholders. This project is a companion visualizer for cc-switch.

</details>

<details>
<summary>Why no colored dot on the macOS menubar?</summary>

macOS menubar status item icons default to template images (monochrome, auto-inverting with light/dark mode). Color requires directly toggling template off on NSStatusItem, which is risky to write blind. We use a monochrome progress ring instead — the fill ratio itself conveys the level, which is more restrained and idiomatic than a colored dot.

</details>

<details>
<summary>Why must Windows use tool python?</summary>

Anaconda's `Library/bin/msvcp140.dll` (VS2019) conflicts with the VS2022 runtime PySide6 needs; `PySide6.QtWidgets` won't load. Tool python `E:/program/tool/python.exe` (3.12.8) has no such conflict.

</details>

## 📚 Documentation

| Doc | Description |
|---|---|
| `AGENTS.md` | Agent rulebook (environment, modules, pitfalls) |
| `docs/superpowers/specs/` | Design docs |
| `docs/superpowers/plans/` | Implementation plans |

## 🤝 Contributing

```bash
git clone https://github.com/zaynzhu/cc-switch-hub.git
cd cc-switch-hub
"E:/program/tool/python/python.exe" -m pip install PySide6 pytest
"E:/program/tool/python/python.exe" -m pytest tests/ -v
```

Fork → Branch → Commit (`type: description`) → PR.

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

No LICENSE file yet. If you want to open-source it, consider adding one (e.g. MIT).

---

<div align="center">

<sub>Built with ❤️ for Claude Code + cc-switch users</sub>

</div>