from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal
from display_text import build_display_text, quota_color

COLORS = {
    'normal': '#d4d4d4',
    'orange': '#e0a030',
    'red': '#e05050',
    'grey': '#888888',
}

class UsageWidget(QWidget):
    moved = Signal()  # 拖动结束时发出，供 main 保存位置

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

    def update_data(self, usage, quota):
        self._usage = usage
        if quota is not None:
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
            tip += (f"\n5h: {self._quota['h5']['used']}/{self._quota['h5']['limit']} "
                    f"重置 {self._quota['h5']['reset']}\n"
                    f"周: {self._quota['weekly']['used']}/{self._quota['weekly']['limit']} "
                    f"重置 {self._quota['weekly']['reset']}")
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