import sys

from PySide6.QtWidgets import QApplication

from windows.main_window import MainWindow
from windows.overlay_window import OverlayWindow

from jarvis_controller import JarvisController
from hotkeys import HotkeyManager
from system.tray import JarvisTray


def main():

    app = QApplication(sys.argv)

    print("[MAIN] QApplication created")

    window = MainWindow()

    print("[MAIN] MainWindow created")
    print("[MAIN] visible:", window.isVisible())
    print("[MAIN] geometry:", window.geometry())

    overlay = OverlayWindow()

    print("[MAIN] Overlay created")

    controller = JarvisController(window)

    print("[MAIN] Controller created")

    window.set_controller(controller)
    overlay.set_controller(controller)
    controller.set_overlay(overlay)

    window.overlay = overlay
    window.jarvis_controller = controller
    overlay.jarvis_controller = controller

    hotkeys = HotkeyManager()

    hotkeys.overlay_toggle.connect(
        overlay.toggle
    )

    window.hotkeys = hotkeys

    tray = JarvisTray(controller)
    window.tray = tray

    print("[MAIN] About to show MainWindow")

    window.show()

    print("[MAIN] MainWindow.show() returned")
    print("[MAIN] visible after show:", window.isVisible())
    print("[MAIN] geometry after show:", window.geometry())

    controller.start()

    hotkeys.start()
    tray.show()

    print("[MAIN] Starting Qt event loop")

    exit_code = app.exec()

    hotkeys.stop()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()