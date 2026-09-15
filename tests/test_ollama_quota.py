"""仅使用合成响应和临时 Provider 库，不读取真实账号或联网。"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError

import pytest

import quota_fetcher as fetcher
from display_text import build_display_text, format_reset_line
from mac_text import build_title, build_menu_items, ring_ratio
from test_quota_fetcher import _FakeResp, _make_providers_db_full, _kimi_cfg


@pytest.fixture(autouse=True)
def isolated_limiter(monkeypatch):
    monkeypatch.setattr(fetcher, '_OLLAMA_RATE_LIMITER', fetcher.RateLimiter())


@pytest.fixture
def response(monkeypatch):
    def install(body):
        monkeypatch.setattr('urllib.request.urlopen',
                            lambda req, timeout: _FakeResp(json.dumps(body).encode()))
    return install


def payload(session=0.234, weekly=0.81):
    return {'limits': {'session': {'usage': session}, 'weekly': {'usage': weekly}}}


@pytest.mark.parametrize('url', [
    'https://ollama.com', 'https://ollama.com/', 'https://ollama.com/v1',
    'https://OLLAMA.COM/api/anthropic', 'ollama.com/v1',
])
def test_detect_ollama(url):
    assert fetcher.detect_provider_type(url) == 'ollama'


@pytest.mark.parametrize('url', [
    'https://ollama.com.example/v1', 'https://notollama.com',
    'https://example.com/ollama.com', 'http://localhost:11434',
])
def test_detect_unrelated_host(url):
    assert fetcher.detect_provider_type(url) is None


def test_request_and_display(monkeypatch):
    def request(req, timeout):
        assert req.full_url == 'https://ollama.com/api/usage'
        assert req.get_method() == 'GET'
        assert req.get_header('Authorization') == 'Bearer synthetic-key'
        assert timeout == 7
        return _FakeResp(json.dumps(payload()).encode())
    monkeypatch.setattr('urllib.request.urlopen', request)
    quota = fetcher.fetch_quota('https://ollama.com/v1', 'synthetic-key', timeout=7)
    # h5：接口不返回 reset_at，按实测固定 5h cadence 推算，来源 estimated
    now_before = datetime.now(timezone.utc)
    assert quota['h5']['used'] == 0.234 * 100
    assert quota['h5']['limit'] == 100
    assert quota['h5']['reset_source'] == 'estimated'
    h5_reset = datetime.fromisoformat(quota['h5']['reset'])
    assert h5_reset.tzinfo is not None
    assert h5_reset.timestamp() % (5 * 3600) == 0  # 落在 5h bucket 边界
    assert now_before < h5_reset <= now_before + timedelta(hours=5)
    # weekly：reset 存 UTC ISO 字符串（带时区），来源标注 estimated
    assert quota['weekly']['used'] == 81
    assert quota['weekly']['limit'] == 100
    assert quota['weekly']['reset_source'] == 'estimated'
    reset = datetime.fromisoformat(quota['weekly']['reset'])
    assert reset.tzinfo is not None
    assert reset.astimezone(reset.tzinfo) == reset  # 已是 tz-aware
    assert build_display_text(0, 0, None, quota).endswith('5h 23% · 周 81%')
    assert build_title(0, 0, 23.4, 100, 81, 100) == '0 $0.00 · 23% · 81%'
    assert ring_ratio(quota['h5']['used'], 100) == pytest.approx(0.234)
    items = build_menu_items(0, 0, None, quota, True)
    assert items[3].startswith('5h: 23% 预计重置 ')
    assert '本地推算' in items[3]
    assert items[4].startswith('周: 81% 预计重置 ')
    assert '本地推算' in items[4]
    assert items[5] == '(额度数据已过期)'


@pytest.mark.parametrize('value', [0, 1, 0.00012345, 0.999999])
def test_valid_ratio(response, value):
    response(payload(value, value))
    quota = fetcher.fetch_ollama_quota('synthetic-key')
    assert quota['h5']['used'] == value * 100
    assert quota['weekly']['used'] == value * 100


@pytest.mark.parametrize('window', ['session', 'weekly'])
@pytest.mark.parametrize('value', [None, True, False, '0.23', [], {}, -0.01, 1.01,
                                   float('nan'), float('inf'), float('-inf')])
def test_invalid_ratio(response, window, value):
    body = payload()
    body['limits'][window]['usage'] = value
    response(body)
    assert fetcher.fetch_ollama_quota('synthetic-key') is None


@pytest.mark.parametrize('body', [
    None, [], {}, {'limits': None}, {'limits': []}, {'limits': {}},
    {'limits': {'session': {'usage': 0}}},
    {'limits': {'session': {}, 'weekly': {'usage': 0}}},
    {'limits': {'session': {'usage': 0}, 'weekly': {}}},
    {'limits': {'session': None, 'weekly': {'usage': 0}}},
])
def test_changed_structure(response, body):
    response(body)
    assert fetcher.fetch_ollama_quota('synthetic-key') is None


@pytest.mark.parametrize('body', [b'<html>error</html>', b'{', b'\xff'])
def test_invalid_json(monkeypatch, body):
    monkeypatch.setattr('urllib.request.urlopen', lambda req, timeout: _FakeResp(body))
    assert fetcher.fetch_ollama_quota('synthetic-key') is None


@pytest.mark.parametrize('error', [
    URLError('offline'), TimeoutError(),
    *[HTTPError('https://ollama.com/api/usage', code, 'error', {}, None)
      for code in (401, 403, 404, 500, 502, 503)],
], ids=['network', 'timeout', '401', '403', '404', '500', '502', '503'])
def test_request_failure(monkeypatch, capsys, error):
    def fail(req, timeout):
        raise error
    monkeypatch.setattr('urllib.request.urlopen', fail)
    assert fetcher.fetch_ollama_quota('synthetic-secret') is None
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize(('now', 'expected'), [
    ('2026-09-13T23:59:59+00:00', '2026-09-14T00:00:00+00:00'),  # 周日午夜前 → 明天周一
    ('2026-09-14T00:00:00+00:00', '2026-09-21T00:00:00+00:00'),  # 恰在周一 00:00 UTC → 严格取下周
    ('2026-09-14T00:00:01+00:00', '2026-09-21T00:00:00+00:00'),  # 周一 00:00 已过 → 下周
    ('2026-09-14T07:59:59+08:00', '2026-09-14T00:00:00+00:00'),  # 北京 周一 07:59（仍是周日 UTC）
    ('2026-09-14T08:00:00+08:00', '2026-09-21T00:00:00+00:00'),  # 北京 周一 08:00 = UTC 00:00 → 下周
    ('2026-09-30T12:00:00+00:00', '2026-10-05T00:00:00+00:00'),  # 跨月
    ('2026-12-31T12:00:00+00:00', '2027-01-04T00:00:00+00:00'),  # 跨年
])
def test_next_weekly_reset(now, expected):
    """实账号验证规则：weekly.usage 于周一 00:00 UTC 刷新 → 严格晚于 now 的下个周一。"""
    now_dt = datetime.fromisoformat(now)
    expected_dt = datetime.fromisoformat(expected)
    reset = fetcher.next_ollama_weekly_reset(now_dt)
    assert reset == expected_dt
    assert reset.tzinfo is not None        # timezone-aware
    assert reset.utcoffset().total_seconds() == 0  # 统一 UTC
    assert reset > now_dt                   # 严格晚于 now


@pytest.mark.parametrize(('now', 'expected'), [
    # 实测边界：UTC 05:00 / 10:00 / 15:00 / 20:00（北京时间 13/18/23/04 点）
    ('2026-09-14T04:59:59+00:00', '2026-09-14T05:00:00+00:00'),
    ('2026-09-14T05:00:00+00:00', '2026-09-14T10:00:00+00:00'),  # 恰在边界 → 下一个
    ('2026-09-14T09:59:59+00:00', '2026-09-14T10:00:00+00:00'),
    ('2026-09-14T10:00:00+00:00', '2026-09-14T15:00:00+00:00'),
    ('2026-09-14T14:59:59+00:00', '2026-09-14T15:00:00+00:00'),
    ('2026-09-14T15:00:00+00:00', '2026-09-14T20:00:00+00:00'),
    ('2026-09-14T19:59:59+00:00', '2026-09-14T20:00:00+00:00'),
    ('2026-09-14T20:00:00+00:00', '2026-09-15T01:00:00+00:00'),  # 跨日
    ('2026-09-14T12:59:59+08:00', '2026-09-14T05:00:00+00:00'),  # 非零时区输入
    ('2026-09-30T23:30:00+00:00', '2026-10-01T02:00:00+00:00'),  # 跨月
    ('2026-12-31T23:00:00+00:00', '2027-01-01T04:00:00+00:00'),  # 跨年
])
def test_next_session_reset(now, expected):
    """实账号连续验证：session 重置为固定 5h cadence，边界与 5h Unix timestamp bucket 对齐。
    5h 不整除 24h，窗口跨日持续推进（09-30 21:00 边界的下一个是 10-01 02:00）。"""
    now_dt = datetime.fromisoformat(now)
    expected_dt = datetime.fromisoformat(expected)
    reset = fetcher.next_ollama_session_reset(now_dt)
    assert reset == expected_dt
    assert reset.tzinfo is not None               # timezone-aware
    assert reset.utcoffset().total_seconds() == 0  # 统一 UTC
    assert reset > now_dt                          # 严格晚于 now


def test_session_reset_local_display():
    """数据层存 UTC，展示层复用现有 format_reset_line 转北京时间并标本地推算。"""
    reset = fetcher.next_ollama_session_reset(
        datetime.fromisoformat('2026-09-15T00:30:00+00:00'))
    assert reset.isoformat() == '2026-09-15T01:00:00+00:00'
    assert format_reset_line(reset.isoformat(), 'estimated') == \
        '预计重置 2026-09-15 09:00 北京时间（本地推算）'


def test_rate_limit(monkeypatch, response):
    now = [100.0]
    monkeypatch.setattr(fetcher, 'monotonic', lambda: now[0])
    response(payload())
    assert fetcher.fetch_ollama_quota('synthetic-key') is not None
    now[0] = 101.999
    assert fetcher.fetch_ollama_quota('synthetic-key') is None
    now[0] = 102.0
    assert fetcher.fetch_ollama_quota('synthetic-key') is not None


def test_concurrent_rate_limit(monkeypatch):
    monkeypatch.setattr(fetcher, 'monotonic', lambda: 100.0)
    limiter = fetcher.RateLimiter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: limiter.acquire(), range(16))) == 1


def test_active_provider_switch(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'providers.db')
    settings = tmp_path / 'settings.json'
    config = json.dumps({'env': {'ANTHROPIC_BASE_URL': 'https://ollama.com/v1/',
                                 'ANTHROPIC_AUTH_TOKEN': 'synthetic-ollama'}})
    _make_providers_db_full(db_path, [
        ('kimi', 'claude', 'Kimi', _kimi_cfg(), 1),
        ('ollama', 'claude', 'Ollama', config, 0),
    ])
    seen = []
    monkeypatch.setattr(fetcher, 'fetch_ollama_quota',
                        lambda key, timeout: seen.append(('ollama', key)))
    monkeypatch.setattr(fetcher, 'fetch_kimi_quota',
                        lambda base, key, timeout: seen.append(('kimi', key)))
    for provider_id in ('ollama', 'kimi'):
        settings.write_text(json.dumps({'currentProviderClaude': provider_id}))
        base, key, _ = fetcher.get_current_provider(db_path, settings)
        fetcher.fetch_quota(base, key)
    assert seen == [('ollama', 'synthetic-ollama'), ('kimi', 'sk-kimi-x')]
    settings.write_text('{"currentProviderClaude": "missing"}')
    assert fetcher.get_current_provider(db_path, settings) is None


@pytest.mark.parametrize('config', [
    {}, {'env': {}}, {'env': None}, {'env': []}, [],
    {'env': {'ANTHROPIC_BASE_URL': 'https://ollama.com'}},
    {'env': {'ANTHROPIC_AUTH_TOKEN': 'synthetic-key'}},
])
def test_missing_credentials(tmp_path, config):
    db_path = str(tmp_path / 'providers.db')
    settings = tmp_path / 'settings.json'
    _make_providers_db_full(db_path, [
        ('ollama', 'claude', 'Ollama', json.dumps(config), 0),
        ('kimi', 'claude', 'Kimi', _kimi_cfg(), 1),
    ])
    settings.write_text('{"currentProviderClaude": "ollama"}')
    assert fetcher.get_current_provider(db_path, settings) is None


@pytest.mark.parametrize(('base', 'name', 'args'), [
    ('https://api.kimi.com/coding', 'fetch_kimi_quota',
     ('https://api.kimi.com/coding', 'synthetic-key', 4)),
    ('https://api.z.ai/v1', 'fetch_zhipu_quota',
     ('https://api.z.ai/v1', 'synthetic-key', 4)),
    ('https://ollama.com/v1', 'fetch_ollama_quota', ('synthetic-key', 4)),
])
def test_dispatch_preserves_arguments(monkeypatch, base, name, args):
    seen = []
    sentinel = object()
    def query(*received):
        seen.append(received)
        return sentinel
    monkeypatch.setattr(fetcher, name, query)
    assert fetcher.fetch_quota(base, 'synthetic-key', timeout=4) is sentinel
    assert seen == [args]


@pytest.mark.parametrize('key', [None, '', '   ', 123])
def test_invalid_key_does_not_request(monkeypatch, key):
    calls = []
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **kw: calls.append(a))
    assert fetcher.fetch_ollama_quota(key) is None
    assert calls == []
