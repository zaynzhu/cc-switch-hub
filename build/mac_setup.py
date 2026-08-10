# build/mac_setup.py
"""py2app 打包配置。在 Mac 上运行：
    pip install py2app rumps
    cd build && python mac_setup.py py2app
产物 build/mac/dist/cc-switch-hub.app
"""
from setuptools import setup

APP = ['src/main.py']
OPTIONS = {
    'argv_emulation': False,
    'packages': ['rumps', 'objc', 'AppKit', 'Foundation',
                 'mac_text', 'usage_reader', 'quota_fetcher', 'display_text'],
    'includes': ['rumps', 'AppKit', 'Foundation'],
    'plist': {
        'LSUIElement': True,  # 不在 Dock 显示，纯菜单栏 app
        'CFBundleName': 'cc-switch-hub',
    },
}

setup(
    app=APP,
    name='cc-switch-hub',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)