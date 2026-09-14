# build/win_build.ps1
# Windows exe 打包。在项目根目录运行：powershell -ExecutionPolicy Bypass -File build/win_build.ps1
# 产物：dist/cc-switch-hub.exe（可双击运行，窄条 + 托盘）
$ErrorActionPreference = 'Stop'
$py = "E:/program/tool/python/python.exe"

# --noconsole：GUI 程序不弹黑窗
# --onefile：单 exe
# --icon：exe 文件图标（$PSScriptRoot 基准，不依赖 cwd）
# --add-data：ripple.ico 打进 exe 供运行时托盘图标读取（sys._MEIPASS/ripple.ico）
# 不用 --collect-all PySide6：那会把整个 PySide6（全部 Qt 模块 + 插件）无差别打进
# exe，体积臃肿（~248MB）。改靠 PyInstaller 自带 PySide6 hook 自动只收集必需件。
& $py -m PyInstaller --noconfirm --noconsole --onefile `
    --name cc-switch-hub `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtCore `
    --icon "$PSScriptRoot\ripple.ico" `
    --add-data "$PSScriptRoot\ripple.ico;." `
    src/main.py

# 原生命令失败不触发 $ErrorActionPreference，必须显式透传退出码，
# 否则 exe 被占用（PermissionError）时脚本仍 exit 0，误报"打包成功"
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller 打包失败（exit $LASTEXITCODE）；常见原因：dist/cc-switch-hub.exe 被运行中的用量条进程占用，先退出再打包"
    exit $LASTEXITCODE
}

Write-Host "产物：dist/cc-switch-hub.exe"
exit 0