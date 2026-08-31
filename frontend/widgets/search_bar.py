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


class StatusDot(QLabel):
    """
    Small JARVIS status indicator.
    """

    def __init__(self, parent=None):

        super().__init__(
            parent
        )

        self.setFixedSize(
            10,
            10,
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
                5px;
            """
        )


class SearchBar(QWidget):
    """
    Persistent JARVIS input bar.

    This widget is always directly below the conversation
    panel. The conversation grows upward from it.
    """

    submitted = Signal(str)

    HEIGHT = 68

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setObjectName(
            "searchBar"
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
            24,
            0,
            12,
            0,
        )

        layout.setSpacing(
            16
        )

        # ==================================================
        # STATUS
        # ==================================================

        self.status_dot = StatusDot()

        # ==================================================
        # INPUT
        # ==================================================

        self.input = QLineEdit()

        self.input.setObjectName(
            "searchInput"
        )

        self.input.setPlaceholderText(
            "Ask Jarvis anything..."
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

        self.input.setFrame(
            False
        )

        self.input.returnPressed.connect(
            self.submit
        )

        # ==================================================
        # SEND
        # ==================================================

        self.send_button = QToolButton()

        self.send_button.setText(
            "➜"
        )

        self.send_button.setObjectName(
            "sendButton"
        )

        self.send_button.setCursor(
            Qt.PointingHandCursor
        )

        self.send_button.setFixedSize(
            42,
            42,
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

        # ==================================================
        # STYLE
        # ==================================================

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
            8,
        )

        self._shadow.setBlurRadius(
            36
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
            QWidget#searchBar {{
                background:
                    rgba(255, 255, 255, 24);

                border:
                    1px solid rgba(255, 255, 255, 52);

                border-radius:
                    {self.HEIGHT // 2}px;
            }}

            QLineEdit#searchInput {{
                background:
                    transparent;

                border:
                    none;

                color:
                    {theme.rgba(theme.TEXT_PRIMARY)};

                padding:
                    0px;
            }}

            QLineEdit#searchInput::placeholder {{
                color:
                    {theme.rgba(theme.TEXT_SECONDARY)};
            }}

            QToolButton#sendButton {{
                background:
                    {theme.rgba(theme.ACCENT_SOFT)};

                border:
                    none;

                border-radius:
                    21px;

                color:
                    {theme.rgba(theme.ACCENT_STRONG)};

                font-size:
                    22px;

                font-weight:
                    400;
            }}

            QToolButton#sendButton:hover {{
                background:
                    rgba(
                        {theme.ACCENT[0]},
                        {theme.ACCENT[1]},
                        {theme.ACCENT[2]},
                        85
                    );
            }}

            QToolButton#sendButton:disabled {{
                color:
                    {theme.rgba(theme.TEXT_MUTED)};

                background:
                    rgba(255, 255, 255, 12);
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
                    48
                )

            elif (
                event.type()
                == event.Type.FocusOut
            ):

                self._shadow.setBlurRadius(
                    36
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