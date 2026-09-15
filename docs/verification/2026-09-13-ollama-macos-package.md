# Ollama Cloud legacy 与 macOS 验收记录

## 当前状态（2026-09-13）

- 当前界面对应源码 `fec2888`；正式安装位于 `/Applications/cc-switch-hub.app`。
- 菜单栏保留 token、花费和两个已用百分比，例如 `69.4M $0.03 · 0% · 100%`；左侧五小时、右侧周额度，仅省略窗口标签。完整字段、模型和重置时间在详情菜单。
- 内圈显示五小时、外圈显示周额度；线宽分别为 2.0 / 2.6。0% 是淡色轨道，100% 是完整粗圈；stale 只降低透明度，不扣减比例。
- 重置时间显示北京时间。Ollama 5h 与周重置均按已实测验证的规则本地推算并标注来源，不冒充 API 时间（2026-09-15 起 5h 重置由固定 5h cadence 推算，此前记录为"session 重置未知"）。
- 首次 DMG 对应 `d32a116`，后续更新直接同步正式版的编译模块。用户要求只保留正式安装：构建应用、暂存副本与两份 DMG 已移到废纸篓，镜像已弹出；仓库没有可直接下载的最新 DMG。

## 数据与验收边界

Ollama 查询沿用当前 Claude Provider 的真实凭据，固定请求 `https://ollama.com/api/usage`；`session.usage` / `weekly.usage` 为已用比例，不是 token 数。身份读取与错误契约见 [README](../../README.md#ollama-cloud-legacy)。

- 本轮一次真实 Ollama 查询返回五小时 0%、周 100%，用户确认与实际相符；这是当时快照，不表示持续监控结果。未记录 Key。
- 通用与 Qt 测试曾全量通过 130 项；该环境缺少 AppKit，跳过原生绘图测试模块。另以系统 Python 运行 6 项真实 Cocoa 测试，覆盖满圈、内外圈映射、顺时针圆弧、过期透明度、未知值和 UI 数据映射。
- 最后一次常驻文字恢复与外圈加粗后，94 项相关文本、Ollama 和 Cocoa 测试通过。
- 正式版包内编译模块的行为、签名和隔离空 HOME 启动均验证通过，随后重启正式版。隔离启动不读取真实 cc-switch 配置。
- 未验证本轮 Windows 原生桌面/EXE、真实 Kimi/智谱切换或新制作的最终 DMG；单元测试与 Qt 离屏测试不代表这些验收已完成。

## 构建与更新的两个已验证陷阱

首次使用 Command Line Tools Python 3.9.6、py2app、rumps 打包，基础命令见 [README](../../README.md#打包)。签名为 ad-hoc，未公证。

### 包内 Python 动态库路径

本次环境生成的 `Contents/MacOS/python` 保留了指向包外的 `@executable_path/../../../../Python3`，直接运行时报 dyld 动态库缺失。对该 Python 3.9 产物执行以下修正后重新签名（仓库根目录）：

```sh
install_name_tool -change '@executable_path/../../../../Python3' '@executable_path/../Frameworks/Python3.framework/Versions/3.9/Python3' build/dist/cc-switch-hub.app/Contents/MacOS/python
codesign --sign - --force --deep build/dist/cc-switch-hub.app
```

其他环境须先核对 `otool -L` 和实际 framework 路径，不能直接套用 3.9 路径。修正后应验证包内 Python 可以运行，并执行 `codesign --verify --deep --strict`。

### 实际加载的是编译模块

正式包优先加载 `Contents/Resources/lib/python39.zip` 中的 `.pyc`，即使旁边 `lib/python3.9/` 也有同名源码。只替换 `.py` 会造成“源码已更新、运行仍旧版”，甚至出现函数签名不匹配。

更新应停止目标应用，备份待替换文件，使用兼容的 Python 版本编译实际变动模块，同步包内字节码及旁边源码，重新签名。验证必须执行包内编译模块的行为，再用空 HOME 隔离启动；失败时恢复备份。仅比较旁边源码不足以证明已安装版本生效。

如重新生成 DMG，应只读挂载后检查包内代码和签名，并执行 `hdiutil verify`；安装成功后弹出镜像、清理构建和暂存副本，保留用户正式安装、源码与配置。不要重建系统全局应用索引来掩盖副本问题。
