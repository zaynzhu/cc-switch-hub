# cc-switch-hub 任务栏用量条 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做一个 Win11 任务栏上的常驻窄条，复用 cc-switch 本地数据库与 Kimi 额度接口，零点击显示今日 token 用量、花费、近用模型、Kimi 套餐额度。

**Architecture:** 单 Python 进程（PySide6），四个职责分离的模块：`usage_reader` 只读聚合 db 今日用量、`quota_fetcher` 读 Kimi 配置并查额度接口、`display_text` 纯函数格式化显示文本、`widget`+`main` 负责 GUI 与调度。用量全部汇总（db 明细不带厂商标识），额度固定查 Kimi。

**Tech Stack:** Python 3.12（tool python，`E:/program/tool/python/python.exe`）、PySide6、sqlite3（标准库）、urllib（标准库）、pytest 9.0.3

## Global Constraints

- Python 解释器固定用 tool python：`E:/program/tool/python/python.exe`（3.12.8，独立发行版）。anaconda 的 `Library/bin/msvcp140.dll`（14.29/VS2019）与 PySide6 所需 14.44/VS2022 DLL 冲突，`PySide6.QtWidgets` 在 anaconda 无法加载；tool python 无此污染，PySide6 已验证可用
- pip 装进 tool python：`"E:/program/tool/python/python.exe" -m pip install <pkg>`
- 测试命令统一：`"E:/program/tool/python/python.exe" -m pytest tests/<file> -v`
- cc-switch 数据库路径：`C:\Users\OMEN\.cc-switch\cc-switch.db`（只读连接，`mode=ro` + uri）
- 代码风格：JS 不分号规则不适用（本计划是 Python），但保持 2 空格缩进改为 4 空格（Python 规范），camelCase 改为 snake_case（Python 规范）
- 额度接口固定 Kimi：`name='Kimi For Coding' AND app_type='claude'`，不随当前激活厂商变化
- 今日用量全部汇总：`proxy_request_logs` 的 `provider_id` 是占位值 `'_session'`，不可用于按厂商过滤
- 今日过滤按本地时区：`date(created_at,'unixepoch','localtime')=date('now','localtime')`
- commit 信息格式：`type: 中文描述`，署名 `git config user.name zaynzhu`（不指定邮箱）

---

## File Structure

| 文件 | 职责 | 接口产出 |
|---|---|---|
| `conftest.py` | 把 `src/` 加入 sys.path，供测试 import | — |
| `.gitignore` | 忽略 `__pycache__`、`settings.json` | — |
| `src/usage_reader.py` | 只读 db，全部汇总今日 token/花费，取最近 model | `get_today_usage(db_path) -> (int, float, str\|None)` |
| `src/quota_fetcher.py` | 按 name 读 Kimi 配置；查额度接口并解析 | `get_kimi_config(db_path) -> (base_url, token)\|None`、`fetch_kimi_quota(base_url, token) -> dict\|None` |
| `src/display_text.py` | 纯函数：格式化 token/cost/quota、组装显示行、额度颜色阈值 | `build_display_text(...)`、`quota_color(...)` |
| `src/widget.py` | 无边框置顶窄条窗口，绘制文本、拖动 | `UsageWidget` 类 |
| `src/main.py` | 启动、30s/5min 定时刷新、托盘退出、位置记忆 | — |
| `tests/test_usage_reader.py` | usage_reader 单测 | — |
| `tests/test_quota_fetcher.py` | quota_fetcher 单测 | — |
| `tests/test_display_text.py` | display_text 单测 | — |
| `settings.json` | 运行时生成，记忆窗口位置（不提交） | — |

---

### Task 1: 项目骨架 + usage_reader

**Files:**
- Create: `conftest.py`, `.gitignore`, `src/usage_reader.py`, `tests/test_usage_reader.py`

**Interfaces:**
- Produces: `get_today_usage(db_path) -> (total_tokens:int, total_cost_usd:float, last_model:str|None)`。db 不存在/表缺失/无数据时返回 `(0, 0.0, None)`

- [ ] **Step 1: 初始化 git + 目录结构 + .gitignore + conftest**

```bash
cd /e/codex/cc-switch-hub
git init
git config user.name zaynzhu
mkdir -p src tests
```

