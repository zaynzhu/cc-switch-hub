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