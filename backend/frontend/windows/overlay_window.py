from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QSizePolicy,
)

import backend.frontend.theme as theme
from backend.frontend.widgets.search_bar import SearchBar
from backend.frontend.widgets.conversation import ConversationView
from backend.frontend.widgets.resize_grip import ResizeGrip


class OverlayWindow(QWidget):
    """
    Quick-access popup, toggled by the global hotkey (Ctrl+Alt+J).

    Reuses the same SearchBar / ConversationView components as the
    persistent desktop widget so the two surfaces look and behave
    identically instead of maintaining two parallel implementations.

    Unlike the old version, this is resizable (drag the bottom-right
    corner, same grip MainWindow uses) so a long reply has somewhere
    to go instead of being stuck in a box that can never grow. It
    stays anchored to the bottom-right corner of the screen as it
    resizes, since that's where a hotkey popup is expected to live.
    """

    request_submitted = Signal(str)

    MIN_WIDTH = 360
    MIN_HEIGHT = 320

    DEFAULT_WIDTH = 460
    DEFAULT_HEIGHT = 620

    RIGHT_MARGIN = 28
    BOTTOM_MARGIN = 28

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Jarvis Overlay")

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self.jarvis_controller = None
        self.pending_query = ""

        # ==================================================
        # ROOT LAYOUT
        # ==================================================

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        # --------------------------------------------------
        # Header (title + close) — mirrors MainWindow so the
        # two surfaces read as one product, and gives the
        # popup an explicit, discoverable way to dismiss
        # itself besides the hotkey.
        # --------------------------------------------------

        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        header.setSpacing(8)

        title = QLabel("JARVIS")
        title_font = QFont(theme.FONT_FAMILY, theme.SIZE_TITLE)
        title_font.setLetterSpacing(QFont.PercentageSpacing, 115)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(
            f"color: {theme.rgba(theme.TEXT_SECONDARY)}; background: transparent;"
        )

        self.close_button = QToolButton()
        self.close_button.setText("✕")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                border: none;
                color: {theme.rgba(theme.TEXT_SECONDARY)};
                font-size: 12px;
                border-radius: 12px;
            }}
            QToolButton:hover {{
                background: rgba(255, 255, 255, 25);
                color: {theme.rgba(theme.TEXT_PRIMARY)};
            }}
            """
        )
        self.close_button.clicked.connect(self.hide_overlay)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.close_button)

        root.addLayout(header)

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        self.conversation = ConversationView(bubble_max_width=360)
        self.conversation.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        root.addWidget(self.conversation, 1)

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        self.search_bar = SearchBar()
        self.search_bar.submitted.connect(self._submit)

        root.addWidget(self.search_bar)

        # --------------------------------------------------
        # Resize grip (bottom-right, floats above layout) —
        # same widget MainWindow uses, so behavior/feel match.
        # --------------------------------------------------

        self.resize_grip = ResizeGrip(self, parent=self)

        self.move_to_bottom_right()

    # ======================================================
    # RESIZE / GRIP POSITIONING
    #
    # Repositions on every resize so the window's bottom-right
    # corner stays anchored to the same screen corner as it
    # grows or shrinks, instead of drifting toward the center
    # of the screen the way a naive resize would.
    # ======================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.resize_grip.move(
            self.width() - self.resize_grip.width() - 4,
            self.height() - self.resize_grip.height() - 4,
        )

        self.resize_grip.raise_()

        self.move_to_bottom_right()

    # ======================================================
    # CONTROLLER
    # ======================================================

    def set_controller(self, controller):
        self.jarvis_controller = controller

    # ======================================================
    # SUBMIT
    # ======================================================

    def _submit(self, text):

        if not text:
            return

        self.pending_query = text
        self.request_submitted.emit(text)

        if self.jarvis_controller is None:
            self.on_error(text, "Jarvis controller is not connected.")
            return

        self.jarvis_controller.ask(text)

    # ======================================================
    # RESPONSE / ERROR / BUSY
    # ======================================================

    def on_response(self, query, response):

        self.conversation.set_thinking(False)
        self.conversation.add_exchange(query, response)
        self.pending_query = ""

    def on_error(self, query, error):

        self.conversation.set_thinking(False)
        self.conversation.add_exchange(query, f"Backend error: {error}", is_error=True)
        self.pending_query = ""

    def on_busy_changed(self, busy):

        self.search_bar.set_busy(busy)
        self.conversation.set_thinking(busy)

    def on_backend_state_changed(self, enabled: bool):
        """Reflects backend state without changing overlay visibility."""

        self.conversation.set_thinking(False)
        self.search_bar.set_offline(not enabled)

    # ======================================================
    # POSITION
    # ======================================================

    def move_to_bottom_right(self):

        screen = self.screen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        x = geometry.right() - self.width() - self.RIGHT_MARGIN
        y = geometry.bottom() - self.height() - self.BOTTOM_MARGIN

        self.move(x, y)

    # ======================================================
    # SHOW / HIDE / TOGGLE
    # ======================================================

    def show_overlay(self):

        self.move_to_bottom_right()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_bar.input.setFocus()

    def hide_overlay(self):
        self.hide()

    def toggle(self):

        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    # ======================================================
    # ESCAPE TO DISMISS
    # ======================================================

    def keyPressEvent(self, event):

        if event.key() == Qt.Key_Escape:
            self.hide_overlay()
            return

        super().keyPressEvent(event)

    # ======================================================
    # PAINT (rounded glass panel, matches MainWindow)
    # ======================================================

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(*theme.PANEL_BG)))
        painter.drawRoundedRect(rect, theme.RADIUS_PANEL, theme.RADIUS_PANEL)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*theme.PANEL_BORDER), 1))
        painter.drawRoundedRect(rect, theme.RADIUS_PANEL, theme.RADIUS_PANEL)