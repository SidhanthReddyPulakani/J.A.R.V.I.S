import sys

from PySide6.QtCore import Qt, QPoint
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


class MainWindow(QWidget):
    """
    Jarvis as a persistent desktop widget.

    Sits on the desktop like a sticky note / gadget: frameless,
    translucent, draggable by its header, resizable from the
    corner, and stays behind normal application windows once
    shown (see configure_desktop_window / put_on_desktop).

    Everything below the header is managed by real layouts, so
    resizing the widget just works instead of requiring manual
    geometry math.
    """

    MIN_WIDTH = 320
    MIN_HEIGHT = 260

    DEFAULT_WIDTH = 400
    DEFAULT_HEIGHT = 560

    def __init__(self, parent=None):
        super().__init__(parent)

        # ==================================================
        # WINDOW
        # ==================================================

        self.setWindowTitle("Jarvis")

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool
        )

        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        # ==================================================
        # STATE
        # ==================================================

        self.jarvis_controller = None
        self.pending_query = ""

        self._drag_offset = None

        # ==================================================
        # ROOT LAYOUT
        # ==================================================

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        # --------------------------------------------------
        # Header (drag handle + title + status + hide)
        # --------------------------------------------------

        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        header.setSpacing(8)

        self._header_widget = QWidget()
        self._header_widget.setLayout(header)
        self._header_widget.setCursor(Qt.SizeAllCursor)

        title = QLabel("JARVIS")
        title_font = QFont(theme.FONT_FAMILY, theme.SIZE_TITLE)
        title_font.setLetterSpacing(QFont.PercentageSpacing, 115)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(
            f"color: {theme.rgba(theme.TEXT_SECONDARY)}; background: transparent;"
        )

        self.hide_button = QToolButton()
        self.hide_button.setText("—")
        self.hide_button.setCursor(Qt.PointingHandCursor)
        self.hide_button.setFixedSize(24, 24)
        self.hide_button.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                border: none;
                color: {theme.rgba(theme.TEXT_SECONDARY)};
                font-size: 14px;
                border-radius: 12px;
            }}
            QToolButton:hover {{
                background: rgba(255, 255, 255, 25);
                color: {theme.rgba(theme.TEXT_PRIMARY)};
            }}
            """
        )
        self.hide_button.clicked.connect(self.hide)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.hide_button)

        root.addWidget(self._header_widget)

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        self.conversation = ConversationView()
        self.conversation.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        root.addWidget(self.conversation, 1)

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        self.search_bar = SearchBar()
        self.search_bar.submitted.connect(self.send_to_backend)

        root.addWidget(self.search_bar)

        # --------------------------------------------------
        # Resize grip (bottom-right, floats above layout)
        # --------------------------------------------------

        self.resize_grip = ResizeGrip(self, parent=self)

        # ==================================================
        # DESKTOP POSITION
        # ==================================================

        self.move_to_desktop()

    # ======================================================
    # RESIZE / GRIP POSITIONING
    # ======================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.resize_grip.move(
            self.width() - self.resize_grip.width() - 4,
            self.height() - self.resize_grip.height() - 4,
        )

        self.resize_grip.raise_()

    # ======================================================
    # DRAG TO MOVE (via header)
    # ======================================================

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton and self._header_widget.underMouse():
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):

        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    # ======================================================
    # DESKTOP POSITION
    # ======================================================

    def move_to_desktop(self):

        screen = self.screen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        x = geometry.left() + geometry.width() - self.width() - 40
        y = geometry.top() + 60

        self.move(x, y)

    # ======================================================
    # DESKTOP WINDOW STYLE (Windows-only)
    # ======================================================

    def configure_desktop_window(self):

        if sys.platform != "win32":
            return

        import ctypes

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32

        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        # Keep it out of Alt+Tab/taskbar, like a desktop gadget.
        ex_style &= ~WS_EX_APPWINDOW
        ex_style |= WS_EX_TOOLWINDOW

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

    def put_on_desktop(self):

        if sys.platform != "win32":
            return

        import ctypes

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32

        HWND_BOTTOM = 1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010

        user32.SetWindowPos(
            hwnd, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
        )

    # ======================================================
    # SHOW
    # ======================================================

    def showEvent(self, event):

        super().showEvent(event)

        self.configure_desktop_window()
        self.put_on_desktop()

        self.search_bar.input.setFocus()

    # ======================================================
    # CONTROLLER
    # ======================================================

    def set_controller(self, controller):
        self.jarvis_controller = controller

    # ======================================================
    # USER -> CONTROLLER
    # ======================================================

    def send_to_backend(self, text):

        if not text:
            return

        if self.jarvis_controller is None:
            self.on_error(text, "Jarvis controller is not connected.")
            return

        self.pending_query = text
        self.jarvis_controller.ask(text)

    # ======================================================
    # CONTROLLER -> UI
    # ======================================================

    def on_response(self, query, response):

        if not query:
            query = self.pending_query

        self.conversation.set_thinking(False)
        self.conversation.add_exchange(query, response)
        self.pending_query = ""

    def on_error(self, query, error):

        if not query:
            query = self.pending_query

        self.conversation.set_thinking(False)
        self.conversation.add_exchange(query, f"Backend error: {error}", is_error=True)
        self.pending_query = ""

    def on_busy_changed(self, busy):

        self.search_bar.set_busy(busy)
        self.conversation.set_thinking(busy)

    def on_backend_state_changed(self, enabled: bool):
        """
        Reflects whether the Jarvis backend is running, without
        ever hiding this window. The widget is meant to stay on
        the desktop at all times; only its input state changes.
        """

        self.conversation.set_thinking(False)
        self.search_bar.set_offline(not enabled)

    # ======================================================
    # PAINT (rounded glass panel)
    # ======================================================

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # Fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(*theme.PANEL_BG)))
        painter.drawRoundedRect(rect, theme.RADIUS_PANEL, theme.RADIUS_PANEL)

        # Hairline border
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*theme.PANEL_BORDER), 1))
        painter.drawRoundedRect(rect, theme.RADIUS_PANEL, theme.RADIUS_PANEL)

    # ======================================================
    # CLOSE
    # ======================================================

    def closeEvent(self, event):

        if self.jarvis_controller is not None:
            self.jarvis_controller.stop()

        event.accept()
