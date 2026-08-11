# build/mac_setup.py
"""py2app 打包配置。在 Mac 上运行：
    pip install py2app rumps
    cd build && python mac_setup.py py2app
产物 build/mac/dist/cc-switch-hub.app
"""
import os
from setuptools import setup

# 基于 __file__ 解析 src/main.py 绝对路径，不依赖 cwd
APP = [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'main.py')]
_ICONS_DIR = os.path.dirname(os.path.abspath(__file__))
OPTIONS = {
    'argv_emulation': False,
    'iconfile': os.path.join(_ICONS_DIR, 'ripple.icns'),  # app 图标（Dock + Finder/启动台）
    'packages': ['rumps', 'objc', 'AppKit', 'Foundation',
                 'mac_text', 'usage_reader', 'quota_fetcher', 'display_text'],
    'includes': ['rumps', 'AppKit', 'Foundation'],
    'plist': {
        'LSUIElement': True,  # 纯菜单栏 app，不在 Dock 显示
        'CFBundleName': 'cc-switch-hub',
    },
}

setup(
    app=APP,
    name='cc-switch-hub',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)