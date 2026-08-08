import sys, os, json
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PySide6.QtCore import QTimer, Qt, QThread, Signal

from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota
from widget import UsageWidget

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
USAGE_INTERVAL = 30 * 1000      # 30 秒
QUOTA_INTERVAL = 5 * 60 * 1000  # 5 分钟

# 持有运行中的 QuotaWorker，防止 Python 包装对象被 GC 后 Qt 销毁运行中的线程
_workers = set()


class QuotaWorker(QThread):
    fetched = Signal(object)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        prov = get_current_provider(DB_PATH, SETTINGS_JSON_PATH)
        if not prov:
            self.fetched.emit(None)
            return
        base, token, _name = prov
        self.fetched.emit(fetch_quota(base, token))


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
    """放到屏幕左下角（任务栏上方）。"""
    screen = QApplication.primaryScreen()
    geo = screen.availableGeometry()
    widget.move(geo.left() + 8,
                geo.bottom() - widget.height())


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
        widget.update_data(get_today_usage(DB_PATH))

    def refresh_quota():
        worker = QuotaWorker(DB_PATH)
        _workers.add(worker)
        worker.fetched.connect(
            lambda q: widget.update_data(widget._usage, q))
        worker.finished.connect(lambda: _workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    # 窄条上的右键"立即刷新"
    widget.refresh_requested.connect(lambda: (refresh_usage(), refresh_quota()))

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
    tray.setIcon(_make_tray_icon())
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

    def _on_quit():
        for w in list(_workers):
            w.wait(2000)
    app.aboutToQuit.connect(_on_quit)

    app.exec()


if __name__ == '__main__':
    main()
