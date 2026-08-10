# build/win_build.ps1
# Windows exe 打包。在项目根目录运行：powershell -ExecutionPolicy Bypass -File build/win_build.ps1
# 产物：dist/cc-switch-hub.exe（可双击运行，窄条 + 托盘）
$ErrorActionPreference = 'Stop'
$py = "E:/program/tool/python/python.exe"

# --noconsole：GUI 程序不弹黑窗
# --onefile：单 exe
# --collect-all PySide6：把 PySide6 全部资源（插件 / Qt dll / translations）打进去
& $py -m PyInstaller --noconfirm --noconsole --onefile `
    --name cc-switch-hub `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtCore `
    --collect-all PySide6 `
    src/main.py

Write-Host "产物：dist/cc-switch-hub.exe"