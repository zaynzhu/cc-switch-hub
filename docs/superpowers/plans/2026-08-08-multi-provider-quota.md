# 多厂商额度跟随 + 细节打磨 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 额度从"固定查 Kimi"重构为"跟随 cc-switch 当前激活厂商"，支持 Kimi + 智谱 GLM；并修终审遗留的三项细节问题（托盘图标兜底、退出线程竞态、测试边界+代码清理）。

**Architecture:** 重构 `quota_fetcher`：新增 `get_current_provider`（settings.json 权威读当前厂商）、`detect_provider_type`（base_url 子串判断 kimi/zhipu）、`fetch_zhipu_quota`（复刻 cc-switch），统一入口 `fetch_quota` 分发；`main.py` 改用新接口并加托盘图标兜底与退出竞态处理；widget 不变（兼容统一返回格式）。

**Tech Stack:** Python 3.12（tool python，`E:/program/tool/python/python.exe`）、PySide6、sqlite3、urllib、json、datetime、pytest

## Global Constraints

- Python 解释器固定 tool python：`"E:/program/tool/python/python.exe"`；测试命令 `"E:/program/tool/python/python.exe" -m pytest tests/<file> -v`
- cc-switch db 只读连接 `file:{path}?mode=ro` uri=True；settings.json 路径 `~/.cc-switch/settings.json`
- 当前激活厂商权威来源：`settings.json` 的 `currentProviderClaude`（id）→ db `providers` 查；兜底 db `is_current=1`
- 智谱接口 **Authorization 不加 Bearer 前缀**（特殊）；Kimi 加 Bearer
- 统一返回格式 `{'h5':{used,limit,reset},'weekly':{used,limit,reset}}`，used/limit 为百分比语义（0-100），缺窗口用 `{'used':None,'limit':None,'reset':None}`
- 智谱接口复刻自 cc-switch `coding_plan.rs`，**无法实测**（无智谱 key），用 mock 单测验证解析
- 不识别厂商 / 查询失败 → 返回 None（走现有 stale 变灰 / `--` 逻辑）
- commit 格式 `type: 中文描述`，user.name zaynzhu
- 现有 20 个测试必须保持通过（回归）

---

### Task 1: quota_fetcher 重构（detect + get_current_provider + zhipu + 统一入口）

**Files:**
- Modify: `src/quota_fetcher.py`
- Test: `tests/test_quota_fetcher.py`

**Interfaces:**
- Consumes: 现有 `fetch_kimi_quota(base_url, token, timeout=10)`
- Produces:
  - `get_current_provider(db_path, settings_path) -> (base_url:str, api_key:str, name:str) | None`
  - `detect_provider_type(base_url) -> 'kimi' | 'zhipu' | None`
  - `fetch_zhipu_quota(base_url, api_key, timeout=15) -> {'h5':{...},'weekly':{...}} | None`
  - `fetch_quota(base_url, api_key, timeout=10) -> {'h5':{...},'weekly':{...}} | None`（统一入口，detect 分发）

- [ ] **Step 1: 追加失败测试到 `tests/test_quota_fetcher.py`**

在现有测试文件末尾追加（保留现有 5 个测试不动）：

```python
import os
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_quota_fetcher.py -v`
Expected: 新测试 FAIL（`ImportError: cannot import name 'get_current_provider'`）

- [ ] **Step 3: 重构 `src/quota_fetcher.py`**

在文件顶部 import 处加 `from datetime import datetime, timezone`。保留现有 `get_kimi_config` 与 `fetch_kimi_quota` 不变。追加：

```python
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
        entry = {
            'used': int(pct) if pct is not None else None,
            'limit': 100 if pct is not None else None,
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
```

注意：`fetch_kimi_quota` 现有返回格式是 `{'weekly':{...},'h5':{...}}`，与新统一格式兼容（键相同）。

- [ ] **Step 4: 跑测试确认通过**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/test_quota_fetcher.py -v`
Expected: 全部通过（原 5 + 新 9 = 14）

- [ ] **Step 5: 真实 db 冒烟验证当前厂商读取**

Run: `PYTHONPATH=src "E:/program/tool/python/python.exe" -X utf8 -c "from quota_fetcher import get_current_provider, detect_provider_type; p=get_current_provider('C:/Users/OMEN/.cc-switch/cc-switch.db','C:/Users/OMEN/.cc-switch/settings.json'); print(p[0], p[2] if p else None); print('type:', detect_provider_type(p[0]) if p else None)"`
Expected: 输出 Kimi base_url、name、"type: kimi"（当前激活是 Kimi）

- [ ] **Step 6: 跑全套回归**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/ -v`
Expected: 全部通过（20 + 9 = 29）

- [ ] **Step 7: Commit**

```bash
git add src/quota_fetcher.py tests/test_quota_fetcher.py
git commit -m "feat: quota_fetcher 重构支持多厂商额度跟随"
```

---

### Task 2: main.py 集成（新额度接口 + 托盘图标兜底 + 退出竞态）

**Files:**
- Modify: `src/main.py`

