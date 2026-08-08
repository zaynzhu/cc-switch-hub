import sqlite3, json, urllib.request
from datetime import datetime, timezone

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

def get_current_provider(db_path, settings_path):
    """读当前激活厂商，返回 (base_url, api_key, name) 或 None。
    首选 settings.json 的 currentProviderClaude（id）→ db 查；兜底 db is_current。"""
    provider_id = None
    try:
        with open(settings_path, encoding='utf-8') as f:
            provider_id = json.load(f).get('currentProviderClaude')
    except (OSError, json.JSONDecodeError):
        provider_id = None
    try:
        db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        row = None
        if provider_id:
            row = db.execute(
                "SELECT settings_config, name FROM providers WHERE id=? AND app_type='claude'",
                (provider_id,)).fetchone()
        if not row:
            row = db.execute(
                "SELECT settings_config, name FROM providers WHERE is_current=1 AND app_type='claude'"
            ).fetchone()
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
    return (base.rstrip('/'), token, row[1])


def detect_provider_type(base_url):
    """按 base_url 子串判断厂商类型：'kimi' | 'zhipu' | None。"""
    if not base_url:
        return None
    u = base_url.lower()
    if 'api.kimi.com/coding' in u:
        return 'kimi'
    if 'open.bigmodel.cn' in u or 'bigmodel.cn' in u or 'api.z.ai' in u:
        return 'zhipu'
    return None


def _ms_to_iso(ms):
    """毫秒时间戳 → ISO 字符串；无效返回 None。"""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError, TypeError):
        return None


def _none_tier():
    return {'used': None, 'limit': None, 'reset': None}


def fetch_zhipu_quota(base_url, api_key, timeout=15):
    """智谱 GLM 套餐额度。返回 {'h5':{...},'weekly':{...}} 或 None。
    注意：Authorization 不加 Bearer 前缀（智谱特殊）。复刻自 cc-switch coding_plan.rs。"""
    zhipu_base = 'https://api.z.ai' if 'api.z.ai' in base_url.lower() else 'https://open.bigmodel.cn'
    url = zhipu_base + '/api/monitor/usage/quota/limit'
    req = urllib.request.Request(url, headers={
        'Authorization': api_key,
        'Content-Type': 'application/json',
        'Accept-Language': 'en-US,en',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
    except Exception:
        return None
    data = body.get('data')
    if not isinstance(data, dict):
        return None
    limits = data.get('limits')
    if not isinstance(limits, list):
        return None
    h5 = _none_tier()
    weekly = _none_tier()
    found = False
    for item in limits:
        if not isinstance(item, dict):
            continue
        if str(item.get('type', '')).upper() != 'TOKENS_LIMIT':
            continue
        pct = item.get('percentage')
        used_val = int(pct) if isinstance(pct, (int, float)) and not isinstance(pct, bool) else None
        entry = {
            'used': used_val,
            'limit': 100 if used_val is not None else None,
            'reset': _ms_to_iso(item.get('nextResetTime')),
        }
        unit = item.get('unit')
        if unit == 3 and h5['used'] is None:
            h5 = entry
            found = True
        elif unit == 6 and weekly['used'] is None:
            weekly = entry
            found = True
    if not found:
        return None
    return {'h5': h5, 'weekly': weekly}


def fetch_quota(base_url, api_key, timeout=10):
    """统一入口：按 detect 结果分发到对应厂商查询；不识别返回 None。"""
    ptype = detect_provider_type(base_url)
    if ptype == 'kimi':
        return fetch_kimi_quota(base_url, api_key, timeout)
    if ptype == 'zhipu':
        return fetch_zhipu_quota(base_url, api_key, timeout)
    return None