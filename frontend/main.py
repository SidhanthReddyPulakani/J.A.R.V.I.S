import sys
from pathlib import Path

# --------------------------------------------------------------
# Project root
# --------------------------------------------------------------

_PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

if str(_PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(_PROJECT_ROOT),
    )


from PySide6.QtWidgets import (
    QApplication,
)

from frontend.windows.main_window import (
    MainWindow,
)

from frontend.jarvis_controller import (
    JarvisController,
)

from frontend.hotkeys import (
    HotkeyManager,
)

from frontend.system.tray import (
    JarvisTray,
)


def main():

    app = QApplication(
        sys.argv
    )

    # ==================================================
    # MAIN JARVIS INTERFACE
    # ==================================================

    window = MainWindow()

    # ==================================================
    # CONTROLLER
    # ==================================================

    controller = JarvisController(
        window
    )

    window.set_controller(
        controller
    )

    # ==================================================
    # BACKEND STATE
    # ==================================================

    controller.state_changed.connect(
        window.on_backend_state_changed
    )

    # ==================================================
    # HOTKEY
    #
    # Ctrl + Alt + J now controls the MAIN interface.
    #
    # There is no separate chat popup.
    # ==================================================

    hotkeys = HotkeyManager()

    hotkeys.overlay_toggle.connect(
        window.toggle_interface
    )

    window.hotkeys = hotkeys

    # ==================================================
    # TRAY
    # ==================================================

    tray = JarvisTray(
        controller
    )

    window.tray = tray

    # ==================================================
    # SHOW
    # ==================================================

    window.show()

    # ==================================================
    # START BACKEND
    # ==================================================

    controller.start()

    hotkeys.start()

    tray.show()

    # ==================================================
    # EVENT LOOP
    # ==================================================

    exit_code = app.exec()

    hotkeys.stop()

    sys.exit(
        exit_code
    )


if __name__ == "__main__":

    main()