**Interfaces:**
- Consumes: `get_current_provider`、`fetch_quota` from quota_fetcher；`_workers`（现有）
- Produces: refresh_quota 改用新接口；托盘纯色图标；aboutToQuit 等线程

- [ ] **Step 1: 修改 `src/main.py`**

import 处：`from quota_fetcher import get_kimi_config, fetch_kimi_quota` 改为 `from quota_fetcher import get_current_provider, fetch_quota`。确保 import 区有 `from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor`。

在 `DB_PATH = ...` 下加：
```python
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
```

`QuotaWorker.run` 改为：
```python
    def run(self):
        prov = get_current_provider(DB_PATH, SETTINGS_JSON_PATH)
        if not prov:
            self.fetched.emit(None)
            return
        base, token, _name = prov
        self.fetched.emit(fetch_quota(base, token))
```

加托盘图标生成函数（模块级，main() 之前）：
```python
def _make_tray_icon():
    """程序生成纯色托盘图标，不依赖系统图标主题（Windows 无主题时 fromTheme 返回空白）。"""
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor('#e0a030'))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, 16, 16, 4, 4)
    p.end()
    return QIcon(pix)
```

main() 里 `tray.setIcon(QIcon.fromTheme('dialog-information'))` 改为 `tray.setIcon(_make_tray_icon())`。

退出竞态处理：在 `app.exec()` 之前加：
```python
    def _on_quit():
        for w in list(_workers):
            w.wait(2000)
    app.aboutToQuit.connect(_on_quit)
```

（注：`Qt` 此前被终审标记为 unused import，现在 `_make_tray_icon` 用了 `Qt.transparent`/`Qt.NoPen`，该 import 变为必要，保留。）

- [ ] **Step 2: 启动验证（不崩 + 额度跟随当前厂商）**

后台启动 ~10 秒确认存活、额度查询走当前厂商（Kimi）：
`"E:/program/tool/python/python.exe" -X utf8 src/main.py > /tmp/cc-hub-t2.log 2>&1 & PID=$!; sleep 10; if kill -0 $PID 2>/dev/null; then echo "STILL RUNNING OK"; kill $PID; else echo "CRASHED"; cat /tmp/cc-hub-t2.log; fi`
Expected: STILL RUNNING OK，无 traceback

- [ ] **Step 3: 跑全套回归**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/ -v`
Expected: 29 passed（main.py 无单测，回归不破）

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: main 集成多厂商额度跟随并加托盘图标兜底与退出竞态处理"
```

---

### Task 3: 细节打磨（测试边界 + 代码清理）

**Files:**
- Modify: `tests/test_display_text.py`, `tests/test_widget.py`, `src/main.py`

**Interfaces:**
- Consumes: 现有 display_text 函数、widget、main

- [ ] **Step 1: 补 display_text 测试边界**

在 `tests/test_display_text.py` 的 `test_format_tokens` 和 `test_quota_color` 等现有函数里补充边界断言（在对应函数内追加 assert，不新建函数）：

在 `test_format_tokens` 末尾追加：
```python
    assert format_tokens(1000) == '1.0K'
```

在 `test_format_quota` 末尾追加：
```python
    assert format_quota(None, 100) == '--'
    assert format_quota(68, None) == '--'
```

在 `test_quota_color` 末尾追加：
```python
    assert quota_color(68, 0) == 'normal'
    assert quota_color(None, 100) == 'normal'
```

- [ ] **Step 2: 清理 test_widget.py 的 unused import**

`tests/test_widget.py` 顶部 `from PySide6.QtWidgets import QApplication` 未使用（qapp fixture 在 conftest.py）→ 删除该行。

- [ ] **Step 3: save_settings 加 OSError 兜底**

`src/main.py` 的 `save_settings` 函数：
```python
def save_settings(pos):
    try:
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump({'x': pos.x(), 'y': pos.y()}, f)
    except OSError:
        pass
```

- [ ] **Step 4: 跑全套确认**

Run: `"E:/program/tool/python/python.exe" -m pytest tests/ -v`
Expected: 全部通过（新增断言不破）

- [ ] **Step 5: Commit**

```bash
git add tests/test_display_text.py tests/test_widget.py src/main.py
git commit -m "test: 补测试边界并清理代码细节"
```

---

## 验收标准

1. `"E:/program/tool/python/python.exe" -m pytest tests/ -v` 全部通过（29 + 新增断言）
2. `src/main.py` 启动后窄条额度跟随当前激活厂商（当前 Kimi → 显示 Kimi 5h/周额度）
3. 托盘图标为程序生成的色块（不空白）
4. 切换 cc-switch 厂商到智谱 GLM 后（若有），窄条额度下次刷新跟随显示（本阶段无法实测智谱，靠 mock 单测保证解析正确）
5. 切到 ollama 等非内置厂商 → 额度显示 `--`
6. 退出应用无 `QThread destroyed while running` 警告

## 不做（YAGNI）

- MiniMax / ZenMux / 火山方舟接口
- 第三方余额查询（DeepSeek/SiliconFlow 等）
- 多厂商同时显示（只跟随当前激活厂商）
- 自定义 js 脚本引擎