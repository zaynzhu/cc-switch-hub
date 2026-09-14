import sqlite3, json, urllib.request
from datetime import datetime, timezone, timedelta
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit


class RateLimiter:
    """同一服务两秒内只放行一次，避免手动刷新并发请求。"""

    def __init__(self):
        self._lock = Lock()
        self._last_request = float('-inf')

    def acquire(self):
        with self._lock:
            now = monotonic()
            if now - self._last_request < 2:
                return False
            self._last_request = now
            return True


_OLLAMA_RATE_LIMITER = RateLimiter()

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
                       'reset': weekly['resetTime'], 'reset_source': 'api'},
            'h5': {'used': int(h5['used']), 'limit': int(h5['limit']),
                   'reset': h5['resetTime'], 'reset_source': 'api'},
        }
    except (KeyError, StopIteration, ValueError, TypeError):
        return None

def get_current_provider(db_path, settings_path):
    """读当前激活厂商，返回 (base_url, api_key, name) 或 None。
    仅按 settings.json 的 currentProviderClaude（id）查，不回退 is_current。"""
    provider_id = None
    try:
        with open(settings_path, encoding='utf-8') as f:
            provider_id = json.load(f).get('currentProviderClaude')
    except (OSError, json.JSONDecodeError, AttributeError):
        provider_id = None
    if not isinstance(provider_id, str) or not provider_id:
        return None
    try:
        db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        row = db.execute(
            "SELECT settings_config, name FROM providers WHERE id=? AND app_type='claude'",
            (provider_id,)).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        db.close()
    if not row:
        return None
    try:
        env = json.loads(row[0]).get('env', {})
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None
    if not isinstance(env, dict):
        return None
    base = env.get('ANTHROPIC_BASE_URL')
    token = env.get('ANTHROPIC_AUTH_TOKEN')
    if not isinstance(base, str) or not isinstance(token, str) or not base or not token:
        return None
    return (base.rstrip('/'), token, row[1])


def detect_provider_type(base_url):
    """按 base_url 判断厂商类型：'kimi' | 'zhipu' | 'ollama' | None。"""
    if not base_url:
        return None
    u = base_url.lower()
    if 'api.kimi.com/coding' in u:
        return 'kimi'
    if 'open.bigmodel.cn' in u or 'bigmodel.cn' in u or 'api.z.ai' in u:
        return 'zhipu'
    try:
        if urlsplit(u if '://' in u else '//' + u).hostname == 'ollama.com':
            return 'ollama'
    except ValueError:
        pass
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
    return {'used': None, 'limit': None, 'reset': None, 'reset_source': None}


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
            'reset_source': 'api',
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


def next_ollama_weekly_reset(now_utc):
    """严格晚于 now 的下一个周一 00:00 UTC（timezone-aware UTC datetime）。

    已用真实 Ollama legacy 账号验证：UTC 周日满额后，北京时间周一 08:00
    （即 UTC 周一 00:00）查询 weekly.usage 已被刷新。
    接口本身不返回该时间，属客户端推算（reset_source='estimated'），
    显示层再转本机时区，不得在数据层写死北京时间。"""
    now = now_utc.astimezone(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    reset = midnight + timedelta(days=(7 - now.weekday()) % 7)
    if reset <= now:
        reset += timedelta(days=7)  # 恰在周一 00:00 UTC：当周窗口已开始，取下周
    return reset


def fetch_ollama_quota(api_key, timeout=10):
    """查询 Ollama Cloud legacy 未文档化接口，结构不符或失败返回 None。"""
    if not isinstance(api_key, str) or not api_key.strip():
        return None
    if not _OLLAMA_RATE_LIMITER.acquire():
        return None
    try:
        req = urllib.request.Request('https://ollama.com/api/usage', headers={
            'Authorization': 'Bearer ' + api_key,
        })
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode())
        session = data['limits']['session']['usage']
        weekly = data['limits']['weekly']['usage']
        for usage in (session, weekly):
            if (isinstance(usage, bool) or not isinstance(usage, (int, float))
                    or not 0 <= usage <= 1):
                return None
        return {
            # session 只给使用率不给窗口起点：reset 暂时保持未知，不做任何推算
            'h5': {'used': session * 100, 'limit': 100,
                   'reset': None, 'reset_source': None},
            'weekly': {'used': weekly * 100, 'limit': 100,
                       'reset': next_ollama_weekly_reset(
                           datetime.now(timezone.utc)).isoformat(),
                       'reset_source': 'estimated'},
        }
    except Exception:
        # 包含网络、HTTP、JSON 与接口结构变化；不记录凭据或异常内容。
        return None


def fetch_quota(base_url, api_key, timeout=10):
    """统一入口：按 detect 结果分发到对应厂商查询；不识别返回 None。"""
    ptype = detect_provider_type(base_url)
    if ptype == 'kimi':
        return fetch_kimi_quota(base_url, api_key, timeout)
    if ptype == 'zhipu':
        return fetch_zhipu_quota(base_url, api_key, timeout)
    if ptype == 'ollama':
        return fetch_ollama_quota(api_key, timeout)
    return None
