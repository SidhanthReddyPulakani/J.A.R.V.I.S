from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtGui import QFont

import frontend.theme as theme


class TypingIndicator(QWidget):
    """
    Three dots that pulse in sequence, styled like the assistant
    bubble, shown while waiting on a backend response.
    """

    DOT_COUNT = 3
    INTERVAL_MS = 260

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Maximum,
            QSizePolicy.Maximum,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(5)

        self.setStyleSheet(
            f"""
            TypingIndicator {{
                background: {theme.rgba(theme.ASSISTANT_BUBBLE_BG)};
                border: 1px solid {theme.rgba(theme.ASSISTANT_BUBBLE_BORDER)};
                border-radius: {theme.RADIUS_BUBBLE}px;
            }}
            """
        )

        self._dots = []

        for _ in range(self.DOT_COUNT):

            dot = QLabel("•")

            font = QFont(theme.FONT_FAMILY)
            font.setPointSize(16)
            font.setBold(True)
            dot.setFont(font)

            dot.setStyleSheet(
                f"color: {theme.rgba(theme.TEXT_MUTED)}; background: transparent;"
            )

            layout.addWidget(dot)
            self._dots.append(dot)

        self._active_index = 0

        self._timer = QTimer(self)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    # ------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------

    def start(self):
        self._active_index = 0
        self._render()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # ------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------

    def _advance(self):
        self._active_index = (self._active_index + 1) % self.DOT_COUNT
        self._render()

    def _render(self):

        for index, dot in enumerate(self._dots):

            if index == self._active_index:
                dot.setStyleSheet(
                    f"color: {theme.rgba(theme.ACCENT_STRONG)}; background: transparent;"
                )
            else:
                dot.setStyleSheet(
                    f"color: {theme.rgba(theme.TEXT_MUTED)}; background: transparent;"
                )
