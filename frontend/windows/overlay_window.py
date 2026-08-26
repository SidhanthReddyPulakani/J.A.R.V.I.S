from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from widgets.search_bar import SearchBar
from widgets.overlay_conversation import OverlayConversation


class OverlayWindow(QWidget):

    request_submitted = Signal(str)

    # ======================================================
    # FIXED WINDOW
    # ======================================================

    WINDOW_WIDTH = 420
    WINDOW_HEIGHT = 500

    # ======================================================
    # SEARCH BAR
    # ======================================================

    SEARCH_WIDTH = 370
    SEARCH_HEIGHT = 46

    SEARCH_BOTTOM_MARGIN = 18

    # ======================================================
    # CONVERSATION
    # ======================================================

    CONVERSATION_BOTTOM_GAP = 8

    # ======================================================
    # SCREEN POSITION
    # ======================================================

    RIGHT_MARGIN = 25
    BOTTOM_MARGIN = 25

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )

        # --------------------------------------------------
        # Window
        # --------------------------------------------------

        self.setWindowTitle(
            "Jarvis Overlay"
        )

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        # FIXED.
        # It will never grow with conversation.
        self.setFixedSize(
            self.WINDOW_WIDTH,
            self.WINDOW_HEIGHT
        )

        # --------------------------------------------------
        # Controller
        # --------------------------------------------------

        self.jarvis_controller = None

        self.pending_query = ""

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        self.conversation = OverlayConversation(
            self
        )

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        self.search_bar = SearchBar(
            self
        )

        self.search_bar.setFixedHeight(
            self.SEARCH_HEIGHT
        )

        font = self.search_bar.input.font()

        font.setPointSize(
            11
        )

        self.search_bar.input.setFont(
            font
        )

        # --------------------------------------------------
        # Signals
        # --------------------------------------------------

        self.search_bar.submitted.connect(
            self._submit
        )

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        self.update_layout()

        self.move_to_bottom_right()

    # ======================================================
    # CONTROLLER
    # ======================================================

    def set_controller(
        self,
        controller
    ):

        self.jarvis_controller = controller

    # ======================================================
    # SUBMIT
    # ======================================================

    def _submit(
        self,
        text
    ):

        if not text:
            return

        self.pending_query = text

        self.request_submitted.emit(
            text
        )

        if self.jarvis_controller is None:

            self.on_error(
                text,
                "Jarvis controller is not connected."
            )

            return

        # Same controller API as MainWindow.
        self.jarvis_controller.ask(
            text
        )

    # ======================================================
    # RESPONSE
    # ======================================================

    def on_response(
        self,
        query,
        response
    ):

        self.conversation.add_conversation(
            query,
            response
        )

        self.pending_query = ""

        self.update_layout()

    # ======================================================
    # ERROR
    # ======================================================

    def on_error(
        self,
        query,
        error
    ):

        self.conversation.add_conversation(
            query,
            f"Backend error: {error}"
        )

        self.pending_query = ""

        self.update_layout()

    # ======================================================
    # BUSY
    # ======================================================

    def on_busy_changed(
        self,
        busy
    ):

        self.search_bar.set_busy(
            busy
        )

    # ======================================================
    # LAYOUT
    # ======================================================

    def update_layout(
        self
    ):

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        search_x = (
            self.WINDOW_WIDTH
            - self.SEARCH_WIDTH
        ) // 2

        search_y = (
            self.WINDOW_HEIGHT
            - self.SEARCH_HEIGHT
            - self.SEARCH_BOTTOM_MARGIN
        )

        self.search_bar.setGeometry(
            search_x,
            search_y,
            self.SEARCH_WIDTH,
            self.SEARCH_HEIGHT
        )

        # --------------------------------------------------
        # Conversation area
        # --------------------------------------------------

        conversation_x = 0

        conversation_y = 12

        conversation_width = (
            self.WINDOW_WIDTH
        )

        conversation_height = (
            search_y
            - self.CONVERSATION_BOTTOM_GAP
            - conversation_y
        )

        self.conversation.setGeometry(
            conversation_x,
            conversation_y,
            conversation_width,
            conversation_height
        )

        # --------------------------------------------------
        # Tell conversation that its viewport changed.
        # --------------------------------------------------

        self.conversation.refresh()

        # --------------------------------------------------
        # Search bar stays above everything.
        # --------------------------------------------------

        self.search_bar.raise_()

    # ======================================================
    # POSITION
    # ======================================================

    def move_to_bottom_right(
        self
    ):

        screen = self.screen()

        if screen is None:
            return

        geometry = (
            screen.availableGeometry()
        )

        x = (
            geometry.right()
            - self.width()
            - self.RIGHT_MARGIN
        )

        y = (
            geometry.bottom()
            - self.height()
            - self.BOTTOM_MARGIN
        )

        self.move(
            x,
            y
        )

    # ======================================================
    # SHOW
    # ======================================================

    def show_overlay(
        self
    ):

        self.update_layout()

        self.move_to_bottom_right()

        self.show()

        self.raise_()

        self.activateWindow()

        self.search_bar.input.setFocus()

    # ======================================================
    # HIDE
    # ======================================================

    def hide_overlay(
        self
    ):

        self.hide()

    # ======================================================
    # TOGGLE
    # ======================================================

    def toggle(
        self
    ):

        if self.isVisible():

            self.hide_overlay()

        else:

            self.show_overlay()

    # ======================================================
    # PAINT
    # ======================================================

    def paintEvent(
        self,
        event
    ):

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
            -1
        )

        # --------------------------------------------------
        # Background
        # --------------------------------------------------

        painter.setPen(
            Qt.NoPen
        )

        painter.setBrush(
            Qt.black
        )

        painter.setOpacity(
            0.78
        )

        painter.drawRoundedRect(
            rect,
            20,
            20
        )

        # --------------------------------------------------
        # Border
        # --------------------------------------------------

        painter.setBrush(
            Qt.transparent
        )

        painter.setPen(
            QPen(
                Qt.white,
                1
            )
        )

        painter.setOpacity(
            0.14
        )

        painter.drawRoundedRect(
            rect,
            20,
            20
        )