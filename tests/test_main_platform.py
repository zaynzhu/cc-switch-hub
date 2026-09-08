import sys

import pytest


class _FakeScreen:
    """screen_at 回调的返回桩：只有 name()。"""
    def __init__(self, name):
        self._name = name
    def name(self):
        return self._name


def test_resolve_restore_pos_screen_matches(monkeypatch):
    """记忆坐标落在记忆屏上 → 恢复坐标。"""
    import main
    st = {'x': 786, 'y': 0, 'screen': 'PF32FC'}
    assert main.resolve_restore_pos(st, lambda x, y: _FakeScreen('PF32FC')) == (786, 0)

def test_resolve_restore_pos_screen_changed(monkeypatch):
    """记忆坐标落到了别的屏（显示器排列变化）→ 拒绝恢复，回默认放置。"""
    import main
    st = {'x': 2546, 'y': -71, 'screen': '\\\\.\\DISPLAY1'}
    assert main.resolve_restore_pos(st, lambda x, y: _FakeScreen('PF32FC')) is None

def test_resolve_restore_pos_legacy_no_screen(monkeypatch):
    """旧格式记忆（无 screen 字段）→ 坐标在任一屏上即恢复，保持兼容。"""
    import main
    st = {'x': 786, 'y': 0}
    assert main.resolve_restore_pos(st, lambda x, y: _FakeScreen('PF32FC')) == (786, 0)

def test_resolve_restore_pos_offscreen(monkeypatch):
    """坐标不属于任何屏（screenAt 返回 None）→ 拒绝恢复。"""
    import main
    st = {'x': 99999, 'y': 0, 'screen': 'PF32FC'}
    assert main.resolve_restore_pos(st, lambda x, y: None) is None

def test_resolve_restore_pos_missing_keys(monkeypatch):
    """记忆缺失坐标 → 拒绝恢复。"""
    import main
    assert main.resolve_restore_pos({}, lambda x, y: _FakeScreen('PF32FC')) is None

def test_save_settings_records_screen(monkeypatch, tmp_path):
    """位置记忆须带屏幕归属，供下次启动校验。"""
    import main
    monkeypatch.setattr(main, 'SETTINGS_PATH', str(tmp_path / 'settings.json'))
    main.save_settings(type('P', (), {'x': lambda s: 10, 'y': lambda s: 20})(), 'PF32FC')
    import json
    with open(tmp_path / 'settings.json', encoding='utf-8') as f:
        st = json.load(f)
    assert st == {'x': 10, 'y': 20, 'screen': 'PF32FC'}


def test_main_exposes_run_windows_run_mac(monkeypatch):
    import main
    assert hasattr(main, 'run_windows')
    assert hasattr(main, 'run_mac')
    assert hasattr(main, 'main')

def test_windows_path_does_not_import_pyside6_at_module_level(monkeypatch):
    """main.py 顶部不得 import PySide6，保证 Mac 加载不崩。

    全量套件里 test_widget 的收集阶段已加载 PySide6，故不能看全局 sys.modules，
    只能验证 re-import main 自身不新增 PySide6 相关模块。"""
    monkeypatch.setattr(sys, 'platform', 'darwin')
    if 'main' in sys.modules:
        del sys.modules['main']
    before = {k for k in sys.modules if k == 'PySide6' or k.startswith('PySide6.')}
    import main  # noqa
    after = {k for k in sys.modules if k == 'PySide6' or k.startswith('PySide6.')}
    # main.py 自身不得新增 PySide6 import
    assert after == before

def test_run_mac_calls_mac_bar(monkeypatch):
    """darwin 平台 main() 调 mac_bar.run，不碰 PySide6。"""
    called = {}
    import types
    fake_mac = types.ModuleType('mac_bar')
    fake_mac.run = lambda: called.setdefault('ran', True)
    monkeypatch.setitem(__import__('sys').modules, 'mac_bar', fake_mac)
    monkeypatch.setattr(sys, 'platform', 'darwin')
    import main
    main.main()
    assert called.get('ran') is True