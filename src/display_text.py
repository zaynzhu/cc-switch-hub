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