`.gitignore`:
```
__pycache__/
*.pyc
settings.json
.pytest_cache/
```

`conftest.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
```

- [ ] **Step 2: 安装 PySide6 到 anaconda**

Run: `E:/program/anaconda3/python.exe -m pip install PySide6`
Expected: 安装成功，`E:/program/anaconda3/python.exe -c "import PySide6; print(PySide6.__version__)"` 输出版本号

- [ ] **Step 3: 写失败测试 `tests/test_usage_reader.py`**

```python
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
    assert tokens == 1000 + 500 + 200 + 300 + 200 + 100  # 3800
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
```

- [ ] **Step 4: 跑测试确认失败**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_usage_reader.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'usage_reader'`

- [ ] **Step 5: 写 `src/usage_reader.py`**

```python
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
             ORDER BY created_at DESC LIMIT 1
        """).fetchone()
    except sqlite3.OperationalError:
        return (0, 0.0, None)
    finally:
        db.close()
    return (int(row[0]), float(row[1]), last[0] if last else None)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_usage_reader.py -v`
Expected: 4 passed

- [ ] **Step 7: 用真实 db 冒烟验证**

Run: `E:/program/anaconda3/python.exe -X utf8 -c "from usage_reader import get_today_usage; print(get_today_usage('C:/Users/OMEN/.cc-switch/cc-switch.db'))"`
Expected: 输出形如 `(69411491, 60.73, 'kimi-k3')`，数字非 0

- [ ] **Step 8: Commit**

```bash
git add conftest.py .gitignore src/usage_reader.py tests/test_usage_reader.py
git commit -m "feat: 添加 usage_reader 读取今日用量汇总"
```

---

### Task 2: quota_fetcher

**Files:**
- Create: `src/quota_fetcher.py`, `tests/test_quota_fetcher.py`

**Interfaces:**
- Consumes: 无（独立模块）
- Produces: `get_kimi_config(db_path) -> (base_url:str, token:str) | None`；`fetch_kimi_quota(base_url, token, timeout=10) -> {'weekly':{'used','limit','reset'}, 'h5':{'used','limit','reset'}} | None`

- [ ] **Step 1: 写失败测试 `tests/test_quota_fetcher.py`**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_quota_fetcher.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'quota_fetcher'`

- [ ] **Step 3: 写 `src/quota_fetcher.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_quota_fetcher.py -v`
Expected: 4 passed

- [ ] **Step 5: 用真实 db 冒烟验证**

Run: `E:/program/anaconda3/python.exe -X utf8 -c "from quota_fetcher import get_kimi_config, fetch_kimi_quota; cfg=get_kimi_config('C:/Users/OMEN/.cc-switch/cc-switch.db'); print(cfg[0] if cfg else None); print(fetch_kimi_quota(*cfg) if cfg else None)"`
Expected: 输出 base_url 与额度 dict（weekly/h5 used/limit 非 None）

- [ ] **Step 6: Commit**

```bash
git add src/quota_fetcher.py tests/test_quota_fetcher.py
git commit -m "feat: 添加 quota_fetcher 查询 Kimi 套餐额度"
```

---

### Task 3: display_text 格式化纯函数

**Files:**
- Create: `src/display_text.py`, `tests/test_display_text.py`

**Interfaces:**
- Consumes: 无
- Produces: `format_tokens(n)->str`、`format_cost(usd)->str`、`format_quota(used,limit)->str`、`quota_color(used,limit)->str`、`build_display_text(total_tokens,total_cost,last_model,quota)->str`。`quota` 形如 `{'h5':{'used','limit','reset'},'weekly':{'used','limit','reset'}}` 或 `None`

- [ ] **Step 1: 写失败测试 `tests/test_display_text.py`**

```python
from display_text import (format_tokens, format_cost, format_quota,
                          quota_color, build_display_text)

def test_format_tokens():
    assert format_tokens(0) == '0'
    assert format_tokens(500) == '500'
    assert format_tokens(1280) == '1.3K'
    assert format_tokens(1000000) == '1.0M'
    assert format_tokens(2100000) == '2.1M'
    assert format_tokens(69411491) == '69.4M'

def test_format_cost():
    assert format_cost(0.0) == '$0.00'
    assert format_cost(0.832) == '$0.83'
    assert format_cost(60.732) == '$60.73'

def test_format_quota():
    assert format_quota(68, 100) == '68%'
    assert format_quota(78, 100) == '78%'
    assert format_quota(None, None) == '--'
    assert format_quota(68, 0) == '--'

def test_quota_color():
    assert quota_color(78, 100) == 'normal'
    assert quota_color(80, 100) == 'orange'
    assert quota_color(94, 100) == 'orange'
    assert quota_color(95, 100) == 'red'
    assert quota_color(None, None) == 'normal'

def test_build_display_text_with_quota():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
         'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}}
    assert build_display_text(69411491, 60.732, 'kimi-k3', q) == \
        '今日 69.4M tok · $60.73 · 近用 kimi-k3 | 5h 78% · 周 68%'

def test_build_display_text_without_quota():
    assert build_display_text(2100000, 0.83, 'glm-5.2', None) == \
        '今日 2.1M tok · $0.83 · 近用 glm-5.2'

def test_build_display_text_no_model():
    assert build_display_text(0, 0.0, None, None) == \
        '今日 0 tok · $0.00 · 近用 --'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_display_text.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'display_text'`

- [ ] **Step 3: 写 `src/display_text.py`**

```python
def format_tokens(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.1f}K'
    return str(n)

def format_cost(usd):
    return f'${usd:.2f}'

def format_quota(used, limit):
    if used is None or limit is None or limit == 0:
        return '--'
    return f'{round(used * 100 / limit)}%'

def quota_color(used, limit):
    if used is None or limit is None or limit == 0:
        return 'normal'
    pct = used * 100 / limit
    if pct >= 95:
        return 'red'
    if pct >= 80:
        return 'orange'
    return 'normal'

def build_display_text(total_tokens, total_cost, last_model, quota):
    tok = format_tokens(total_tokens)
    cost = format_cost(total_cost)
    model = last_model or '--'
    if quota:
        h5 = format_quota(quota['h5']['used'], quota['h5']['limit'])
        wk = format_quota(quota['weekly']['used'], quota['weekly']['limit'])
        return f'今日 {tok} tok · {cost} · 近用 {model} | 5h {h5} · 周 {wk}'
    return f'今日 {tok} tok · {cost} · 近用 {model}'
```

- [ ] **Step 4: 跑测试确认通过**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_display_text.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/display_text.py tests/test_display_text.py
git commit -m "feat: 添加 display_text 格式化显示文本"
```

---

### Task 4: widget GUI 窗口

**Files:**
- Create: `src/widget.py`, `tests/test_widget.py`

**Interfaces:**
- Consumes: `build_display_text`、`quota_color` from `display_text`
- Produces: `UsageWidget(QWidget)`，方法 `update_data(usage:tuple, quota:dict|None)`，其中 `usage=(total_tokens, total_cost, last_model)`

- [ ] **Step 1: 写冒烟测试 `tests/test_widget.py`**

```python
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from widget import UsageWidget

def test_widget_update_data(qapp):
    w = UsageWidget()
    w.update_data((69411491, 60.732, 'kimi-k3'),
                  {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
                   'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}})
    assert '69.4M' in w._label.text()
    # 无额度时不崩
    w.update_data((0, 0.0, None), None)
    assert '近用 --' in w._label.text()
```

`tests/conftest.py`（提供 qapp fixture）:
```python
import os, pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

@pytest.fixture(scope='session')
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: 跑测试确认失败**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_widget.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'widget'`

- [ ] **Step 3: 写 `src/widget.py`**

```python
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal
from display_text import build_display_text, quota_color

COLORS = {
    'normal': '#d4d4d4',
    'orange': '#e0a030',
    'red': '#e05050',
    'grey': '#888888',
}

class UsageWidget(QWidget):
    moved = Signal()  # 拖动结束时发出，供 main 保存位置

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._usage = (0, 0.0, None)
        self._quota = None
        self._stale = False  # 额度数据是否过期（接口失败但曾有数据）
        self._drag_pos = None

        self._label = QLabel(self)
        self._set_color('normal')
        self._label.setText('今日 -- tok · $-- · 近用 --')
        self._label.adjustSize()
        self.adjustSize()

    def _set_color(self, color_key):
        """重建完整样式表，避免 replace 找不到目标色的问题。"""
        color = COLORS[color_key]
        self._label.setStyleSheet(
            f"QLabel{{font-family:'Microsoft YaHei';font-size:12px;"
            f"color:{color};background-color:rgba(30,30,30,220);"
            f"padding:4px 8px;border-radius:3px;}}")

    def update_data(self, usage, quota):
        self._usage = usage
        if quota is not None:
            self._quota = quota
            self._stale = False
        elif self._quota is not None:
            # 接口失败但曾有数据：保留上次，标记过期
            self._stale = True
        # 从未拿到额度时 self._quota 保持 None

        text = build_display_text(usage[0], usage[1], usage[2], self._quota)
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

        # tooltip 完整数字
        tip = (f"今日: {usage[0]} tok / {usage[1]:.4f} USD\n"
               f"近用模型: {usage[2] or '--'}")
        if self._quota:
            tip += (f"\n5h: {self._quota['h5']['used']}/{self._quota['h5']['limit']} "
                    f"重置 {self._quota['h5']['reset']}\n"
                    f"周: {self._quota['weekly']['used']}/{self._quota['weekly']['limit']} "
                    f"重置 {self._quota['weekly']['reset']}")
            if self._stale:
                tip += '\n(额度数据已过期)'
        self._label.setToolTip(tip)

        # 额度颜色：过期变灰，否则取 5h 与周额度较高档
        if self._stale:
            self._set_color('grey')
        elif self._quota:
            c5 = quota_color(self._quota['h5']['used'], self._quota['h5']['limit'])
            cw = quota_color(self._quota['weekly']['used'], self._quota['weekly']['limit'])
            rank = {'normal': 0, 'orange': 1, 'red': 2}
            self._set_color(max([c5, cw], key=lambda c: rank[c]))
        else:
            self._set_color('normal')

    # 拖动
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()
            e.accept()
    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
    def mouseReleaseEvent(self, e):
        if self._drag_pos is not None:
            self._drag_pos = None
            self.moved.emit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `E:/program/anaconda3/python.exe -m pytest tests/test_widget.py -v`
Expected: 1 passed

- [ ] **Step 5: 手动验证窗口外观**

Run: `E:/program/anaconda3/python.exe -X utf8 -c "
import sys, os
os.environ.setdefault('QT_QPA_PLATFORM','windows')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from widget import UsageWidget
app = QApplication([])
w = UsageWidget()
w.update_data((69411491, 60.732, 'kimi-k3'), {'h5':{'used':78,'limit':100,'reset':'t'},'weekly':{'used':68,'limit':100,'reset':'t'}})
w.move(1200, 700); w.show()
QTimer.singleShot(8000, app.quit)
app.exec()
"`
Expected: 屏幕上出现一个深色窄条显示「今日 69.4M tok · $60.73 · 近用 kimi-k3 | 5h 78% · 周 68%」，8 秒后自动关闭，鼠标可拖动

- [ ] **Step 6: Commit**

```bash
git add src/widget.py tests/test_widget.py tests/conftest.py
git commit -m "feat: 添加任务栏窄条窗口 widget"
```

---

### Task 5: main 调度 + 托盘 + 位置记忆

**Files:**
- Create: `src/main.py`

**Interfaces:**
- Consumes: `get_today_usage`、`get_kimi_config`+`fetch_kimi_quota`、`UsageWidget`

- [ ] **Step 1: 写 `src/main.py`**

```python
import sys, os, json
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer, Qt, QThread, Signal

from usage_reader import get_today_usage
from quota_fetcher import get_kimi_config, fetch_kimi_quota
from widget import UsageWidget

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
USAGE_INTERVAL = 30 * 1000      # 30 秒
QUOTA_INTERVAL = 5 * 60 * 1000  # 5 分钟


class QuotaWorker(QThread):
    fetched = Signal(object)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        cfg = get_kimi_config(self.db_path)
        if not cfg:
            self.fetched.emit(None)
            return
        self.fetched.emit(fetch_kimi_quota(*cfg))


def load_settings():
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(pos):
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump({'x': pos.x(), 'y': pos.y()}, f)


def place_default(widget):
    """放到屏幕右下角（任务栏上方）。"""
    screen = QApplication.primaryScreen()
    geo = screen.availableGeometry()
    widget.move(geo.right() - widget.width() - 8,
                geo.bottom() - widget.height() - 4)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    widget = UsageWidget()
    widget.show()

    # 恢复位置
    st = load_settings()
    if 'x' in st and 'y' in st:
        widget.move(st['x'], st['y'])
    else:
        place_default(widget)
    # 拖动结束记忆位置
    widget.moved.connect(lambda: save_settings(widget.pos()))

    def refresh_usage():
        widget.update_data(get_today_usage(DB_PATH), widget._quota)

    def refresh_quota():
        worker = QuotaWorker(DB_PATH)
        worker.fetched.connect(
            lambda q: widget.update_data(widget._usage, q))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    usage_timer = QTimer()
    usage_timer.timeout.connect(refresh_usage)
    usage_timer.start(USAGE_INTERVAL)
    quota_timer = QTimer()
    quota_timer.timeout.connect(refresh_quota)
    quota_timer.start(QUOTA_INTERVAL)
    refresh_usage()
    refresh_quota()

    # 托盘
    tray = QSystemTrayIcon()
    tray.setIcon(QIcon.fromTheme('dialog-information'))
    tray.setToolTip('cc-switch 用量条')
    menu = QMenu()
    act_refresh = QAction('立即刷新')
    act_refresh.triggered.connect(lambda: (refresh_usage(), refresh_quota()))
    menu.addAction(act_refresh)
    act_quit = QAction('退出')
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.show()

    app.exec()


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 手动运行验证**

Run: `E:/program/anaconda3/python.exe -X utf8 src/main.py`
Expected: 右下角任务栏上方出现窄条，显示真实今日用量与 Kimi 额度；30 秒后用量刷新；右键托盘图标可「立即刷新」「退出」；拖动窄条换位置后退出再启动，位置被记住

- [ ] **Step 3: 调整窄条位置（手动）**

启动后如果窄条位置不理想（被任务栏遮挡 / 离边缘太远），手动拖到合适位置，工具会记忆。若 `place_default` 计算偏差过大，回到 `src/main.py:place_default` 微调 `-8`/`-4` 偏移量。

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: 添加 main 调度托盘与位置记忆"
```

---

### Task 6: 开机自启（可选，验证满意后）

**Files:**
- Create: 启动文件夹快捷方式（不进 git）

- [ ] **Step 1: 创建开机自启快捷方式**

在 PowerShell 执行（用户自行）：
```powershell
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\cc-switch-hub.lnk")
$lnk.TargetPath = "E:\program\tool\python\pythonw.exe"
$lnk.Arguments = "E:\codex\cc-switch-hub\src\main.py"
$lnk.WorkingDirectory = "E:\codex\cc-switch-hub"
$lnk.Save()
```
Expected: 重启后窄条自动出现（pythonw 无控制台窗口）

- [ ] **Step 2: 验证自启**

重启 Windows，确认窄条自动出现、数据正确

- [ ] **Step 3: 记录到 README（可选）**

如需归档，把上述快捷方式脚本写进 `README.md` 的「开机自启」一节。本步不强制 commit。

---

## 验收标准

1. `"E:/program/tool/python/python.exe" -m pytest tests/ -v` 全部通过（usage_reader 5 + quota_fetcher 5 + display_text 7 + widget 2 = 19 项）
2. `pythonw src/main.py` 启动后，右下角出现窄条，显示形如「今日 69.4M tok · $60.73 · 近用 kimi-k3 | 5h 78% · 周 68%」
3. 窄条数据与 cc-switch 托盘点开看到的数字一致（今日 token、花费、Kimi 周额度）
4. 关闭 cc-switch 后窄条不崩（db 只读连接，显示上次值）
5. 拖动位置后重启，位置被记住

## 不做（YAGNI）

- 不支持多厂商额度接口（v1 只 Kimi）
- 不做 PyInstaller 打包（后续按需）
- 不做历史曲线/图表
- 不写回 cc-switch 的数据库
- 不做真正的 Shell 任务栏嵌入（用置顶无边框窗口近似）