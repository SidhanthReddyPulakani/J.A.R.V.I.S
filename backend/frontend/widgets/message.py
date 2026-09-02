from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
    QGraphicsOpacityEffect,
)
from PySide6.QtGui import QFont

import backend.frontend.theme as theme


class MessageBubble(QFrame):
    """
    A single rounded chat bubble.

    role: "user" | "assistant" | "error"
    """

    def __init__(self, text: str, role: str = "assistant", parent=None):
        super().__init__(parent)

        self.role = role

        self.setObjectName("bubble")
        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Maximum,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        font = QFont(theme.FONT_FAMILY)
        font.setPointSize(theme.SIZE_BODY)
        self.label.setFont(font)

        layout.addWidget(self.label)

        self._apply_style()

    # ------------------------------------------------------
    # STYLE
    # ------------------------------------------------------

    def _apply_style(self):

        if self.role == "user":
            bg = theme.rgba(theme.USER_BUBBLE_BG)
            text_color = theme.rgba(theme.USER_BUBBLE_TEXT)
            border = "none"

        elif self.role == "error":
            bg = theme.rgba(theme.ERROR_BUBBLE_BG)
            text_color = theme.rgba(theme.ERROR_BUBBLE_TEXT)
            border = f"1px solid {theme.rgba(theme.ERROR_BUBBLE_BORDER)}"

        else:
            bg = theme.rgba(theme.ASSISTANT_BUBBLE_BG)
            text_color = theme.rgba(theme.ASSISTANT_BUBBLE_TEXT)
            border = f"1px solid {theme.rgba(theme.ASSISTANT_BUBBLE_BORDER)}"

        self.setStyleSheet(
            f"""
            QFrame#bubble {{
                background: {bg};
                border: {border};
                border-radius: {theme.RADIUS_BUBBLE}px;
            }}
            QLabel {{
                background: transparent;
                color: {text_color};
                border: none;
            }}
            """
        )

    def set_max_bubble_width(self, width: int):
        self.setMaximumWidth(width)
        self.label.setMaximumWidth(width - 28)


class MessageRow(QWidget):
    """
    Aligns a bubble left (assistant/error) or right (user) within
    the conversation column, and fades it in on creation.
    """

    def __init__(self, text: str, role: str = "assistant", parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum,
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 3, 4, 3)

        self.bubble = MessageBubble(text, role=role)

        if role == "user":
            row.addStretch(1)
            row.addWidget(self.bubble)
        else:
            row.addWidget(self.bubble)
            row.addStretch(1)

        # --------------------------------------------------
        # Fade-in
        # --------------------------------------------------

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._animation = QPropertyAnimation(self._effect, b"opacity")
        self._animation.setDuration(220)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.start()

    def set_max_bubble_width(self, width: int):
        self.bubble.set_max_bubble_width(width)
