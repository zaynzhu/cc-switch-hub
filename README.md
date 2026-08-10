# cc-switch-hub 任务栏用量条

Windows 任务栏上的常驻窄条，零点击显示 Claude Code（经 cc-switch 接入第三方厂商）的**今日 token 用量、估算花费、近用模型**，以及套餐制厂商（Kimi / 智谱 GLM）的 **5 小时窗口与周额度**百分比。

数据复用 cc-switch 本地数据库与厂商额度接口，不重复造轮子。

## 运行

```bash
"E:/program/tool/python/python.exe" src/main.py
```

无边框置顶窄条出现在**屏幕左下角、任务栏上沿**。可拖动（位置记忆）、右键有「立即刷新 / 退出」菜单；额度查询失败时保留上次数据并变灰提示过期。

## 依赖

- Python 3.12（**必须用 tool python** `E:/program/tool/python/python.exe`，原因见下）
- PySide6：`"E:/program/tool/python/python.exe" -m pip install PySide6`
- pytest（开发）：`"E:/program/tool/python/python.exe" -m pip install pytest`

> ⚠️ 不要用 Anaconda 的 python：其 `Library/bin/msvcp140.dll`（VS2019）与 PySide6 所需 VS2022 运行时冲突，`PySide6.QtWidgets` 无法加载。

## 测试

```bash
"E:/program/tool/python/python.exe" -m pytest tests/ -v
```

## 项目结构

| 文件 | 职责 |
|---|---|
| `src/usage_reader.py` | 只读 cc-switch.db，全部汇总今日 token / 花费 / 近用模型 |
| `src/quota_fetcher.py` | 跟随当前激活厂商查套餐额度（detect 判型 + Kimi / 智谱分发） |
| `src/display_text.py` | 纯函数：格式化 token / 花费 / 额度文本与颜色阈值 |
| `src/widget.py` | 无边框置顶窄条窗口（绘制、颜色、tooltip、拖动、右键菜单） |
| `src/main.py` | 入口：定时刷新、托盘、后台额度线程、位置记忆 |

## 数据来源

- 今日用量 / 花费 / 近用模型：`~/.cc-switch/cc-switch.db`（只读）的 `proxy_request_logs` 表
- 当前激活厂商：`~/.cc-switch/settings.json` 的 `currentProviderClaude`
- 套餐额度：Kimi `api.kimi.com/coding/v1/usages`、智谱 `{base}/api/monitor/usage/quota/limit`

## 开机自启（可选）

见 `docs/superpowers/plans/2026-08-07-taskbar-usage-widget.md` 的 Task 6：创建启动文件夹快捷方式，用 `pythonw.exe` 无控制台启动。

## 文档

- 设计文档：`docs/superpowers/specs/`
- 实现计划：`docs/superpowers/plans/`
- agent 规则手册：`AGENTS.md`

## macOS 使用

```bash
pip install rumps
python src/main.py
```

菜单栏出现用量条：进度环 icon（填充=5h 额度水位）+ `69.4M $0.03 58%` 文字，点击看完整详情。

### 打包成 dmg（Mac）

```bash
pip install py2app rumps
cd build && python mac_setup.py py2app
codesign --sign - --force --deep dist/cc-switch-hub.app
hdiutil create -volname "cc-switch-hub" -srcfolder dist/cc-switch-hub.app -ov -format UDZO dist/cc-switch-hub.dmg
```

### 首次打开 dmg（Gatekeeper 绕过）

dmg 仅 ad-hoc 签名、未公证，双击会被拦。右键点 app →「打开」→「仍要打开」；或「系统设置 → 隐私与安全性 → 仍要打开」。
