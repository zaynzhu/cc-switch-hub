import sqlite3

def get_today_usage(db_path):
    """返回 (total_tokens, total_cost_usd, last_model)。
    db 不存在/表缺失/无数据时返回 (0, 0.0, None)。"""
    try:
        db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    except sqlite3.OperationalError:
        return (0, 0.0, None)
    try:
        row = db.execute("""
            SELECT COALESCE(SUM(input_tokens+output_tokens+cache_read_tokens+cache_creation_tokens),0),
                   COALESCE(ROUND(SUM(total_cost_usd),4),0)
              FROM proxy_request_logs
             WHERE date(created_at,'unixepoch','localtime')=date('now','localtime')
        """).fetchone()
        last = db.execute("""
            SELECT model FROM proxy_request_logs
             ORDER BY created_at DESC, rowid DESC LIMIT 1
        """).fetchone()
    except sqlite3.OperationalError:
        return (0, 0.0, None)
    finally:
        db.close()
    return (int(row[0]), float(row[1]), last[0] if last else None)