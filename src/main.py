import sys, os, json, subprocess

from usage_reader import get_today_usage
from quota_fetcher import get_current_provider, fetch_quota

DB_PATH = os.path.expanduser('~/.cc-switch/cc-switch.db')
SETTINGS_JSON_PATH = os.path.expanduser('~/.cc-switch/settings.json')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
USAGE_INTERVAL = 30 * 1000      # 30 秒
QUOTA_INTERVAL = 5 * 60 * 1000  # 5 分钟

# 持有运行中的 QuotaWorker，防止 Python 包装对象被 GC 后 Qt 销毁运行中的线程
_workers = set()


def load_settings():
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(pos):
    try:
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump({'x': pos.x(), 'y': pos.y()}, f)
    except OSError:
        pass


def place_default(widget):
    """放到屏幕工作区顶部水平居中、贴上边。"""
    widget.snap_top_center()


def run_windows():
    """Windows 路径：PySide6 延迟 import，Mac 不加载。"""
    from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu)
    from PySide6.QtGui import QIcon, QAction
    from PySide6.QtCore import QTimer, Qt, QThread, Signal
    from widget import UsageWidget

    def _resource_path(name):
        """资源绝对路径：打包态从 sys._MEIPASS 读，脚本态从 build/ 读。"""
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, name)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'build', name)

    def _make_tray_icon():
        """托盘图标用 ripple.ico（与 exe 文件图标一致）。"""
        return QIcon(_resource_path('ripple.ico'))

    class QuotaWorker(QThread):
        fetched = Signal(object)

        def __init__(self, db_path):
            super().__init__()
            self.db_path = db_path

        def run(self):
            prov = get_current_provider(self.db_path, SETTINGS_JSON_PATH)
            if not prov:
                self.fetched.emit(None)
                return
            base, token, _name = prov
            self.fetched.emit(fetch_quota(base, token))

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

    # 开机自启：启动文件夹快捷方式（对齐 mac_bar 的 LaunchAgent 菜单项）
    STARTUP_LNK = os.path.expandvars(
        r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\cc-switch-hub.lnk')

    def _ps_quote(s):
        """PowerShell 单引号字符串转义：路径内单引号翻倍。"""
        return s.replace("'", "''")

    def _pythonw_path():
        """优先用 sys.executable 同目录的 pythonw.exe（无控制台），
        找不到则回退 sys.executable（带控制台窗口）。"""
        cand = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        return cand if os.path.exists(cand) else sys.executable

    def _enable_autostart():
        """写启动文件夹 .lnk，返回 (是否成功, 是否回退到带控制台解释器)。
        打包态(frozen)快捷方式直接指 exe 自身；脚本态找 pythonw 无控制台启动。"""
        if getattr(sys, 'frozen', False):
            # PyInstaller onefile：sys.executable 就是 exe，无需解释器/脚本/工作目录
            exe = sys.executable
            args = ''
            workdir = ''
            fallback = False
        else:
            exe = _pythonw_path()
            args = os.path.abspath(__file__)
            workdir = os.path.dirname(os.path.dirname(args))  # 仓库根
            fallback = exe == sys.executable
        ps = ("$ws = New-Object -ComObject WScript.Shell;"
              f"$lnk = $ws.CreateShortcut('{_ps_quote(STARTUP_LNK)}');"
              f"$lnk.TargetPath = '{_ps_quote(exe)}';")
        if args:
            ps += f"$lnk.Arguments = '{_ps_quote(args)}';"
        if workdir:
            ps += f"$lnk.WorkingDirectory = '{_ps_quote(workdir)}';"
        ps += "$lnk.Save()"
        subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                       capture_output=True)
        return os.path.exists(STARTUP_LNK), fallback

    def _disable_autostart():
        """删启动文件夹 .lnk；删除失败返回 False（调用方还原勾选）。"""
        try:
            os.remove(STARTUP_LNK)
        except OSError:
            pass
        return not os.path.exists(STARTUP_LNK)

    def _toggle_autostart():
        """QAction checkable 点击后 isChecked 已自动切换，据此写/删 .lnk。"""
        if act_autostart.isChecked():
            ok, fallback = _enable_autostart()
            if not ok:
                act_autostart.setChecked(False)
                tray.showMessage('cc-switch 用量条', '写入自启快捷方式失败',
                                 QSystemTrayIcon.Warning, 3000)
            elif fallback:
                tray.showMessage('cc-switch 用量条', '未找到 pythonw，自启将带控制台窗口',
                                 QSystemTrayIcon.Information, 3000)
        else:
            if not _disable_autostart():
                act_autostart.setChecked(True)  # 删失败还原勾选

    # 托盘
    tray = QSystemTrayIcon()
    tray.setIcon(_make_tray_icon())
    tray.setToolTip('cc-switch 用量条')
    menu = QMenu()
    act_refresh = QAction('立即刷新')
    act_refresh.triggered.connect(lambda: (refresh_usage(), refresh_quota()))
    menu.addAction(act_refresh)
    act_autostart = QAction('开机自启')
    act_autostart.setCheckable(True)
    act_autostart.setChecked(os.path.exists(STARTUP_LNK))
    act_autostart.triggered.connect(_toggle_autostart)
    menu.addAction(act_autostart)
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


def run_mac():
    """Mac 路径：rumps 菜单栏。"""
    from mac_bar import run as mac_run
    mac_run()


def main():
    if sys.platform == 'darwin':
        run_mac()
    else:
        run_windows()


if __name__ == '__main__':
    main()