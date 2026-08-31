from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QToolButton,
)

import backend.frontend.theme as theme


class StatusDot(QLabel):
    """Small status dot: blue = idle, amber = busy, gray = offline."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(9, 9)
        self._state = "idle"
        self._paint()

    def set_state(self, state: str):
        """state: 'idle' | 'busy' | 'offline'"""
        self._state = state
        self._paint()

    def _paint(self):

        colors = {
            "idle": theme.STATUS_IDLE,
            "busy": theme.STATUS_BUSY,
            "offline": theme.STATUS_OFFLINE,
        }

        color = colors.get(self._state, theme.STATUS_IDLE)

        self.setStyleSheet(
            f"""
            background-color: {theme.rgba(color)};
            border-radius: 4px;
            """
        )


class SearchBar(QWidget):
    """
    Pill-shaped input bar: status dot, text field, send button.

    Uses QSS for the pill shape/border instead of hand-painted
    QPainter geometry, and a QGraphicsDropShadowEffect that
    intensifies subtly on focus.
    """

    submitted = Signal(str)

    HEIGHT = 52

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("searchBar")
        self.setFixedHeight(self.HEIGHT)

        self._busy = False
        self._offline = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(12)

        # --------------------------------------------------
        # Status dot
        # --------------------------------------------------

        self.status_dot = StatusDot()

        # --------------------------------------------------
        # Input
        # --------------------------------------------------

        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis anything...")
        self.input.setObjectName("searchInput")

        font = QFont(theme.FONT_FAMILY_LIGHT)
        font.setPointSize(theme.SIZE_INPUT)
        self.input.setFont(font)

        self.input.returnPressed.connect(self.submit)

        # --------------------------------------------------
        # Send button
        # --------------------------------------------------

        self.send_button = QToolButton()
        self.send_button.setText("➤")
        self.send_button.setObjectName("sendButton")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setFixedSize(32, 32)
        self.send_button.clicked.connect(self.submit)

        layout.addWidget(self.status_dot)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.send_button)

        self._apply_style()

        # --------------------------------------------------
        # Shadow (subtle by default, glows on focus)
        # --------------------------------------------------

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 4)
        self._set_shadow(blur=22, alpha=90)
        self.setGraphicsEffect(self._shadow)

        self.input.installEventFilter(self)

    # ------------------------------------------------------
    # STYLE
    # ------------------------------------------------------

    def _apply_style(self):

        self.setStyleSheet(
            f"""
            QWidget#searchBar {{
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: {theme.RADIUS_PILL}px;
            }}

            QLineEdit#searchInput {{
                background: transparent;
                border: none;
                color: {theme.rgba(theme.TEXT_PRIMARY)};
                padding: 0;
            }}

            QLineEdit#searchInput::placeholder {{
                color: {theme.rgba(theme.TEXT_SECONDARY)};
            }}

            QToolButton#sendButton {{
                background: {theme.rgba(theme.ACCENT_SOFT)};
                border: none;
                border-radius: 16px;
                color: {theme.rgba(theme.ACCENT_STRONG)};
                font-size: 13px;
            }}

            QToolButton#sendButton:hover {{
                background: {theme.rgba((theme.ACCENT[0], theme.ACCENT[1], theme.ACCENT[2], 75))};
            }}

            QToolButton#sendButton:disabled {{
                color: {theme.rgba(theme.TEXT_MUTED)};
                background: rgba(255, 255, 255, 10);
            }}
            """
        )

    def _set_shadow(self, blur, alpha):
        self._shadow.setBlurRadius(blur)
        self._shadow.setColor(Qt.black)

    # ------------------------------------------------------
    # FOCUS GLOW
    # ------------------------------------------------------

    def eventFilter(self, obj, event):

        if obj is self.input:

            if event.type() == event.Type.FocusIn:
                self._set_shadow(blur=32, alpha=140)

            elif event.type() == event.Type.FocusOut:
                self._set_shadow(blur=22, alpha=90)

        return super().eventFilter(obj, event)

    # ------------------------------------------------------
    # SUBMIT
    # ------------------------------------------------------

    def submit(self):

        if self._busy or self._offline:
            return

        text = self.input.text().strip()

        if not text:
            return

        self.submitted.emit(text)
        self.input.clear()

    # ------------------------------------------------------
    # BUSY STATE
    # ------------------------------------------------------

    def set_busy(self, busy: bool):

        # Offline is a stickier state than busy — a stray busy_changed
        # signal arriving after the backend has already been stopped
        # must not silently re-enable the input.
        if self._offline:
            return

        self._busy = busy

        self.status_dot.set_state("busy" if busy else "idle")
        self.send_button.setEnabled(not busy)

        if busy:
            self.input.setPlaceholderText("Jarvis is thinking...")
            self.input.setEnabled(False)
        else:
            self.input.setPlaceholderText("Ask Jarvis anything...")
            self.input.setEnabled(True)
            self.input.setFocus()

    # ------------------------------------------------------
    # OFFLINE STATE
    #
    # Distinct from "busy": this reflects the backend being
    # stopped entirely (e.g. disabled from the tray), not a
    # single in-flight request. The widget stays visible and
    # on the desktop — it just can't take input right now.
    # ------------------------------------------------------

    def set_offline(self, offline: bool):

        self._offline = offline
        self._busy = False

        if offline:
            self.status_dot.set_state("offline")
            self.input.setPlaceholderText("Jarvis is offline")
            self.input.setEnabled(False)
            self.send_button.setEnabled(False)
        else:
            self.status_dot.set_state("idle")
            self.input.setPlaceholderText("Ask Jarvis anything...")
            self.input.setEnabled(True)
            self.send_button.setEnabled(True)
            self.input.setFocus()
