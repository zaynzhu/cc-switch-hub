# src/mac_bar.py
"""macOS 菜单栏用量条（rumps）。盲写，回家测。
- icon：单色进度环，NSImage 矢量，填充比例=5h 额度水位
- title：'{token} {cost} {h5_pct}'
- 菜单：详情 + 立即刷新 / 退出
- 30s 刷用量、5min 后台线程查额度，主线程刷 UI
"""
import os, threading, subprocess
import rumps
from AppKit import NSImage, NSBezierPath, NSColor
from Foundation import NSBundle

from mac_text import build_title, ring_ratio, build_menu_items
from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
USAGE_INTERVAL = 30        # 秒
QUOTA_INTERVAL = 5 * 60    # 秒
LA_LABEL = 'com.zaynzhu.cc-switch-hub'  # 开机自启 LaunchAgent 标签
LA_PLIST = os.path.expanduser('~/Library/LaunchAgents/com.zaynzhu.cc-switch-hub.plist')


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
        # 详情行用 MenuItem 引用持有：rumps Menu 容器按 title 做 key，
        # 不能用整数索引 self.menu[i]（KeyError），且 title 变化后 key 也变，
        # 故持有引用直接改 .title 最稳。
        self._m_today = rumps.MenuItem('今日: --')
        self._m_cost = rumps.MenuItem('花费: --')
        self._m_model = rumps.MenuItem('近用: --')
        self._m_h5 = rumps.MenuItem('5h: --')
        self._m_week = rumps.MenuItem('周: --')
        self._m_stale = rumps.MenuItem('')  # 第 6 占位行：stale 时填过期提示
        self._m_autostart = rumps.MenuItem('开机自启', callback=self._toggle_autostart)
        self._m_autostart.state = 1 if self._autostart_enabled() else 0
        self.menu = [self._m_today, self._m_cost, self._m_model,
                     self._m_h5, self._m_week, self._m_stale,
                     None, '立即刷新', self._m_autostart, '退出']
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
        # rumps App.icon setter 只收文件路径、不接受 NSImage，直接写内部
        # _icon_nsimage 并刷 status bar。构造阶段 _nsapp 未就绪会 AttributeError，
        # _icon_nsimage 已存，run loop 启动时 setStatusBarIcon 自动取用它。
        try:
            self._icon_nsimage = ring_image(ratio, self._stale)
        except Exception:
            self._icon_nsimage = None  # 兜底：title 已含水位百分比，水位不丢
        try:
            self._nsapp.setStatusBarIcon()
        except AttributeError:
            pass
        # 菜单详情文本：通过 __init__ 持有的 MenuItem 引用改 title
        items = build_menu_items(u[0], u[1], u[2], q, self._stale)
        self._m_today.title = items[0]
        self._m_cost.title = items[1]
        self._m_model.title = items[2]
        # 无额度时只有 3 行，5h/周 保持初始 '--'
        if len(items) > 3:
            self._m_h5.title = items[3]
        if len(items) > 4:
            self._m_week.title = items[4]
        # 第 6 占位行：stale 时显示过期提示，否则空文本
        self._m_stale.title = items[5] if len(items) > 5 else ''

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

    def _autostart_enabled(self):
        """开机自启是否已配置（LaunchAgent plist 存在）。"""
        return os.path.exists(LA_PLIST)

    def _toggle_autostart(self, _):
        """切换开机自启：写/删 LaunchAgent plist + launchctl load/unload。
        需打包 .app 后使用（python 运行时无 bundle，注册的是 Python.app）。"""
        if self._autostart_enabled():
            subprocess.run(['launchctl', 'unload', LA_PLIST], capture_output=True)
            try:
                os.remove(LA_PLIST)
            except OSError:
                pass
            self._m_autostart.state = 0
            return
        app_path = NSBundle.mainBundle().bundlePath()
        if not (app_path and app_path.endswith('.app') and 'cc-switch-hub' in app_path):
            rumps.notification('cc-switch 用量条', '开机自启', '需打包成 .app 后使用')
            return
        exe = os.path.join(app_path, 'Contents', 'MacOS', 'cc-switch-hub')
        plist = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                 '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                 '<plist version="1.0">\n<dict>\n'
                 f'  <key>Label</key><string>{LA_LABEL}</string>\n'
                 f'  <key>Program</key><string>{exe}</string>\n'
                 '  <key>RunAtLoad</key><true/>\n'
                 '  <key>KeepAlive</key><false/>\n'
                 '</dict>\n</plist>\n')
        try:
            os.makedirs(os.path.dirname(LA_PLIST), exist_ok=True)
            with open(LA_PLIST, 'w') as f:
                f.write(plist)
            subprocess.run(['launchctl', 'load', LA_PLIST], capture_output=True)
            self._m_autostart.state = 1
        except OSError:
            rumps.notification('cc-switch 用量条', '开机自启', '写入启动配置失败')


def run():
    """main.py 的 darwin 分支调用。"""
    app = MacUsageBar()
    # 构造时 ring_image 因无 NSGraphicsContext 失败（icon 暂存 None）；
    # run loop 启动后 1 秒重画一次，让进度环立即可见，不必干等 30s 定时器
    rumps.Timer(lambda _sender: app._update_ui(), 1).start()
    app.run()