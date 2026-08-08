import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from widget import UsageWidget

def test_widget_update_data(qapp):
    w = UsageWidget()
    w.update_data((69411491, 60.732, 'kimi-k3'),
                  {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
                   'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}})
    assert '69.4M' in w._label.text()
    # 无额度时不崩
    w.update_data((0, 0.0, None), None)
    assert '近用 --' in w._label.text()

def test_usage_refresh_preserves_stale(qapp):
    w = UsageWidget()
    quota = {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
             'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}}
    w.update_data((69411491, 60.732, 'kimi-k3'), quota)
    assert w._stale is False
    w.update_data((69411491, 60.732, 'kimi-k3'), None)   # 额度失败 → stale
    assert w._stale is True
    w.update_data((69411491, 60.732, 'kimi-k3'))          # 仅刷用量，无 quota 参数 → stale 保持
    assert w._stale is True
    assert '周 68%' in w._label.text()                     # 保留上次额度仍显示

def test_widget_clamps_offscreen_right(qapp):
    from PySide6.QtWidgets import QApplication
    w = UsageWidget()
    w.update_data((69411491, 60.732, 'kimi-k3'),
                  {'h5': {'used': 78, 'limit': 100, 'reset': 't'},
                   'weekly': {'used': 68, 'limit': 100, 'reset': 't'}})
    g = QApplication.primaryScreen().availableGeometry()
    w.move(g.right() + 50, g.bottom() - w.height())  # 故意移出屏幕右缘
    w._clamp_to_screen()
    assert w.x() + w.width() <= g.right() + 1