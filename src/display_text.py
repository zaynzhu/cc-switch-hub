from datetime import datetime, timedelta, timezone


def format_reset(value):
    """带时区的 API 时间转为北京时间；未知或已有说明的文本保持原意。"""
    if not value:
        return '--'
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return value
        beijing = parsed.astimezone(timezone(timedelta(hours=8)))
        return beijing.strftime('%Y-%m-%d %H:%M') + ' 北京时间'
    except (ValueError, TypeError, AttributeError):
        return value


def format_reset_line(reset, source=None):
    """详情行尾的重置片段，按来源区分口径：
    - source == 'estimated'（如 Ollama weekly）：'预计重置 <北京时间>（本地推算）'
    - source == 'api'（Kimi / 智谱真实返回）：'重置 <北京时间>'
    - reset 为 None：'重置 --'，未知不猜测
    """
    if not reset:
        return '重置 --'
    if source == 'estimated':
        return f'预计重置 {format_reset(reset)}（本地推算）'
    return f'重置 {format_reset(reset)}'


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
        return f'{tok} tok · {cost} · {model} · 5h {h5} · 周 {wk}'
    return f'{tok} tok · {cost} · {model}'
