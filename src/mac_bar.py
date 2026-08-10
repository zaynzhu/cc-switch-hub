# src/mac_bar.py
"""macOS 菜单栏用量条（rumps）。盲写，回家测。
- icon：单色进度环，NSImage 矢量，填充比例=5h 额度水位
- title：'{token} {cost} {h5_pct}'
- 菜单：详情 + 立即刷新 / 退出
- 30s 刷用量、5min 后台线程查额度，主线程刷 UI
"""
import os, threading
import rumps
from AppKit import NSImage, NSBezierPath, NSColor

from mac_text import build_title, ring_ratio, build_menu_items
from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
USAGE_INTERVAL = 30        # 秒
QUOTA_INTERVAL = 5 * 60    # 秒


def ring_image(ratio, stale=False, size=18):
    """NSImage 矢量画单色进度环。ratio=None 画空环；stale 加缺口。
    template 模式单色，随深浅模式自动反色。绘制失败抛异常由调用方兜底。"""
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSColor.controlTextColor().set()
    r = size / 2 - 2
    center = (size / 2, size / 2)
    # 背景整环（细）
    bg = NSBezierPath.bezierPath()
    bg.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
        center, r, 0, 360)
    bg.setLineWidth_(1.5)
    bg.stroke()
    # 前景填充比例（粗，从 12 点顺时针）
    if ratio is not None:
        fill = ratio if not stale else max(0.0, ratio - 0.08)
        end_angle = 90 - 360 * fill
        fg = NSBezierPath.bezierPath()
        fg.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
            center, r, 90, end_angle)
        fg.setLineWidth_(2.5)
        fg.stroke()
    img.unlockFocus()
    img.setTemplate_(True)  # 单色 template，菜单栏自动反色
    return img


class MacUsageBar(rumps.App):
    def __init__(self):
        super().__init__(name='cc-switch 用量条', title='0 $0.00 --', icon=None)
        # 菜单：5 详情行 + stale 占位行 + 分隔 + 立即刷新 + 退出
        self.menu = ['今日: --', '花费: --', '近用: --', '5h: --', '周: --',
                     '', None, '立即刷新', '退出']
        self._usage = (0, 0.0, None)
        self._quota = None
        self._stale = False
        self._quota_dirty = False  # 后台线程查完置 True，主线程 timer 检测刷 UI
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_usage()
        self._refresh_quota_async()

    def _refresh_usage(self):
        self._usage = get_today_usage(DB_PATH)
        self._update_ui()

    def _refresh_quota_async(self):
        threading.Thread(target=self._fetch_quota, daemon=True).start()

    def _fetch_quota(self):
        """后台线程：查额度，整体引用替换 self._quota（原子），置 dirty 标志。
        不直接刷 UI（Cocoa UI 须主线程）。"""
        prov = get_current_provider(DB_PATH, SETTINGS_JSON_PATH)
        q = fetch_quota(prov[0], prov[1]) if prov else None
        if q is None and self._quota is not None:
            self._stale = True  # 曾有数据但本次失败 → 过期
        elif q is not None:
            self._stale = False
            self._quota = q
        self._quota_dirty = True

    def _update_ui(self):
        u = self._usage
        q = self._quota
        h5 = q['h5'] if q else None
        h5_used = h5['used'] if h5 else None
        h5_limit = h5['limit'] if h5 else None
        self.title = build_title(u[0], u[1], h5_used, h5_limit)
        ratio = ring_ratio(h5_used, h5_limit)
        try:
            self.icon = ring_image(ratio, self._stale)
        except Exception:
            self.icon = None  # 兜底：title 已含 58% 数字，水位不丢
        # 菜单详情文本（前 5 行 + 可选第 6 行过期提示）
        items = build_menu_items(u[0], u[1], u[2], q, self._stale)
        for i, text in enumerate(items[:5]):
            self.menu[i].title = text
        # 第 6 行（索引 5）：stale 时显示过期提示，否则空文本占位
        self.menu[5].title = items[5] if len(items) > 5 else ''

    @rumps.timer(USAGE_INTERVAL)
    def _usage_timer(self, _sender):
        self._refresh_usage()
        # 顺带把后台完成的额度刷出来（延迟 ≤30s）
        if self._quota_dirty:
            self._quota_dirty = False
            self._update_ui()

    @rumps.timer(QUOTA_INTERVAL)
    def _quota_timer(self, _sender):
        self._refresh_quota_async()

    @rumps.clicked('立即刷新')
    def _refresh_now(self, _):
        self._refresh_all()

    @rumps.clicked('退出')
    def _quit(self, _):
        rumps.quit_application()


def run():
    """main.py 的 darwin 分支调用。"""
    MacUsageBar().run()