from PySide6.QtWidgets import QWidget, QLabel, QApplication, QMenu, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QPen, QColor
from display_text import build_display_text, quota_color, format_reset
from mac_text import ring_ratio

_KEEP = object()  # 哨兵：update_data 不传 quota 时保持额度状态不变

COLORS = {
    'normal': '#5bb974',   # 圆点：额度充足-绿
    'orange': '#e3b341',   # 接近上限-琥珀
    'red': '#f85149',      # 超限-红
    'grey': '#888888',     # 无数据或过期-灰
}
TEXT_COLOR = '#e8e8e8'
BG_COLOR = 'transparent'


class RingWidget(QWidget):
    """自绘双进度环：内圈 5h、外圈周额度，各弧取各自档位色。
    对齐 mac_bar.ring_image 的几何，QPainter 等价实现。"""

    SIZE = 18
    # 半径按 macOS 比例（0.235/0.415），线宽略缩保证两环间留 ≥1px 空隙
    INNER_R = SIZE * 0.235
    INNER_W = 1.8
    OUTER_R = SIZE * 0.415
    OUTER_W = 2.4

    def __init__(self):
        super().__init__()
        self._h5_ratio = None     # 内圈 0-1 填充比例，None=无额度画空环
        self._h5_color = COLORS['grey']
        self._weekly_ratio = None  # 外圈周额度比例
        self._weekly_color = COLORS['grey']
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_state(self, h5_ratio, h5_color, weekly_ratio, weekly_color):
        self._h5_ratio = h5_ratio
        self._h5_color = h5_color
        self._weekly_ratio = weekly_ratio
        self._weekly_color = weekly_color
        self.update()

    def _draw_ring(self, p, radius, width, ratio, color):
        c = self.width() / 2
        rect = QRectF(c - radius, c - radius, 2 * radius, 2 * radius)
        # 轨道整环（细，半透明）
        bg = QPen(QColor(255, 255, 255, 60))
        bg.setWidthF(1.0)
        p.setPen(bg)
        p.drawArc(rect, 0, 360 * 16)
        # 填充弧（档位色，从 12 点顺时针）；无额度或 0% 只画轨道
        if not ratio:
            return
        fg = QPen(QColor(color))
        fg.setWidthF(width)
        p.setPen(fg)
        # 满圈画 -360° 整圆，Qt 不会像 Cocoa 那样把整周归一化为零
        p.drawArc(rect, 90 * 16, int(-360 * min(ratio, 1.0) * 16))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_ring(p, self.OUTER_R, self.OUTER_W,
                        self._weekly_ratio, self._weekly_color)
        self._draw_ring(p, self.INNER_R, self.INNER_W,
                        self._h5_ratio, self._h5_color)


class UsageWidget(QWidget):
    moved = Signal()  # 拖动结束时发出，供 main 保存位置
    refresh_requested = Signal()  # 右键菜单"立即刷新"发出，供 main 触发刷新

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # 窄条从不激活（WA_ShowWithoutActivating），Windows 默认只给激活窗口
        # 显示 tooltip，悬停永远出不来 → 顶级窗口设"未激活也显示"开关
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 透明背景
        self._usage = (0, 0.0, None)
        self._quota = None
        self._stale = False  # 额度数据是否过期（接口失败但曾有数据）
        self._drag_pos = None
        self._user_moved = False  # 用户拖动过则不再自动居中

        # 整条背景画在 widget 上、label 透明，避免双 label 间背景断裂
        self.setObjectName('UsageWidget')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"#UsageWidget{{background-color:{BG_COLOR};}}")
        # 进度环与文字分两个 widget：环自绘水位、文字纯文本，各自垂直居中
        self._ring = RingWidget()
        self._text_label = QLabel(self)
        self._text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._text_label.setStyleSheet(
            f"QLabel{{font-family:'Microsoft YaHei UI';font-size:10pt;"
            f"color:{TEXT_COLOR};}}")
        self._text_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)
        layout.addWidget(self._ring)
        layout.addWidget(self._text_label, 1)
        self._text_label.setText('-- tok · $-- · --')

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

        # 双环色：过期或无额度 → 灰；有额度各环取各自档位色
        if self._stale or not self._quota:
            h5_color = wk_color = COLORS['grey']
        else:
            h5_color = COLORS[quota_color(self._quota['h5']['used'], self._quota['h5']['limit'])]
            wk_color = COLORS[quota_color(self._quota['weekly']['used'], self._quota['weekly']['limit'])]
        # 双环填充比例：内圈 5h、外圈周（stale 用上次额度数据，灰弧表过期）
        h5_ratio = ring_ratio(self._quota['h5']['used'], self._quota['h5']['limit']) if self._quota else None
        wk_ratio = ring_ratio(self._quota['weekly']['used'], self._quota['weekly']['limit']) if self._quota else None
        self._ring.set_state(h5_ratio, h5_color, wk_ratio, wk_color)

        self._text_label.setText(text)
        self.adjustSize()

        # tooltip 完整数字（与右键菜单详情行共用）
        self.setToolTip('\n'.join(self._detail_lines()))

        # 文本变长后位置调整：用户拖动过则防超屏，否则保持顶部居中
        if self._user_moved:
            self._clamp_to_screen()
        else:
            self.snap_top_center()

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

    def snap_top_center(self):
        """贴工作区上边、水平居中。"""
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        g = screen.availableGeometry()
        x = g.left() + (g.width() - self.width()) // 2
        self.move(x, g.top())

    def _detail_lines(self):
        """详情行：今日用量/花费、近用模型、5h/周额度与重置时间。
        tooltip 与右键菜单顶部共用，无额度时只有前两行。"""
        u = self._usage
        lines = [f"今日: {u[0]} tok / {u[1]:.4f} USD",
                 f"近用模型: {u[2] or '--'}"]
        if self._quota:
            def _tier_txt(t):
                u = t['used'] if t['used'] is not None else '--'
                l = t['limit'] if t['limit'] is not None else '--'
                r = format_reset(t['reset'])
                return f"{u}/{l} 重置 {r}"
            lines.append(f"5h: {_tier_txt(self._quota['h5'])}")
            lines.append(f"周: {_tier_txt(self._quota['weekly'])}")
            if self._stale:
                lines.append('(额度数据已过期)')
        return lines

    # 右键菜单：详情行 / 立即刷新 / 退出
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        # 详情行置灰不可点，仅展示（对齐 macOS 菜单的 5h/周重置时间）
        for line in self._detail_lines():
            act = menu.addAction(line)
            act.setEnabled(False)
        menu.addSeparator()
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
            target = e.globalPosition().toPoint() - self._drag_pos
            # 拖动时实时限制在工作区内，避免松手后延迟弹回
            screen = QApplication.screenAt(target) or QApplication.primaryScreen()
            g = screen.availableGeometry()
            x = max(g.left(), min(target.x(), g.right() - self.width()))
            y = max(g.top(), min(target.y(), g.bottom() - self.height()))
            self.move(x, y)
            e.accept()
    def mouseReleaseEvent(self, e):
        if self._drag_pos is not None:
            self._drag_pos = None
            self._user_moved = True
            self.moved.emit()
