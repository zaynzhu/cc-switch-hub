from mac_text import build_title, ring_ratio, build_menu_items

def test_build_title_with_quota():
    assert build_title(69411491, 0.03, 78, 100, 100, 100) == '69.4M $0.03 · 5h 78% · 周 100%'

def test_build_title_without_quota():
    assert build_title(0, 0.0, None, None, None, None) == '0 $0.00 · 5h -- · 周 --'

def test_ring_ratio():
    assert ring_ratio(78, 100) == 0.78
    assert ring_ratio(0, 100) == 0.0
    assert ring_ratio(150, 100) == 1.0  # 超限封顶 1.0
    assert ring_ratio(None, 100) is None
    assert ring_ratio(78, 0) is None
    assert ring_ratio(78, None) is None

def test_build_menu_items_with_quota():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': '02:30'},
         'weekly': {'used': 68, 'limit': 100, 'reset': '周一'}}
    items = build_menu_items(69411491, 0.03, 'kimi-k3', q, False)
    assert items[0] == '今日: 69.4M tok'
    assert items[1] == '花费: $0.03'
    assert items[2] == '近用: kimi-k3'
    assert items[3] == '5h: 78% 重置 02:30'
    assert items[4] == '周: 68% 重置 周一'

def test_build_menu_items_without_quota():
    items = build_menu_items(0, 0.0, None, None, False)
    assert items[0] == '今日: 0 tok'
    assert items[1] == '花费: $0.00'
    assert items[2] == '近用: --'
    assert len(items) == 3  # 无额度不附 5h/周 行

def test_build_menu_items_stale():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': '02:30'},
         'weekly': {'used': 68, 'limit': 100, 'reset': '周一'}}
    items = build_menu_items(69411491, 0.03, 'kimi-k3', q, True)
    assert items[-1] == '(额度数据已过期)'

def test_menu_reset_beijing():
    quota = {'h5': {'used': 10, 'limit': 100, 'reset': '2026-09-13T23:30:00Z'},
             'weekly': {'used': 20, 'limit': 100, 'reset': '2026-09-14T00:00:00+00:00'}}
    items = build_menu_items(0, 0, None, quota, False)
    assert items[3] == '5h: 10% 重置 2026-09-14 07:30 北京时间'
    assert items[4] == '周: 20% 重置 2026-09-14 08:00 北京时间'


def test_title_zero_session_full_weekly():
    assert build_title(0, 0, 0, 100, 100, 100) == '0 $0.00 · 5h 0% · 周 100%'
