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
