"""使用真实 Cocoa 栅格化验证双环，缺少 AppKit 的环境跳过。"""
import math

import pytest

pytest.importorskip('AppKit')
pytest.importorskip('rumps')
from AppKit import NSApplication, NSBitmapImageRep
from mac_bar import ring_image


@pytest.fixture(scope='module', autouse=True)
def cocoa_app():
    return NSApplication.sharedApplication()


def ring_pixels(h5, weekly, stale=False):
    image = ring_image(h5, weekly, stale)
    assert image.isTemplate()
    bitmap = NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
    width, height = bitmap.pixelsWide(), bitmap.pixelsHigh()
    inner, outer, right, left = 0, 0, 0, 0
    for y in range(height):
        for x in range(width):
            dx = (x + 0.5) * 20 / width - 10
            dy = (y + 0.5) * 20 / height - 10
            radius = math.hypot(dx, dy)
            alpha = bitmap.colorAtX_y_(x, y).alphaComponent()
            if radius < 6.4:
                inner += alpha
                if dx > 0:
                    right += alpha
                else:
                    left += alpha
            else:
                outer += alpha
    return inner, outer, right, left


def test_full_inner_ring_is_not_empty():
    empty = ring_pixels(0, 0)
    full = ring_pixels(1, 0)
    assert full[0] > empty[0] * 3
    assert full[1] == pytest.approx(empty[1])


def test_weekly_is_outer_ring():
    empty = ring_pixels(0, 0)
    full = ring_pixels(0, 1)
    assert full[1] > empty[1] * 3
    assert full[0] == pytest.approx(empty[0])


def test_quarter_ring_is_clockwise_and_not_three_quarters():
    empty = ring_pixels(0, 0)
    quarter = ring_pixels(0.25, 0)
    full = ring_pixels(1, 0)
    fraction = (quarter[0] - empty[0]) / (full[0] - empty[0])
    assert 0.20 < fraction < 0.30
    assert quarter[2] > quarter[3] * 2


def test_stale_preserves_full_ring_at_lower_opacity():
    empty = ring_pixels(0, 0)
    stale = ring_pixels(1, 1, True)
    full = ring_pixels(1, 1)
    for index in (0, 1):
        assert empty[index] < stale[index] < full[index]
    assert stale[2] == pytest.approx(stale[3], rel=0.03)


def test_unknown_rings_have_only_tracks():
    assert ring_pixels(None, None) == ring_pixels(0, 0)


def test_ui_maps_session_and_weekly_to_both_rings_and_title(monkeypatch):
    from types import SimpleNamespace
    import mac_bar
    bar = SimpleNamespace(
        _usage=(0, 0, None), _stale=False,
        _quota={'h5': {'used': 0, 'limit': 100, 'reset': None},
                'weekly': {'used': 100, 'limit': 100, 'reset': None}})
    for name in ('_m_today', '_m_cost', '_m_model', '_m_h5', '_m_week', '_m_stale'):
        setattr(bar, name, SimpleNamespace(title=''))
    seen = []
    def draw(h5, weekly, stale):
        seen.append((h5, weekly, stale))
        return ring_image(h5, weekly, stale)
    monkeypatch.setattr(mac_bar, 'ring_image', draw)
    mac_bar.MacUsageBar._update_ui(bar)
    assert seen == [(0.0, 1.0, False)]
    assert bar.title == '0% / 100%'
    assert bar._m_h5.title.startswith('5h: 0%')
    assert bar._m_week.title.startswith('周: 100%')
