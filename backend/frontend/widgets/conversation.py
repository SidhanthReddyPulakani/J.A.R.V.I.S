from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QSizePolicy,
)

import backend.frontend.theme as theme
from backend.frontend.widgets.message import MessageRow
from backend.frontend.widgets.typing_indicator import TypingIndicator


class ConversationView(QScrollArea):
    """
    Scrollable, unbounded chat history.

    Replaces the old fixed-5-slot ConversationStack (main window)
    and the separate newest-fit OverlayConversation (overlay) with
    one implementation: real scrolling, unlimited history, smooth
    auto-scroll to the newest message, and a typing indicator while
    the backend is thinking.
    """

    def __init__(self, parent=None, bubble_max_width: int = 560):
        super().__init__(parent)

        self.bubble_max_width = bubble_max_width

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet(theme.scrollbar_qss("QScrollArea"))

        # --------------------------------------------------
        # Inner content column
        # --------------------------------------------------

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)

        self.setWidget(self._content)

        self._rows = []

        self._typing = TypingIndicator()
        self._typing_visible = False

    # ------------------------------------------------------
    # HISTORY
    # ------------------------------------------------------

    def add_exchange(self, query: str, response: str, is_error: bool = False):
        """Append a user message followed by the assistant's reply."""

        if query:
            self._add_row(query, role="user")

        if response:
            self._add_row(response, role=("error" if is_error else "assistant"))

    def _add_row(self, text: str, role: str):

        row = MessageRow(text, role=role)
        row.set_max_bubble_width(self.bubble_max_width)

        # Insert before the trailing stretch.
        self._layout.insertWidget(self._layout.count() - 1, row)

        self._rows.append(row)

        self._scroll_to_bottom()

    def clear(self):

        for row in self._rows:
            self._layout.removeWidget(row)
            row.deleteLater()

        self._rows.clear()

    # ------------------------------------------------------
    # TYPING INDICATOR
    # ------------------------------------------------------

    def set_thinking(self, thinking: bool):

        if thinking and not self._typing_visible:

            self._layout.insertWidget(
                self._layout.count() - 1,
                self._typing,
            )

            self._typing.start()
            self._typing_visible = True
            self._scroll_to_bottom()

        elif not thinking and self._typing_visible:

            self._typing.stop()
            self._layout.removeWidget(self._typing)
            self._typing.setParent(None)
            self._typing_visible = False

    # ------------------------------------------------------
    # SCROLL
    # ------------------------------------------------------

    def _scroll_to_bottom(self):

        # Deferred: layout needs a pass before the scrollbar
        # range reflects the newly added widget.
        QTimer.singleShot(0, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self):

        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------
    # RESPONSIVE BUBBLE WIDTH
    # ------------------------------------------------------

    def set_bubble_max_width(self, width: int):

        self.bubble_max_width = width

        for row in self._rows:
            row.set_max_bubble_width(width)

    def resizeEvent(self, event):

        super().resizeEvent(event)

        # Keep bubbles from stretching edge-to-edge on wide windows.
        target = max(220, min(self.viewport().width() - 24, 640))
        self.set_bubble_max_width(target)
