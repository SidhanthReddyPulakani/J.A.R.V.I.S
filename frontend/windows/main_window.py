from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from widgets.search_bar import SearchBar
from widgets.conversation import ConversationStack


class MainWindow(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # --------------------------------------------------
        # Window
        # --------------------------------------------------

        self.setWindowTitle("Jarvis")

        self.setWindowFlags(
            Qt.FramelessWindowHint
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        self.WINDOW_WIDTH = 900
        self.WINDOW_HEIGHT = 600

        self.setFixedSize(
            self.WINDOW_WIDTH,
            self.WINDOW_HEIGHT
        )

        # --------------------------------------------------
        # Search bar
        # --------------------------------------------------

        self.search_bar = SearchBar(self)

        self.SEARCH_WIDTH = 820
        self.SEARCH_HEIGHT = 58
        self.SEARCH_X = 40

        self.SEARCH_Y = (
            self.WINDOW_HEIGHT
            - self.SEARCH_HEIGHT
        ) // 2

        self.search_bar.setGeometry(
            self.SEARCH_X,
            self.SEARCH_Y,
            self.SEARCH_WIDTH,
            self.SEARCH_HEIGHT
        )

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        self.conversation = ConversationStack(self)

        # Conversation has EXACTLY the same width as
        # the search bar.
        self.CONVERSATION_X = self.SEARCH_X
        self.CONVERSATION_WIDTH = self.SEARCH_WIDTH

        self.conversation.setGeometry(
            self.CONVERSATION_X,
            20,
            self.CONVERSATION_WIDTH,
            100
        )

        # --------------------------------------------------
        # Backend controller
        # --------------------------------------------------

        self.jarvis_controller = None

        self.search_bar.submitted.connect(
            self.send_to_backend
        )

    # ======================================================
    # USER → BACKEND
    # ======================================================

    def send_to_backend(self, text):

        if self.jarvis_controller is None:

            self.on_error(
                "Jarvis controller is not connected."
            )

            return

        backend = self.jarvis_controller.backend

        if not backend.is_running():

            self.on_error(
                "Jarvis backend is not running."
            )

            return

        self.search_bar.last_submitted = text

        backend.ask(text)

    # ======================================================
    # BACKEND → UI
    # ======================================================

    def on_response(self, response):

        query = self.search_bar.last_submitted

        self.conversation.add_conversation(
            query,
            response
        )

        self.update_conversation_position()

    # ======================================================
    # ERROR
    # ======================================================

    def on_error(self, error):

        query = self.search_bar.last_submitted

        self.conversation.add_conversation(
            query,
            f"Backend error: {error}"
        )

        self.update_conversation_position()

    # ======================================================
    # BUSY
    # ======================================================

    def on_busy_changed(self, busy):

        self.search_bar.set_busy(
            busy
        )

    # ======================================================
    # CONVERSATION POSITION
    # ======================================================

    def update_conversation_position(self):

        # The search bar NEVER moves.
        search_y = self.search_bar.y()

        # Ask Qt how tall the actual conversation content is.
        content_height = (
            self.conversation.sizeHint().height()
        )

        if content_height <= 0:
            return

        gap = 8

        # The conversation's bottom edge is locked
        # just above the search bar.
        bottom = search_y - gap

        # Grow upward.
        top = max(
            10,
            bottom - content_height
        )

        height = bottom - top

        # --------------------------------------------------
        # IMPORTANT:
        #
        # Width is ALWAYS fixed to the search bar width.
        # Only height changes.
        # --------------------------------------------------

        self.conversation.setGeometry(
            self.CONVERSATION_X,
            top,
            self.CONVERSATION_WIDTH,
            height
        )

        # Conversation behind the search bar.
        self.conversation.raise_()

        # Search bar stays on top.
        self.search_bar.raise_()

    # ======================================================
    # CLOSE
    # ======================================================

    def closeEvent(self, event):

        if self.jarvis_controller is not None:
            self.jarvis_controller.stop()

        event.accept()