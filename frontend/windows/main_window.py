import ctypes

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from widgets.search_bar import SearchBar
from widgets.conversation import ConversationStack


class MainWindow(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # ==================================================
        # WINDOW
        # ==================================================

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

        # ==================================================
        # CONTROLLER
        # ==================================================

        self.jarvis_controller = None

        self.pending_query = ""

        # ==================================================
        # CONVERSATION
        # ==================================================

        self.conversation = ConversationStack(
            self
        )

        self.CONVERSATION_X = 40
        self.CONVERSATION_WIDTH = 820

        self.conversation.setGeometry(
            self.CONVERSATION_X,
            20,
            self.CONVERSATION_WIDTH,
            100
        )

        # ==================================================
        # SEARCH BAR
        # ==================================================

        self.search_bar = SearchBar(
            self
        )

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

        self.search_bar.submitted.connect(
            self.send_to_backend
        )

        # ==================================================
        # DESKTOP POSITION
        # ==================================================

        self.move_to_desktop()

    # ======================================================
    # DESKTOP POSITION
    # ======================================================

    def move_to_desktop(self):

        screen = self.screen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        x = (
            geometry.left()
            + (
                geometry.width()
                - self.WINDOW_WIDTH
            ) // 2
        )

        y = (
            geometry.top()
            + (
                geometry.height()
                - self.WINDOW_HEIGHT
            ) // 2
        )

        self.move(x, y)

    # ======================================================
    # DESKTOP WINDOW STYLE
    # ======================================================

    def configure_desktop_window(self):

        hwnd = int(
            self.winId()
        )

        user32 = ctypes.windll.user32

        # --------------------------------------------------
        # Extended window styles
        # --------------------------------------------------

        GWL_EXSTYLE = -20

        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000

        ex_style = user32.GetWindowLongW(
            hwnd,
            GWL_EXSTYLE
        )

        # Remove APPWINDOW so Windows does not treat this
        # as a normal task-switcher/taskbar application.
        ex_style &= ~WS_EX_APPWINDOW

        # TOOLWINDOW keeps it out of Alt+Tab/taskbar.
        ex_style |= WS_EX_TOOLWINDOW

        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            ex_style
        )

    # ======================================================
    # PUT ON DESKTOP
    # ======================================================

    def put_on_desktop(self):

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
            | SWP_NOACTIVATE
        )

    # ======================================================
    # SHOW
    # ======================================================

    def showEvent(self, event):

        super().showEvent(event)

        self.move_to_desktop()

        # Configure the native window as a desktop
        # utility window before changing its Z-order.
        self.configure_desktop_window()

        # Put it underneath normal application windows.
        #
        # IMPORTANT:
        # We intentionally do NOT use SWP_SHOWWINDOW here.
        # Qt has already shown the window.
        self.put_on_desktop()

    # ======================================================
    # CONTROLLER
    # ======================================================

    def set_controller(self, controller):

        self.jarvis_controller = controller

    # ======================================================
    # USER → CONTROLLER
    # ======================================================

    def send_to_backend(self, text):

        if not text:
            return

        if self.jarvis_controller is None:

            self.on_error(
                text,
                "Jarvis controller is not connected."
            )

            return

        self.pending_query = text

        self.jarvis_controller.ask(text)

    # ======================================================
    # CONTROLLER → UI
    # ======================================================

    def on_response(
        self,
        query,
        response
    ):

        if not query:
            query = self.pending_query

        self.conversation.add_conversation(
            query,
            response
        )

        self.pending_query = ""

        self.update_conversation_position()

    # ======================================================
    # ERROR
    # ======================================================

    def on_error(
        self,
        query,
        error
    ):

        if not query:
            query = self.pending_query

        self.conversation.add_conversation(
            query,
            f"Backend error: {error}"
        )

        self.pending_query = ""

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

        search_y = self.search_bar.y()

        content_height = (
            self.conversation
            .sizeHint()
            .height()
        )

        if content_height <= 0:
            return

        gap = 8

        bottom = (
            search_y
            - gap
        )

        top = max(
            10,
            bottom - content_height
        )

        height = (
            bottom - top
        )

        self.conversation.setGeometry(
            self.CONVERSATION_X,
            top,
            self.CONVERSATION_WIDTH,
            height
        )

        self.conversation.raise_()

        self.search_bar.raise_()

    # ======================================================
    # CLOSE
    # ======================================================

    def closeEvent(self, event):

        if self.jarvis_controller is not None:
            self.jarvis_controller.stop()

        event.accept()