from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
)
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QSizePolicy,
)

import frontend.theme as theme
from frontend.widgets.message import MessageRow
from frontend.widgets.typing_indicator import TypingIndicator


class ConversationView(QScrollArea):
    """
    Dynamic JARVIS conversation panel.

    Behavior:

        - Starts at zero height.
        - Grows upward as messages are added.
        - Remains directly above the SearchBar.
        - Has zero external spacing.
        - Stops growing at max_height.
        - Once max_height is reached, the contents scroll.
        - Newest content is automatically brought into view.
    """

    height_changed = Signal(int)

    MIN_HEIGHT = 0

    CONTENT_MARGIN_LEFT = 18
    CONTENT_MARGIN_TOP = 14
    CONTENT_MARGIN_RIGHT = 18
    CONTENT_MARGIN_BOTTOM = 14

    def __init__(
        self,
        parent=None,
        bubble_max_width=760,
    ):
        super().__init__(parent)

        self.bubble_max_width = (
            bubble_max_width
        )

        self._max_height = 600
        self._rows = []

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

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        self.viewport().setAttribute(
            Qt.WA_TranslucentBackground
        )

        # ==================================================
        # CONTENT
        # ==================================================

        self._content = QWidget()

        self._content.setAttribute(
            Qt.WA_TranslucentBackground
        )

        self._content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        self._layout = QVBoxLayout(
            self._content
        )

        self._layout.setContentsMargins(
            self.CONTENT_MARGIN_LEFT,
            self.CONTENT_MARGIN_TOP,
            self.CONTENT_MARGIN_RIGHT,
            self.CONTENT_MARGIN_BOTTOM,
        )

        self._layout.setSpacing(
            2
        )

        self._layout.setSizeConstraint(
            QVBoxLayout.SetMinAndMaxSize
        )

        self._layout.addStretch(
            1
        )

        self.setWidget(
            self._content
        )

        # ==================================================
        # TYPING
        # ==================================================

        self._typing = TypingIndicator()

        self._typing_visible = False

    # ======================================================
    # MAX HEIGHT
    # ======================================================

    def set_max_height(
        self,
        height: int,
    ):

        self._max_height = max(
            self.MIN_HEIGHT,
            int(height),
        )

        self._refresh_height()

    # ======================================================
    # ADD EXCHANGE
    # ======================================================

    def add_exchange(
        self,
        query: str,
        response: str,
        is_error: bool = False,
    ):

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

        self._schedule_refresh()

    # ======================================================
    # ADD ROW
    # ======================================================

    def _add_row(
        self,
        text: str,
        role: str,
    ):

        row = MessageRow(
            text,
            role=role,
        )

        row.set_max_bubble_width(
            self.bubble_max_width
        )

        # Insert before the permanent stretch.
        self._layout.insertWidget(
            self._layout.count() - 1,
            row,
        )

        self._rows.append(
            row
        )

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

        self._schedule_refresh()

    # ======================================================
    # THINKING
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

            self._schedule_refresh()

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

            self._schedule_refresh()

    # ======================================================
    # HEIGHT CALCULATION
    # ======================================================

    def _schedule_refresh(self):

        QTimer.singleShot(
            0,
            self._refresh_height,
        )

    def _refresh_height(self):

        # Let Qt finish geometry/layout calculations first.
        self._layout.activate()

        self._content.adjustSize()

        self._layout.activate()

        content_height = (
            self._layout.sizeHint().height()
        )

        # No content means no visible conversation panel.
        has_content = bool(
            self._rows
            or self._typing_visible
        )

        if not has_content:

            desired = 0

        else:

            desired = min(
                content_height,
                self._max_height,
            )

        # Avoid unnecessary geometry churn.
        if (
            desired != self.height()
            or (
                desired == 0
                and self.isVisible()
            )
        ):

            self.setFixedHeight(
                desired
            )

        self.height_changed.emit(
            desired
        )

        # Always keep the newest message visible.
        if has_content:

            self._scroll_to_bottom()

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
    # BUBBLE WIDTH
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

        self._schedule_refresh()

    # ======================================================
    # RESIZE
    # ======================================================

    def resizeEvent(self, event):

        super().resizeEvent(
            event
        )

        target = max(
            220,
            min(
                self.viewport().width() - 36,
                760,
            ),
        )

        self.set_bubble_max_width(
            target
        )

        self._schedule_refresh()

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
            1,
            1,
            -1,
            -1,
        )

        # Glass body
        painter.setPen(
            Qt.NoPen
        )

        painter.setBrush(
            QBrush(
                QColor(
                    15,
                    20,
                    28,
                    175,
                )
            )
        )

        painter.drawRoundedRect(
            rect,
            theme.RADIUS_PANEL,
            theme.RADIUS_PANEL,
        )

        # Hairline border
        painter.setBrush(
            Qt.NoBrush
        )

        painter.setPen(
            QPen(
                QColor(
                    255,
                    255,
                    255,
                    32,
                ),
                1,
            )
        )

        painter.drawRoundedRect(
            rect,
            theme.RADIUS_PANEL,
            theme.RADIUS_PANEL,
        )

        super().paintEvent(
            event
        )