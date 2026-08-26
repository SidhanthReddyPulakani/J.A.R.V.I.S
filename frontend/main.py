import sys

from PySide6.QtWidgets import QApplication

from windows.main_window import MainWindow
from windows.overlay_window import OverlayWindow

from jarvis_controller import JarvisController
from hotkeys import HotkeyManager
from system.tray import JarvisTray


def main():

    app = QApplication(
        sys.argv
    )

    # --------------------------------------------------
    # Main interface
    # --------------------------------------------------

    window = MainWindow()

    # --------------------------------------------------
    # Overlay interface
    # --------------------------------------------------

    overlay = OverlayWindow()

    # --------------------------------------------------
    # ONE Jarvis controller
    # --------------------------------------------------

    controller = JarvisController(
        window
    )

    # Attach controller to main interface.
    window.set_controller(
        controller
    )

    # Attach controller to overlay.
    overlay.set_controller(
        controller
    )

    # Let controller broadcast to overlay.
    controller.set_overlay(
        overlay
    )

    # Keep references alive.
    window.overlay = overlay
    window.jarvis_controller = controller

    overlay.jarvis_controller = controller

    # --------------------------------------------------
    # Global hotkey
    # --------------------------------------------------

    hotkeys = HotkeyManager()

    hotkeys.overlay_toggle.connect(
        overlay.toggle
    )

    # Keep the hotkey manager alive.
    window.hotkeys = hotkeys

    # --------------------------------------------------
    # System tray
    # --------------------------------------------------

    tray = JarvisTray(
        controller
    )

    # Keep the tray alive.
    window.tray = tray

    # --------------------------------------------------
    # Show permanent main interface
    # --------------------------------------------------

    window.show()

    # --------------------------------------------------
    # Start Jarvis
    # --------------------------------------------------

    controller.start()

    # --------------------------------------------------
    # Start global hotkey
    # --------------------------------------------------

    hotkeys.start()

    # --------------------------------------------------
    # Show tray
    # --------------------------------------------------

    tray.show()

    # --------------------------------------------------
    # Run Qt
    # --------------------------------------------------

    exit_code = app.exec()

    # --------------------------------------------------
    # Clean up
    # --------------------------------------------------

    hotkeys.stop()

    sys.exit(
        exit_code
    )


if __name__ == "__main__":
    main()