# build/win_build.ps1
# Windows exe 打包。在项目根目录运行：powershell -ExecutionPolicy Bypass -File build/win_build.ps1
# 产物：dist/cc-switch-hub.exe（可双击运行，窄条 + 托盘）
$ErrorActionPreference = 'Stop'
$py = "E:/program/tool/python/python.exe"

# --noconsole：GUI 程序不弹黑窗
# --onefile：单 exe
# --icon：exe 文件/任务栏图标（$PSScriptRoot 基准，不依赖 cwd）
# 不用 --collect-all PySide6：那会把整个 PySide6（全部 Qt 模块 + 插件）无差别打进
# exe，体积臃肿（~248MB）。改靠 PyInstaller 自带 PySide6 hook 自动只收集必需件。
& $py -m PyInstaller --noconfirm --noconsole --onefile `
    --name cc-switch-hub `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtCore `
    --icon "$PSScriptRoot\ripple.ico" `
    src/main.py

Write-Host "产物：dist/cc-switch-hub.exe"