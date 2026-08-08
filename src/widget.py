from PySide6.QtWidgets import QWidget, QLabel, QApplication, QMenu
from PySide6.QtCore import Qt, Signal
from display_text import build_display_text, quota_color

_KEEP = object()  # 哨兵：update_data 不传 quota 时保持额度状态不变

COLORS = {
    'normal': '#d4d4d4',
    'orange': '#e0a030',
    'red': '#e05050',
    'grey': '#888888',
}

class UsageWidget(QWidget):
    moved = Signal()  # 拖动结束时发出，供 main 保存位置
    refresh_requested = Signal()  # 右键菜单"立即刷新"发出，供 main 触发刷新

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

    def update_data(self, usage, quota=_KEEP):
        self._usage = usage
        if quota is _KEEP:
            pass  # 仅刷用量，不动额度状态
        elif quota is not None:
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
            def _tier_txt(t):
                u = t['used'] if t['used'] is not None else '--'
                l = t['limit'] if t['limit'] is not None else '--'
                r = t['reset'] if t['reset'] is not None else '--'
                return f"{u}/{l} 重置 {r}"
            tip += (f"\n5h: {_tier_txt(self._quota['h5'])}\n"
                    f"周: {_tier_txt(self._quota['weekly'])}")
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

        # 文本变长后窗口可能超出屏幕右缘，收回来
        self._clamp_to_screen()

    def _clamp_to_screen(self):
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        g = screen.availableGeometry()
        x, y = self.x(), self.y()
        if self.x() + self.width() > g.right():
            x = g.right() - self.width()
        if self.y() + self.height() > g.bottom():
            y = g.bottom() - self.height()
        if x != self.x() or y != self.y():
            self.move(x, y)

    # 右键菜单：立即刷新 / 退出
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_refresh = menu.addAction('立即刷新')
        act_refresh.triggered.connect(self.refresh_requested.emit)
        act_quit = menu.addAction('退出')
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.exec(e.globalPos())

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