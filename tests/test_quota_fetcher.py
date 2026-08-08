import sqlite3, json
from quota_fetcher import get_kimi_config, fetch_kimi_quota

def _make_providers_db(path, rows):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE providers(id TEXT, app_type TEXT, name TEXT, settings_config TEXT)")
    for r in rows:
        db.execute("INSERT INTO providers VALUES (?,?,?,?)", r)
    db.commit(); db.close()

def test_get_kimi_config_found(tmp_path):
    p = str(tmp_path / "t.db")
    cfg = json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://api.kimi.com/coding/",
                              "ANTHROPIC_AUTH_TOKEN": "sk-kimi-abc"}})
    _make_providers_db(p, [("id1", "claude", "Kimi For Coding", cfg)])
    base, token = get_kimi_config(p)
    assert base == "https://api.kimi.com/coding"  # rstrip 去尾斜杠
    assert token == "sk-kimi-abc"

def test_get_kimi_config_missing(tmp_path):
    p = str(tmp_path / "t.db")
    _make_providers_db(p, [("id2", "claude", "Ollama", '{"env":{}}')])
    assert get_kimi_config(p) is None

def test_get_kimi_config_missing_db(tmp_path):
    assert get_kimi_config(str(tmp_path / "nope.db")) is None

class _FakeResp:
    def __init__(self, body): self._body = body
    def read(self): return self._body
    def __enter__(self): return self
    def __exit__(self, *a): return False

def test_fetch_kimi_quota_parse(monkeypatch):
    body = json.dumps({
        "usage": {"limit": "100", "used": "68", "remaining": "32",
                  "resetTime": "2026-08-07T12:51:12Z"},
        "limits": [
            {"window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
             "detail": {"limit": "100", "used": "78", "remaining": "22",
                        "resetTime": "2026-08-07T11:51:12Z"}}
        ]
    }).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=10: _FakeResp(body))
    q = fetch_kimi_quota("https://api.kimi.com/coding", "sk-test")
    assert q == {"weekly": {"used": 68, "limit": 100, "reset": "2026-08-07T12:51:12Z"},
                 "h5": {"used": 78, "limit": 100, "reset": "2026-08-07T11:51:12Z"}}

def test_fetch_kimi_quota_failure(monkeypatch):
    def boom(req, timeout=10): raise Exception("net err")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert fetch_kimi_quota("https://x", "sk") is None

from quota_fetcher import (get_current_provider, detect_provider_type,
                           fetch_zhipu_quota, fetch_quota)


def _make_providers_db_full(path, rows):
    import sqlite3 as _s
    db = _s.connect(path)
    db.execute("CREATE TABLE providers(id TEXT, app_type TEXT, name TEXT, settings_config TEXT, is_current INTEGER)")
    for r in rows:
        db.execute("INSERT INTO providers VALUES (?,?,?,?,?)", r)
    db.commit(); db.close()


def _kimi_cfg():
    return '{"env": {"ANTHROPIC_BASE_URL": "https://api.kimi.com/coding/", "ANTHROPIC_AUTH_TOKEN": "sk-kimi-x"}}'


def test_detect_provider_type():
    assert detect_provider_type('https://api.kimi.com/coding/') == 'kimi'
    assert detect_provider_type('https://api.kimi.com/coding') == 'kimi'
    assert detect_provider_type('https://open.bigmodel.cn/api/paas/v4') == 'zhipu'
    assert detect_provider_type('https://bigmodel.cn/x') == 'zhipu'
    assert detect_provider_type('https://api.z.ai/v1') == 'zhipu'
    assert detect_provider_type('https://ollama.com') is None
    assert detect_provider_type('https://api.xiaomimimo.com/anthropic') is None
    assert detect_provider_type('') is None
    assert detect_provider_type(None) is None


