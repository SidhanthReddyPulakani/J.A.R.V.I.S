from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
)
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

import frontend.theme as theme


class OverlayMessageBubble(QFrame):
    """
    A single rounded chat bubble used exclusively by OverlayWindow.

    role:
        "user"
        "assistant"
        "error"
    """

    def __init__(
        self,
        text: str,
        role: str = "assistant",
        parent=None,
    ):
        super().__init__(parent)

        self.role = role

        self.setObjectName(
            "overlayBubble"
        )

        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Maximum,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            14,
            9,
            14,
            9,
        )

        self.label = QLabel(
            text
        )

        self.label.setWordWrap(
            True
        )

        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        font = QFont(
            theme.FONT_FAMILY
        )

        font.setPointSize(
            theme.SIZE_BODY
        )

        self.label.setFont(
            font
        )

        layout.addWidget(
            self.label
        )

        self._apply_style()

    # ======================================================
    # STYLE
    # ======================================================

    def _apply_style(self):

        if self.role == "user":

            bg = theme.rgba(
                theme.USER_BUBBLE_BG
            )

            text_color = theme.rgba(
                theme.USER_BUBBLE_TEXT
            )

            border = "none"

        elif self.role == "error":

            bg = theme.rgba(
                theme.ERROR_BUBBLE_BG
            )

            text_color = theme.rgba(
                theme.ERROR_BUBBLE_TEXT
            )

            border = (
                f"1px solid "
                f"{theme.rgba(theme.ERROR_BUBBLE_BORDER)}"
            )

        else:

            bg = theme.rgba(
                theme.ASSISTANT_BUBBLE_BG
            )

            text_color = theme.rgba(
                theme.ASSISTANT_BUBBLE_TEXT
            )

            border = (
                f"1px solid "
                f"{theme.rgba(theme.ASSISTANT_BUBBLE_BORDER)}"
            )

        self.setStyleSheet(
            f"""
            QFrame#overlayBubble {{
                background: {bg};
                border: {border};
                border-radius:
                    {theme.RADIUS_BUBBLE}px;
            }}

            QLabel {{
                background: transparent;
                color: {text_color};
                border: none;
            }}
            """
        )

    # ======================================================
    # WIDTH
    # ======================================================

    def set_max_bubble_width(
        self,
        width: int,
    ):

        width = max(
            100,
            int(width),
        )

        self.setMaximumWidth(
            width
        )

        self.label.setMaximumWidth(
            max(
                72,
                width - 28,
            )
        )


class OverlayMessageRow(QWidget):
    """
    Overlay-specific message row.

    User messages are right aligned.
    Assistant/error messages are left aligned.
    """

    def __init__(
        self,
        text: str,
        role: str = "assistant",
        parent=None,
    ):
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum,
        )

        row = QHBoxLayout(
            self
        )

        row.setContentsMargins(
            4,
            3,
            4,
            3,
        )

        self.bubble = OverlayMessageBubble(
            text,
            role=role,
        )

        if role == "user":

            row.addStretch(
                1
            )

            row.addWidget(
                self.bubble
            )

        else:

            row.addWidget(
                self.bubble
            )

            row.addStretch(
                1
            )

        # ==================================================
        # FADE IN
        # ==================================================

        self._effect = (
            QGraphicsOpacityEffect(
                self
            )
        )

        self._effect.setOpacity(
            0.0
        )

        self.setGraphicsEffect(
            self._effect
        )

        self._animation = (
            QPropertyAnimation(
                self._effect,
                b"opacity",
            )
        )

        self._animation.setDuration(
            220
        )

        self._animation.setStartValue(
            0.0
        )

        self._animation.setEndValue(
            1.0
        )

        self._animation.setEasingCurve(
            QEasingCurve.OutCubic
        )

        self._animation.start()

    # ======================================================
    # WIDTH
    # ======================================================

    def set_max_bubble_width(
        self,
        width: int,
    ):

        self.bubble.set_max_bubble_width(
            width
        )