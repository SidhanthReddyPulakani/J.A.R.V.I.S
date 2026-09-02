import sys
from pathlib import Path

# --------------------------------------------------------------
# Make "backend.frontend.X" absolute imports resolvable no matter
# where this script is launched from (double-click, run_jarvis.bat,
# or `python main.py` from inside this very folder).
#
# This file lives at .../Jarvis/backend/frontend/main.py, so the
# directory two levels up (.../Jarvis) is what needs to be on
# sys.path for "backend.frontend..." to be importable.
# --------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from backend.frontend.windows.main_window import MainWindow
from backend.frontend.windows.overlay_window import OverlayWindow

from backend.frontend.jarvis_controller import JarvisController
from backend.frontend.hotkeys import HotkeyManager
from backend.frontend.system.tray import JarvisTray


def main():

    app = QApplication(sys.argv)

    window = MainWindow()
    overlay = OverlayWindow()

    controller = JarvisController(window)

    window.set_controller(controller)
    overlay.set_controller(controller)
    controller.set_overlay(overlay)

    window.overlay = overlay
    window.jarvis_controller = controller
    overlay.jarvis_controller = controller

    # The main widget and overlay both reflect backend state
    # (online/offline) without either of them being hidden as
    # a side effect of the other.
    controller.state_changed.connect(window.on_backend_state_changed)
    controller.state_changed.connect(overlay.on_backend_state_changed)

    hotkeys = HotkeyManager()
    hotkeys.overlay_toggle.connect(overlay.toggle)
    window.hotkeys = hotkeys

    tray = JarvisTray(controller)
    window.tray = tray

    window.show()

    controller.start()

    hotkeys.start()
    tray.show()

    exit_code = app.exec()

    hotkeys.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
