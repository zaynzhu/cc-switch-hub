import sys, importlib

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