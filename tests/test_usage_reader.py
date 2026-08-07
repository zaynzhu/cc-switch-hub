import sqlite3, time, os
from usage_reader import get_today_usage

def _make_db(path):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE proxy_request_logs(
        created_at INTEGER, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
        cache_read_tokens INTEGER, cache_creation_tokens INTEGER, total_cost_usd REAL)""")
    return db

def test_today_aggregation(tmp_path):
    p = str(tmp_path / "t.db")
    db = _make_db(p)
    now = int(time.time())
    # 今日两条
    db.execute("INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?)",
               (now, 'kimi-k3', 1000, 500, 200, 100, 0.12))
    db.execute("INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?)",
               (now, 'glm-5.2', 2000, 300, 0, 0, 0.08))
    # 昨日一条（不应计入）
    db.execute("INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?)",
               (now - 90000, 'kimi-k3', 9999, 9999, 0, 0, 9.99))
    db.commit(); db.close()
    tokens, cost, model = get_today_usage(p)
    assert tokens == 1000 + 500 + 200 + 100 + 2000 + 300  # 4100
    assert abs(cost - 0.20) < 0.001
    assert model == 'glm-5.2'  # 最近一条（created_at 相同时按插入顺序，model 取最后插入）

def test_empty_db(tmp_path):
    p = str(tmp_path / "t.db")
    db = _make_db(p); db.commit(); db.close()
    assert get_today_usage(p) == (0, 0.0, None)

def test_missing_db(tmp_path):
    p = str(tmp_path / "nope.db")
    assert get_today_usage(p) == (0, 0.0, None)

def test_missing_table(tmp_path):
    p = str(tmp_path / "empty.db")
    sqlite3.connect(p).close()  # 建空库无表
    assert get_today_usage(p) == (0, 0.0, None)