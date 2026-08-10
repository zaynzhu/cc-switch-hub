from display_text import (format_tokens, format_cost, format_quota,
                          quota_color, build_display_text)

def test_format_tokens():
    assert format_tokens(0) == '0'
    assert format_tokens(500) == '500'
    assert format_tokens(1280) == '1.3K'
    assert format_tokens(1000000) == '1.0M'
    assert format_tokens(2100000) == '2.1M'
    assert format_tokens(69411491) == '69.4M'
    assert format_tokens(1000) == '1.0K'

def test_format_cost():
    assert format_cost(0.0) == '$0.00'
    assert format_cost(0.832) == '$0.83'
    assert format_cost(60.732) == '$60.73'

def test_format_quota():
    assert format_quota(68, 100) == '68%'
    assert format_quota(78, 100) == '78%'
    assert format_quota(None, None) == '--'
    assert format_quota(68, 0) == '--'
    assert format_quota(None, 100) == '--'
    assert format_quota(68, None) == '--'

def test_quota_color():
    assert quota_color(78, 100) == 'normal'
    assert quota_color(80, 100) == 'orange'
    assert quota_color(94, 100) == 'orange'
    assert quota_color(95, 100) == 'red'
    assert quota_color(None, None) == 'normal'
    assert quota_color(68, 0) == 'normal'
    assert quota_color(None, 100) == 'normal'

def test_build_display_text_with_quota():
    q = {'h5': {'used': 78, 'limit': 100, 'reset': 't1'},
         'weekly': {'used': 68, 'limit': 100, 'reset': 't2'}}
    assert build_display_text(69411491, 60.732, 'kimi-k3', q) == \
        '69.4M tok · $60.73 · kimi-k3 · 5h 78% · 周 68%'

def test_build_display_text_without_quota():
    assert build_display_text(2100000, 0.83, 'glm-5.2', None) == \
        '2.1M tok · $0.83 · glm-5.2'

def test_build_display_text_no_model():
    assert build_display_text(0, 0.0, None, None) == \
        '0 tok · $0.00 · --'