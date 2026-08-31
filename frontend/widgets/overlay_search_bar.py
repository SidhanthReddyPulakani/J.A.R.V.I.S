from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QToolButton,
)

import frontend.theme as theme


class OverlayStatusDot(QLabel):
    """
    Status indicator belonging exclusively to OverlaySearchBar.
    """

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.setFixedSize(
            9,
            9,
        )

        self._state = "idle"

        self._paint()

    def set_state(
        self,
        state: str,
    ):

        self._state = state

        self._paint()

    def _paint(self):

        colors = {
            "idle": theme.STATUS_IDLE,
            "busy": theme.STATUS_BUSY,
            "offline": theme.STATUS_OFFLINE,
        }

        color = colors.get(
            self._state,
            theme.STATUS_IDLE,
        )

        self.setStyleSheet(
            f"""
            background-color:
                {theme.rgba(color)};

            border-radius:
                4px;
            """
        )


class OverlaySearchBar(QWidget):
    """
    Search/input bar used exclusively by OverlayWindow.
    """

    submitted = Signal(str)

    HEIGHT = 52

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.setObjectName(
            "overlaySearchBar"
        )

        self.setFixedHeight(
            self.HEIGHT
        )

        self._busy = False
        self._offline = False

        # ==================================================
        # LAYOUT
        # ==================================================

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            18,
            0,
            10,
            0,
        )

        layout.setSpacing(
            12
        )

        # ==================================================
        # STATUS
        # ==================================================

        self.status_dot = (
            OverlayStatusDot()
        )

        # ==================================================
        # INPUT
        # ==================================================

        self.input = QLineEdit()

        self.input.setPlaceholderText(
            "Ask Jarvis anything..."
        )

        self.input.setObjectName(
            "overlaySearchInput"
        )

        font = QFont(
            theme.FONT_FAMILY_LIGHT
        )

        font.setPointSize(
            theme.SIZE_INPUT
        )

        self.input.setFont(
            font
        )

        self.input.returnPressed.connect(
            self.submit
        )

        # ==================================================
        # SEND
        # ==================================================

        self.send_button = QToolButton()

        self.send_button.setText(
            "➤"
        )

        self.send_button.setObjectName(
            "overlaySendButton"
        )

        self.send_button.setCursor(
            Qt.PointingHandCursor
        )

        self.send_button.setFixedSize(
            32,
            32,
        )

        self.send_button.clicked.connect(
            self.submit
        )

        # ==================================================
        # LAYOUT
        # ==================================================

        layout.addWidget(
            self.status_dot
        )

        layout.addWidget(
            self.input,
            1,
        )

        layout.addWidget(
            self.send_button
        )

        self._apply_style()

        # ==================================================
        # SHADOW
        # ==================================================

        self._shadow = (
            QGraphicsDropShadowEffect(
                self
            )
        )

        self._shadow.setOffset(
            0,
            4,
        )

        self._shadow.setBlurRadius(
            22
        )

        self._shadow.setColor(
            Qt.black
        )

        self.setGraphicsEffect(
            self._shadow
        )

        self.input.installEventFilter(
            self
        )

    # ======================================================
    # STYLE
    # ======================================================

    def _apply_style(self):

        self.setStyleSheet(
            f"""
            QWidget#overlaySearchBar {{
                background:
                    rgba(255, 255, 255, 20);

                border:
                    1px solid
                    rgba(255, 255, 255, 35);

                border-radius:
                    {theme.RADIUS_PILL}px;
            }}

            QLineEdit#overlaySearchInput {{
                background:
                    transparent;

                border:
                    none;

                color:
                    {theme.rgba(
                        theme.TEXT_PRIMARY
                    )};

                padding:
                    0;
            }}

            QLineEdit#overlaySearchInput::placeholder {{
                color:
                    {theme.rgba(
                        theme.TEXT_SECONDARY
                    )};
            }}

            QToolButton#overlaySendButton {{
                background:
                    {theme.rgba(
                        theme.ACCENT_SOFT
                    )};

                border:
                    none;

                border-radius:
                    16px;

                color:
                    {theme.rgba(
                        theme.ACCENT_STRONG
                    )};

                font-size:
                    13px;
            }}

            QToolButton#overlaySendButton:hover {{
                background:
                    {theme.rgba(
                        (
                            theme.ACCENT[0],
                            theme.ACCENT[1],
                            theme.ACCENT[2],
                            75,
                        )
                    )};
            }}

            QToolButton#overlaySendButton:disabled {{
                color:
                    {theme.rgba(
                        theme.TEXT_MUTED
                    )};

                background:
                    rgba(
                        255,
                        255,
                        255,
                        10
                    );
            }}
            """
        )

    # ======================================================
    # FOCUS
    # ======================================================

    def eventFilter(
        self,
        obj,
        event,
    ):

        if obj is self.input:

            if (
                event.type()
                == event.Type.FocusIn
            ):

                self._shadow.setBlurRadius(
                    32
                )

            elif (
                event.type()
                == event.Type.FocusOut
            ):

                self._shadow.setBlurRadius(
                    22
                )

        return super().eventFilter(
            obj,
            event,
        )

    # ======================================================
    # SUBMIT
    # ======================================================

    def submit(self):

        if (
            self._busy
            or self._offline
        ):
            return

        text = (
            self.input
            .text()
            .strip()
        )

        if not text:
            return

        self.submitted.emit(
            text
        )

        self.input.clear()

    # ======================================================
    # BUSY
    # ======================================================

    def set_busy(
        self,
        busy: bool,
    ):

        if self._offline:
            return

        self._busy = busy

        self.status_dot.set_state(
            "busy"
            if busy
            else "idle"
        )

        self.send_button.setEnabled(
            not busy
        )

        if busy:

            self.input.setPlaceholderText(
                "Jarvis is thinking..."
            )

            self.input.setEnabled(
                False
            )

        else:

            self.input.setPlaceholderText(
                "Ask Jarvis anything..."
            )

            self.input.setEnabled(
                True
            )

            self.input.setFocus()

    # ======================================================
    # OFFLINE
    # ======================================================

    def set_offline(
        self,
        offline: bool,
    ):

        self._offline = offline
        self._busy = False

        if offline:

            self.status_dot.set_state(
                "offline"
            )

            self.input.setPlaceholderText(
                "Jarvis is offline"
            )

            self.input.setEnabled(
                False
            )

            self.send_button.setEnabled(
                False
            )

        else:

            self.status_dot.set_state(
                "idle"
            )

            self.input.setPlaceholderText(
                "Ask Jarvis anything..."
            )

            self.input.setEnabled(
                True
            )

            self.send_button.setEnabled(
                True
            )

            self.input.setFocus()