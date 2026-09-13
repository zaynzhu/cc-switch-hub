# src/mac_text.py
"""Mac 菜单栏用量条的纯函数：title 文本、进度环比例、菜单详情。
不依赖 rumps/AppKit，可在 Windows 单测。"""
from display_text import format_tokens, format_cost, format_quota, format_reset


def build_title(total_tokens, total_cost, h5_used, h5_limit, weekly_used, weekly_limit):
    """菜单栏同时显示五小时、周额度，避免只看见单个窗口。"""
    tok = format_tokens(total_tokens)
    cost = format_cost(total_cost)
    h5 = format_quota(h5_used, h5_limit)  # 无额度返回 '--'
    weekly = format_quota(weekly_used, weekly_limit)
    return f'{tok} {cost} · 5h {h5} · 周 {weekly}'


def ring_ratio(used, limit):
    """5h 额度使用比例 0-1，超限封顶 1.0；无额度返回 None。"""
    if used is None or limit is None or limit == 0:
        return None
    return min(used / limit, 1.0)


def build_menu_items(total_tokens, total_cost, last_model, quota, stale):
    """菜单详情行列表。无额度时只返回用量三行。"""
    items = [
        f'今日: {format_tokens(total_tokens)} tok',
        f'花费: {format_cost(total_cost)}',
        f'近用: {last_model or "--"}',
    ]
    if quota:
        h5 = quota['h5']
        wk = quota['weekly']
        items.append(
            f"5h: {format_quota(h5['used'], h5['limit'])} 重置 {format_reset(h5['reset'])}")
        items.append(
            f"周: {format_quota(wk['used'], wk['limit'])} 重置 {format_reset(wk['reset'])}")
        if stale:
            items.append('(额度数据已过期)')
    return items
