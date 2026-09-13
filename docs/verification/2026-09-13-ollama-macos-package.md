# Ollama Cloud legacy macOS 打包验收

- 功能源码：`d32a116`。
- 产物：`build/dist/cc-switch-hub-ollama-d32a116.dmg`（约 9.4 MiB，构建产物不入 Git）。
- SHA-256：`055d8aa370e6e40835f2e48a2b42b9c1384226fcf04cd575c9df6dad883f1653`。
- 使用现有 Command Line Tools Python 3.9.6、py2app、rumps 打包；ad-hoc 签名，未公证。

## 构建注意

在 `build/` 运行 `python3 mac_setup.py py2app`。本次环境生成的 `Contents/MacOS/python` 保留了指向包外的 `@executable_path/../../../../Python3`，直接运行时报 dyld 动态库缺失。对本次 Python 3.9 产物执行以下修正后重新签名（仓库根目录）：

```sh
install_name_tool -change '@executable_path/../../../../Python3' '@executable_path/../Frameworks/Python3.framework/Versions/3.9/Python3' build/dist/cc-switch-hub.app/Contents/MacOS/python
codesign --sign - --force --deep build/dist/cc-switch-hub.app
```

其他 Python 版本重建时应先检查 `otool -L` 与实际 framework 路径，不直接套用 3.9 路径。DMG 根目录包含应用和指向 `/Applications` 的安装快捷方式。

## 验证结果

- 功能提交的完整测试：126 项通过，包括 Qt 离屏组件、macOS 文本函数、Ollama 合成响应与 Kimi/智谱回归。
- 应用包内 `quota_fetcher.py` 与功能源码逐字节一致。
- 修正后包内 Python 可执行 `-V`；Info.plist 格式检查通过。
- 应用使用临时空 HOME 启动 5 秒，进程保持运行，无标准输出、错误输出或 traceback；测试结束后终止该测试进程。未读取真实 cc-switch 数据或请求账号接口。
- DMG 的 `hdiutil verify` 通过；只读挂载后再次验证包内源码、Python 启动与 `codesign --verify --deep --strict`，均通过。
- 未替换 `/Applications` 中用户现有应用。真实 Ollama 账号查询和实际 Provider 切换由安装后验收。

## 安装后验证

退出旧应用，打开 DMG，将应用拖入 Applications 并替换。启动新版，在 cc-switch 激活包含真实 Base URL 和 Key 的 Ollama Provider，再从菜单点击“立即刷新”。检查 5h / 周比例、5h 未知重置时间和周重置“本地推算”标记；切换到 Kimi 或智谱后再次刷新，确认额度跟随。

## 安装后清理

用户安装新版后要求只保留正式版。已确认 `/Applications/cc-switch-hub.app` 包含 Ollama 查询代码且签名验证通过；随后弹出安装镜像，将当前及旧项目中的三个应用副本、两份 DMG 和 DMG 暂存目录移到废纸篓，并移除重复应用注册。上述产物路径现已清空，源码与 cc-switch 配置保留。

## 北京时间显示更新

按用户要求，重置详情统一使用北京时间；Ollama 周重置显示周一 08:00 并保留“本地推算”，Kimi/智谱带时区的 API 时间通过共用格式化函数转换。完整测试 129 项通过。直接更新已安装正式版的三个 Python 模块（quota_fetcher、display_text、mac_text），重新签名并通过隔离空 HOME 启动验证，再启动正式版。未新增 .app 副本或 DMG；此前 DMG 哈希仅对应初次打包快照。

## 双环与双百分比更新

修复 Cocoa 满额圆弧归一化为零长度的问题：100% 使用完整椭圆路径，部分圆弧显式指定顺时针。macOS 内圈显示五小时、外圈显示周额度，过期降低透明度且不再扣减比例；菜单栏常驻文字同时标注 `5h …% · 周 …%`。当前 Provider 的一次真实 Ollama 查询返回五小时 0%、周 100%，用户确认与实际一致；未记录 Key。

通用与 Qt 测试 130 项通过（该环境跳过 AppKit 模块）；系统 Python 的 6 项真实 Cocoa 测试覆盖满圈、内外圈映射、四分之一弧方向、过期透明度、未知值和 UI 双百分比映射，全部通过。另检查了真实栅格化预览。直接更新正式版中的 mac_bar 字节码及 mac_text 模块，签名与隔离启动通过后重启；未生成额外应用或 DMG。

本次安装验收还发现 py2app 优先加载 `python39.zip` 的编译模块，先前仅同步旁边 `.py` 的北京时间更新不能证明已生效。首次双百分比安装因新旧函数签名不匹配而失败并自动回滚；随后统一编译并更新 mac_bar、mac_text、display_text、quota_fetcher 的包内 `.pyc`，同步旁边源码。通过包内实际导入检查双环参数、双百分比文本及北京时间，再重新签名、隔离启动并重启正式版。后续不得仅以旁边源码一致作为安装验收。

## 菜单栏紧凑显示

经用户确认，常驻文字改为 `0% / 100%`（左侧五小时、右侧周额度），去掉标签、今日 token 和花费；双环与点击后的完整详情保留。94 项相关文本、Ollama 和 Cocoa 测试通过。同步正式包实际编译模块及源码、重新签名，通过包内行为与隔离启动检查后重启；没有生成额外安装包或应用副本。

## 常驻信息与外圈调整

用户澄清仅去掉 `5h` 和“周”标签，不移除原有信息：常驻文字恢复为 `69.4M $0.03 · 0% · 100%`，保留 token、花费和原分隔点，去掉斜杠。外圈已用弧线宽由 2.0 增至 2.6，内圈保持 2.0。94 项相关测试通过；正式包编译模块已同步，签名及隔离启动验证通过后重启。
