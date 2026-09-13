import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from widget import UsageWidget

def test_widget_update_data(qapp):
    w = UsageWidget()
    w.update_data((69411491, 60.732, 'kimi-k3'),
                  {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
                   'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}})
    assert '69.4M' in w._text_label.text()
    # 无额度时不崩
    w.update_data((0, 0.0, None), None)
    assert '· --' in w._text_label.text()

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
    assert '周 68%' in w._text_label.text()                     # 保留上次额度仍显示

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

def test_ollama_display_and_stale(qapp, monkeypatch):
    import json
    import quota_fetcher
    from test_quota_fetcher import _FakeResp
    from widget import COLORS

    monkeypatch.setattr(quota_fetcher, '_OLLAMA_RATE_LIMITER', quota_fetcher.RateLimiter())
    body = json.dumps({'limits': {'session': {'usage': 0.234},
                                  'weekly': {'usage': 0.81}}}).encode()
    monkeypatch.setattr('urllib.request.urlopen', lambda req, timeout: _FakeResp(body))
    quota = quota_fetcher.fetch_ollama_quota('synthetic-key')
    w = UsageWidget()
    w.update_data((0, 0, None), quota)
    assert w._text_label.text().endswith('5h 23% · 周 81%')
    assert '本地推算' in w.toolTip()
    assert f"5h: {quota['h5']['used']}/100 重置 --" in w.toolTip()
    assert w._dot_color == COLORS['orange']
    w.update_data((0, 0, None), None)
    assert w._quota is quota
    assert w._stale
    assert w._dot_color == COLORS['grey']
    assert '额度数据已过期' in w.toolTip()
    w.close()


def test_tooltip_reset_beijing(qapp):
    quota = {'h5': {'used': 10, 'limit': 100, 'reset': '2026-09-13T23:30:00Z'},
             'weekly': {'used': 20, 'limit': 100, 'reset': '2026-09-14T00:00:00+00:00'}}
    w = UsageWidget()
    w.update_data((0, 0, None), quota)
    assert '2026-09-14 07:30 北京时间' in w.toolTip()
    assert '2026-09-14 08:00 北京时间' in w.toolTip()
    w.close()