def test_get_current_provider_via_settings(tmp_path):
    import json as _j
    db_p = str(tmp_path / "t.db")
    cfg_kimi = _kimi_cfg()
    _make_providers_db_full(db_p, [
        ("id-kimi", "claude", "Kimi For Coding", cfg_kimi, 0),
        ("id-ollama", "claude", "ollama all", '{"env":{}}', 1),
    ])
    sj = str(tmp_path / "settings.json")
    with open(sj, 'w', encoding='utf-8') as f:
        _j.dump({"currentProviderClaude": "id-kimi"}, f)
    base, token, name = get_current_provider(db_p, sj)
    assert base == "https://api.kimi.com/coding"
    assert token == "sk-kimi-x"
    assert name == "Kimi For Coding"


def test_get_current_provider_fallback_is_current(tmp_path):
    db_p = str(tmp_path / "t.db")
    _make_providers_db_full(db_p, [
        ("id-kimi", "claude", "Kimi For Coding", _kimi_cfg(), 1),
    ])
    sj = str(tmp_path / "settings.json")  # 不存在 → 兜底 is_current
    base, token, name = get_current_provider(db_p, sj)
    assert base == "https://api.kimi.com/coding"
    assert name == "Kimi For Coding"


def test_get_current_provider_missing(tmp_path):
    db_p = str(tmp_path / "t.db")
    _make_providers_db_full(db_p, [])
    assert get_current_provider(db_p, str(tmp_path / "sj.json")) is None


def test_fetch_zhipu_quota_parse(monkeypatch):
    body = json.dumps({
        "data": {
            "limits": [
                {"type": "TOKENS_LIMIT", "percentage": 78, "nextResetTime": 1786000000000, "unit": 3},
                {"type": "TOKENS_LIMIT", "percentage": 68, "nextResetTime": 1786100000000, "unit": 6},
                {"type": "OTHER_LIMIT", "percentage": 50, "unit": 1},
            ]
        }
    }).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=15: _FakeResp(body))
    q = fetch_zhipu_quota("https://open.bigmodel.cn/api/paas/v4", "glm-key")
    assert q['h5']['used'] == 78
    assert q['h5']['limit'] == 100
    assert q['weekly']['used'] == 68
    assert q['weekly']['limit'] == 100
    assert q['h5']['reset'] is not None and q['weekly']['reset'] is not None


def test_fetch_zhipu_quota_auth_header(monkeypatch):
    seen = {}
    def spy(req, timeout=15):
        seen['auth'] = req.headers.get('Authorization')
        return _FakeResp(json.dumps({"data": {"limits": []}}).encode())
    monkeypatch.setattr("urllib.request.urlopen", spy)
    fetch_zhipu_quota("https://open.bigmodel.cn", "glm-key")
    assert seen['auth'] == "glm-key"  # 智谱不加 Bearer 前缀


def test_fetch_zhipu_quota_only_five_hour(monkeypatch):
    body = json.dumps({"data": {"limits": [
        {"type": "TOKENS_LIMIT", "percentage": 40, "nextResetTime": 1786000000000, "unit": 3}]}}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=15: _FakeResp(body))
    q = fetch_zhipu_quota("https://open.bigmodel.cn", "k")
    assert q['h5']['used'] == 40
    assert q['weekly']['used'] is None  # 缺 weekly 窗口用 None 值


def test_fetch_zhipu_quota_failure(monkeypatch):
    def boom(req, timeout=15): raise Exception("net")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert fetch_zhipu_quota("https://open.bigmodel.cn", "k") is None


def test_fetch_quota_dispatch(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=15: _FakeResp(json.dumps({"data": {"limits": [
                            {"type": "TOKENS_LIMIT", "percentage": 55, "nextResetTime": 1786000000000, "unit": 6}]}}).encode()))
    q = fetch_quota("https://open.bigmodel.cn/api/paas/v4", "k")
    assert q is not None and q['weekly']['used'] == 55
    assert fetch_quota("https://ollama.com", "k") is None  # 不识别


def test_fetch_zhipu_quota_malformed_percentage(monkeypatch):
    body = json.dumps({"data": {"limits": [
        {"type": "TOKENS_LIMIT", "percentage": "abc", "nextResetTime": 1786100000000, "unit": 6}]}}).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=15: _FakeResp(body))
    q = fetch_zhipu_quota("https://open.bigmodel.cn", "k")
    assert q is not None  # 畸形 percentage 不抛异常、不绕过 stale 契约
    assert q['weekly']['used'] is None