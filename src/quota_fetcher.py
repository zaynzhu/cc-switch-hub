import sqlite3, json, urllib.request

def get_kimi_config(db_path):
    """按 name 读 Kimi For Coding 配置，返回 (base_url, token) 或 None。"""
    try:
        db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        row = db.execute("""
            SELECT settings_config FROM providers
             WHERE app_type='claude' AND name='Kimi For Coding'
        """).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        db.close()
    if not row:
        return None
    try:
        env = json.loads(row[0]).get('env', {})
    except (json.JSONDecodeError, TypeError):
        return None
    base = env.get('ANTHROPIC_BASE_URL')
    token = env.get('ANTHROPIC_AUTH_TOKEN')
    if not base or not token:
        return None
    return (base.rstrip('/'), token)

def fetch_kimi_quota(base_url, token, timeout=10):
    """查额度接口，返回 {'weekly':{...}, 'h5':{...}} 或 None（失败/解析失败）。"""
    req = urllib.request.Request(base_url + '/v1/usages',
                                 headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return None
    try:
        weekly = data['usage']
        h5 = next(l for l in data['limits']
                  if l['window']['duration'] == 300)['detail']
        return {
            'weekly': {'used': int(weekly['used']), 'limit': int(weekly['limit']),
                       'reset': weekly['resetTime']},
            'h5': {'used': int(h5['used']), 'limit': int(h5['limit']),
                   'reset': h5['resetTime']},
        }
    except (KeyError, StopIteration, ValueError, TypeError):
        return None