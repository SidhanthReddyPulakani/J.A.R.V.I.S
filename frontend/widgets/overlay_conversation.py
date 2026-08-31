from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QSizePolicy,
)

import frontend.theme as theme

from frontend.widgets.overlay_message import (
    OverlayMessageRow,
)

from frontend.widgets.overlay_typing_indicator import (
    OverlayTypingIndicator,
)


class OverlayConversationView(QScrollArea):
    """
    Conversation history specifically for OverlayWindow.

    This is intentionally independent from MainWindow's
    ConversationView.
    """

    def __init__(
        self,
        parent=None,
        bubble_max_width: int = 360,
    ):
        super().__init__(
            parent
        )

        self.bubble_max_width = (
            bubble_max_width
        )

        # ==================================================
        # SCROLL AREA
        # ==================================================

        self.setWidgetResizable(
            True
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.setFrameShape(
            QScrollArea.NoFrame
        )

        self.setStyleSheet(
            theme.scrollbar_qss(
                "QScrollArea"
            )
        )

        # ==================================================
        # CONTENT
        # ==================================================

        self._content = QWidget()

        self._content.setStyleSheet(
            "background: transparent;"
        )

        self._content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        self._layout = QVBoxLayout(
            self._content
        )

        self._layout.setContentsMargins(
            6,
            6,
            6,
            6,
        )

        self._layout.setSpacing(
            2
        )

        self._layout.addStretch(
            1
        )

        self.setWidget(
            self._content
        )

        # ==================================================
        # STATE
        # ==================================================

        self._rows = []

        self._typing = (
            OverlayTypingIndicator()
        )

        self._typing_visible = False

    # ======================================================
    # HISTORY
    # ======================================================

    def add_exchange(
        self,
        query: str,
        response: str,
        is_error: bool = False,
    ):
        """
        Append the user message followed by the
        assistant response.
        """

        if query:

            self._add_row(
                query,
                role="user",
            )

        if response:

            self._add_row(
                response,
                role=(
                    "error"
                    if is_error
                    else "assistant"
                ),
            )

    def _add_row(
        self,
        text: str,
        role: str,
    ):

        row = OverlayMessageRow(
            text,
            role=role,
        )

        row.set_max_bubble_width(
            self.bubble_max_width
        )

        self._layout.insertWidget(
            self._layout.count() - 1,
            row,
        )

        self._rows.append(
            row
        )

        self._scroll_to_bottom()

    # ======================================================
    # CLEAR
    # ======================================================

    def clear(self):

        for row in self._rows:

            self._layout.removeWidget(
                row
            )

            row.deleteLater()

        self._rows.clear()

    # ======================================================
    # TYPING
    # ======================================================

    def set_thinking(
        self,
        thinking: bool,
    ):

        if (
            thinking
            and not self._typing_visible
        ):

            self._layout.insertWidget(
                self._layout.count() - 1,
                self._typing,
            )

            self._typing.start()

            self._typing_visible = True

            self._scroll_to_bottom()

        elif (
            not thinking
            and self._typing_visible
        ):

            self._typing.stop()

            self._layout.removeWidget(
                self._typing
            )

            self._typing.setParent(
                None
            )

            self._typing_visible = False

    # ======================================================
    # SCROLL
    # ======================================================

    def _scroll_to_bottom(self):

        QTimer.singleShot(
            0,
            self._do_scroll_to_bottom,
        )

    def _do_scroll_to_bottom(self):

        bar = self.verticalScrollBar()

        bar.setValue(
            bar.maximum()
        )

    # ======================================================
    # RESPONSIVE WIDTH
    # ======================================================

    def set_bubble_max_width(
        self,
        width: int,
    ):

        self.bubble_max_width = (
            width
        )

        for row in self._rows:

            row.set_max_bubble_width(
                width
            )

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        target = max(
            220,
            min(
                self.viewport().width() - 24,
                640,
            ),
        )

        self.set_bubble_max_width(
            target
        )