from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
)


class SearchBar(QWidget):

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(58)

        self._busy = False

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            22,
            0,
            18,
            0
        )

        layout.setSpacing(14)

        # --------------------------------------------------
        # Status dot
        # --------------------------------------------------

        self.status_dot = QLabel()

        self.status_dot.setFixedSize(
            8,
            8
        )

        self.status_dot.setStyleSheet(
            """
            background-color: rgba(120, 190, 255, 230);
            border-radius: 4px;
            """
        )

        # --------------------------------------------------
        # Search icon
        # --------------------------------------------------

        self.search_icon = SearchIcon()

        self.search_icon.setFixedSize(
            28,
            28
        )

        # --------------------------------------------------
        # Input
        # --------------------------------------------------

        self.input = QLineEdit()

        self.input.setPlaceholderText(
            "Ask Jarvis anything..."
        )

        self.input.setFont(
            QFont(
                "Segoe UI Light",
                17
            )
        )

        self.input.setStyleSheet(
            """
            QLineEdit {
                background: transparent;
                border: none;
                color: rgba(245, 248, 255, 235);
                padding: 0;
            }

            QLineEdit::placeholder {
                color: rgba(235, 240, 250, 145);
            }
            """
        )

        self.input.returnPressed.connect(
            self.submit
        )

        # --------------------------------------------------
        # Arrow
        # --------------------------------------------------

        self.arrow = QLabel("→")

        self.arrow.setAlignment(
            Qt.AlignCenter
        )

        self.arrow.setFont(
            QFont(
                "Segoe UI Light",
                26
            )
        )

        self.arrow.setStyleSheet(
            """
            color: rgba(240, 245, 255, 190);
            background: transparent;
            """
        )

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        layout.addWidget(
            self.status_dot
        )

        layout.addWidget(
            self.search_icon
        )

        layout.addWidget(
            self.input,
            1
        )

        layout.addWidget(
            self.arrow
        )

        # --------------------------------------------------
        # Shadow
        # --------------------------------------------------

        shadow = QGraphicsDropShadowEffect(
            self
        )

        shadow.setBlurRadius(
            28
        )

        shadow.setOffset(
            0,
            6
        )

        shadow.setColor(
            Qt.black
        )

        self.setGraphicsEffect(
            shadow
        )

    # ======================================================
    # SUBMIT
    # ======================================================

    def submit(self):

        if self._busy:
            return

        text = self.input.text().strip()

        if not text:
            return

        self.submitted.emit(
            text
        )

        self.input.clear()

    # ======================================================
    # BUSY STATE
    # ======================================================

    def set_busy(self, busy):

        self._busy = busy

        if busy:

            self.input.setPlaceholderText(
                "Jarvis is thinking..."
            )

            self.input.setEnabled(
                False
            )

            self.arrow.setText(
                "⋯"
            )

            self.arrow.setStyleSheet(
                """
                color: rgba(120, 190, 255, 220);
                background: transparent;
                """
            )

            self.status_dot.setStyleSheet(
                """
                background-color: rgba(120, 190, 255, 255);
                border-radius: 4px;
                """
            )

        else:

            self.input.setPlaceholderText(
                "Ask Jarvis anything..."
            )

            self.input.setEnabled(
                True
            )

            self.arrow.setText(
                "→"
            )

            self.arrow.setStyleSheet(
                """
                color: rgba(240, 245, 255, 190);
                background: transparent;
                """
            )

            self.status_dot.setStyleSheet(
                """
                background-color: rgba(120, 190, 255, 230);
                border-radius: 4px;
                """
            )

            self.input.setFocus()

    # ======================================================
    # PAINT
    # ======================================================

    def paintEvent(self, event):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        rect = self.rect().adjusted(
            2,
            2,
            -2,
            -2
        )

        # --------------------------------------------------
        # Glass border
        # --------------------------------------------------

        painter.setBrush(
            Qt.GlobalColor.transparent
        )

        painter.setPen(
            QPen(
                Qt.white,
                1
            )
        )

        painter.setOpacity(
            0.20
        )

        painter.drawRoundedRect(
            rect,
            29,
            29
        )

        # --------------------------------------------------
        # Translucent fill
        # --------------------------------------------------

        painter.setPen(
            Qt.NoPen
        )

        painter.setBrush(
            Qt.GlobalColor.white
        )

        painter.setOpacity(
            0.15
        )

        painter.drawRoundedRect(
            rect,
            29,
            29
        )


class SearchIcon(QWidget):

    def paintEvent(self, event):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        pen = QPen(
            Qt.white,
            2.5
        )

        pen.setCapStyle(
            Qt.RoundCap
        )

        painter.setPen(
            pen
        )

        painter.setOpacity(
            0.9
        )

        # Magnifying glass
        painter.drawEllipse(
            4,
            3,
            17,
            17
        )

        painter.drawLine(
            18,
            17,
            25,
            24
        )