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