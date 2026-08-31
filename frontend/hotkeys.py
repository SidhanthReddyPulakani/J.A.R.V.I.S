import ctypes
from ctypes import wintypes

from PySide6.QtCore import (
    QObject,
    Signal,
    QAbstractNativeEventFilter,
)

from PySide6.QtWidgets import QApplication


class HotkeyManager(
    QObject,
    QAbstractNativeEventFilter
):

    overlay_toggle = Signal()

    # Windows hotkey identifier.
    HOTKEY_ID = 1

    # Ctrl + Alt + J
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002

    VK_J = 0x4A

    WM_HOTKEY = 0x0312

    def __init__(
        self,
        parent=None
    ):

        QObject.__init__(
            self,
            parent
        )

        QAbstractNativeEventFilter.__init__(
            self
        )

        self.enabled = False

    # ======================================================
    # START
    # ======================================================

    def start(self):

        if self.enabled:
            return

        registered = (
            ctypes.windll.user32.RegisterHotKey(
                None,
                self.HOTKEY_ID,
                self.MOD_CONTROL | self.MOD_ALT,
                self.VK_J
            )
        )

        if not registered:

            print(
                "[Hotkeys] ERROR: "
                "Could not register Ctrl + Alt + J."
            )

            print(
                "[Hotkeys] The hotkey may already "
                "be registered."
            )

            return

        app = QApplication.instance()

        if app is not None:

            app.installNativeEventFilter(
                self
            )

        self.enabled = True

        print(
            "[Hotkeys] Ctrl + Alt + J registered."
        )

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        if not self.enabled:
            return

        ctypes.windll.user32.UnregisterHotKey(
            None,
            self.HOTKEY_ID
        )

        app = QApplication.instance()

        if app is not None:

            app.removeNativeEventFilter(
                self
            )

        self.enabled = False

        print(
            "[Hotkeys] Ctrl + Alt + J unregistered."
        )

    # ======================================================
    # WINDOWS NATIVE EVENT
    # ======================================================

    def nativeEventFilter(
        self,
        eventType,
        message
    ):

        if eventType not in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            return False, 0

        msg = wintypes.MSG.from_address(
            int(message)
        )

        if msg.message == self.WM_HOTKEY:

            if msg.wParam == self.HOTKEY_ID:

                print(
                    "[Hotkeys] Ctrl + Alt + J pressed."
                )

                self.overlay_toggle.emit()

                return True, 0

        return False, 0