from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

import backend.frontend.theme as theme


class ResizeGrip(QWidget):
    """
    Small bottom-right handle that lets the frameless panel be
    resized by dragging, since Qt gives us no native border
    resizing once WindowFlags strip the frame away.
    """

    def __init__(self, target_window, parent=None):
        super().__init__(parent)

        self.target = target_window

        self.setFixedSize(18, 18)
        self.setCursor(Qt.SizeFDiagCursor)

        self._dragging = False
        self._start_pos = QPoint()
        self._start_size = None

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:

            self._dragging = True
            self._start_pos = event.globalPosition().toPoint()
            self._start_size = self.target.size()

    def mouseMoveEvent(self, event):

        if not self._dragging:
            return

        delta = event.globalPosition().toPoint() - self._start_pos

        new_width = max(
            self.target.MIN_WIDTH,
            self._start_size.width() + delta.x(),
        )

        new_height = max(
            self.target.MIN_HEIGHT,
            self._start_size.height() + delta.y(),
        )

        self.target.resize(new_width, new_height)

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r, g, b, a = theme.TEXT_SECONDARY
        pen = QPen(QColor(r, g, b, a), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setOpacity(0.35)

        # Three short diagonal strokes, Mac/Windows-grip style.
        for offset in (0, 5, 10):
            painter.drawLine(
                12 - offset, 16,
                16, 12 - offset,
            )
