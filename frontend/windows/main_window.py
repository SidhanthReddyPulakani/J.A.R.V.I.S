import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSizePolicy,
)

import frontend.theme as theme
from frontend.widgets.search_bar import SearchBar
from frontend.widgets.conversation import ConversationView


class MainWindow(QWidget):
    """
    Persistent JARVIS desktop interface.

    Layout:

        ┌──────────────────────────────────────┐
        │                                      │
        │          conversation panel          │
        │                                      │
        └──────────────────────────────────────┘
        ┌──────────────────────────────────────┐
        │   ●   Ask Jarvis anything...      →  │
        └──────────────────────────────────────┘

    The search bar is the fixed anchor.

    The conversation panel grows upward from the search bar.
    There is intentionally ZERO spacing between them.

    The window itself is a transparent desktop layer. Only the
    actual JARVIS controls receive/paint visible content.
    """

    SEARCH_WIDTH_RATIO = 0.76
    SEARCH_MAX_WIDTH = 1180
    SEARCH_HEIGHT = 68

    CONVERSATION_WIDTH_RATIO = 0.76
    CONVERSATION_MAX_WIDTH = 1180

    MAX_CONVERSATION_RATIO = 0.64

    SIDE_MARGIN = 40
    BOTTOM_MARGIN = 72

    def __init__(self, parent=None):
        super().__init__(parent)

        # ==================================================
        # WINDOW
        # ==================================================

        self.setWindowTitle("Jarvis")

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        # This window acts as a desktop fixture.
        self.setMinimumSize(1, 1)

        # ==================================================
        # STATE
        # ==================================================

        self.jarvis_controller = None
        self.pending_query = ""

        self.overlay = None
        self.hotkeys = None
        self.tray = None

        # ==================================================
        # ROOT LAYOUT
        # ==================================================

        self.root = QVBoxLayout(self)

        self.root.setContentsMargins(
            self.SIDE_MARGIN,
            0,
            self.SIDE_MARGIN,
            self.BOTTOM_MARGIN,
        )

        # IMPORTANT:
        #
        # There is NO spacing between conversation and search.
        #
        self.root.setSpacing(0)

        # --------------------------------------------------
        # Top spacer
        #
        # This forces the UI group to remain anchored to the
        # bottom of the screen.
        # --------------------------------------------------

        self.root.addStretch(1)

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        self.conversation = ConversationView()

        self.conversation.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        self.conversation.setVisible(False)

        self.root.addWidget(
            self.conversation,
            0,
            Qt.AlignHCenter,
        )

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        self.search_bar = SearchBar()

        self.search_bar.setFixedHeight(
            self.SEARCH_HEIGHT
        )

        self.search_bar.submitted.connect(
            self.send_to_backend
        )

        self.root.addWidget(
            self.search_bar,
            0,
            Qt.AlignHCenter,
        )

        # ==================================================
        # CONVERSATION HEIGHT SIGNAL
        # ==================================================

        self.conversation.height_changed.connect(
            self._on_conversation_height_changed
        )

        # ==================================================
        # INITIAL GEOMETRY
        # ==================================================

        self._update_widths()

    # ======================================================
    # SHOW
    # ======================================================

    def showEvent(self, event):

        super().showEvent(event)

        self._resize_to_screen()
        self._update_widths()

        self.configure_desktop_window()
        self.put_on_desktop()

        self.search_bar.input.setFocus()

    # ======================================================
    # RESIZE
    # ======================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self._update_widths()

        self._update_conversation_limit()

    # ======================================================
    # SCREEN GEOMETRY
    # ======================================================

    def _resize_to_screen(self):

        screen = self.screen()

        if screen is None:
            return

        geometry = screen.geometry()

        self.setGeometry(
            geometry
        )

    # ======================================================
    # WIDTHS
    # ======================================================

    def _update_widths(self):

        width = self.width()

        if width <= 1:
            return

        search_width = min(
            int(width * self.SEARCH_WIDTH_RATIO),
            self.SEARCH_MAX_WIDTH,
        )

        conversation_width = min(
            int(width * self.CONVERSATION_WIDTH_RATIO),
            self.CONVERSATION_MAX_WIDTH,
        )

        search_width = max(
            420,
            search_width,
        )

        conversation_width = max(
            420,
            conversation_width,
        )

        self.search_bar.setFixedWidth(
            search_width
        )

        self.conversation.setFixedWidth(
            conversation_width
        )

        self._update_conversation_limit()

    # ======================================================
    # CONVERSATION HEIGHT LIMIT
    # ======================================================

    def _update_conversation_limit(self):

        screen = self.screen()

        if screen is None:
            return

        height = screen.availableGeometry().height()

        maximum = int(
            height * self.MAX_CONVERSATION_RATIO
        )

        self.conversation.set_max_height(
            maximum
        )

    # ======================================================
    # CONVERSATION HEIGHT
    # ======================================================

    def _on_conversation_height_changed(
        self,
        height: int,
    ):

        if height <= 0:

            self.conversation.setVisible(
                False
            )

            return

        self.conversation.setVisible(
            True
        )

        self.conversation.setFixedHeight(
            height
        )

        self.root.activate()

    # ======================================================
    # USER -> CONTROLLER
    # ======================================================

    def send_to_backend(self, text):

        if not text:
            return

        if self.jarvis_controller is None:

            self.on_error(
                text,
                "Jarvis controller is not connected.",
            )

            return

        self.pending_query = text

        # Show the conversation immediately so the user's
        # message appears above the search bar.
        self.conversation.setVisible(
            True
        )

        self.jarvis_controller.ask(
            text
        )

    # ======================================================
    # CONTROLLER -> UI
    # ======================================================

    def on_response(
        self,
        query,
        response,
    ):

        if not query:
            query = self.pending_query

        self.conversation.set_thinking(
            False
        )

        self.conversation.add_exchange(
            query,
            response,
        )

        self.pending_query = ""

    def on_error(
        self,
        query,
        error,
    ):

        if not query:
            query = self.pending_query

        self.conversation.set_thinking(
            False
        )

        self.conversation.add_exchange(
            query,
            f"Backend error: {error}",
            is_error=True,
        )

        self.pending_query = ""

    def on_busy_changed(
        self,
        busy,
    ):

        self.search_bar.set_busy(
            busy
        )

        self.conversation.set_thinking(
            busy
        )

    def on_backend_state_changed(
        self,
        enabled: bool,
    ):

        self.conversation.set_thinking(
            False
        )

        self.search_bar.set_offline(
            not enabled
        )

    # ======================================================
    # CONTROLLER
    # ======================================================

    def set_controller(
        self,
        controller,
    ):

        self.jarvis_controller = controller

    # ======================================================
    # INTERFACE TOGGLE
    # ======================================================

    def toggle_interface(self):

        if self.isVisible():

            self.hide()

        else:

            self.show()
            self.raise_()
            self.activateWindow()
            self.search_bar.input.setFocus()

    def show_interface(self):

        if not self.isVisible():

            self.show()

        self.raise_()
        self.activateWindow()
        self.search_bar.input.setFocus()

    # ======================================================
    # WINDOWS DESKTOP LAYER
    # ======================================================

    def configure_desktop_window(self):

        if sys.platform != "win32":
            return

        import ctypes

        hwnd = int(
            self.winId()
        )

        user32 = ctypes.windll.user32

        GWL_EXSTYLE = -20

        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000

        ex_style = (
            user32.GetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
            )
        )

        ex_style &= ~WS_EX_APPWINDOW
        ex_style |= WS_EX_TOOLWINDOW

        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            ex_style,
        )

    def put_on_desktop(self):

        if sys.platform != "win32":
            return

        import ctypes

        hwnd = int(
            self.winId()
        )

        user32 = ctypes.windll.user32

        HWND_BOTTOM = 1

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010

        user32.SetWindowPos(
            hwnd,
            HWND_BOTTOM,
            0,
            0,
            0,
            0,
            SWP_NOSIZE
            | SWP_NOMOVE
            | SWP_NOACTIVATE,
        )

    # ======================================================
    # PAINT
    # ======================================================

    def paintEvent(self, event):

        # The MainWindow itself is intentionally transparent.
        #
        # The conversation and search bar paint their own glass
        # surfaces.
        return

    # ======================================================
    # CLOSE
    # ======================================================

    def closeEvent(self, event):

        if self.jarvis_controller is not None:

            self.jarvis_controller.stop()

        event.accept()