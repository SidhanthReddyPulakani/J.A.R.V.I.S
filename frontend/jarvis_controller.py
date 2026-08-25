from pathlib import Path
import sys

from PySide6.QtCore import QObject, Signal, QTimer

from backend_bridge import BackendBridge


# ------------------------------------------------------
# Backend path
# ------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jarvis.system.ollama import OllamaController


class JarvisController(QObject):

    state_changed = Signal(bool)

    def __init__(self, window, parent=None):
        super().__init__(parent)

        self.window = window

        # Backend process controller
        self.backend = BackendBridge(self)

        # Ollama process controller
        self.ollama = OllamaController()

        self.enabled = False

        # --------------------------------------------------
        # Backend → Frontend
        # --------------------------------------------------

        self.backend.response_ready.connect(
            self._forward_response
        )

        self.backend.error.connect(
            self._forward_error
        )

        self.backend.busy_changed.connect(
            self._forward_busy
        )

    # ------------------------------------------------------
    # Start Jarvis
    # ------------------------------------------------------

    def start(self):

        if self.enabled:
            return

        print("\n[Starting Jarvis]")

        # Start Ollama first
        if not self.ollama.start():

            print(
                "[Jarvis failed: Ollama could not start]"
            )

            return

        # Give Ollama a moment to initialize.
        # This does not freeze the Qt UI.
        QTimer.singleShot(
            1000,
            self._start_backend
        )

    def _start_backend(self):

        if self.enabled:
            return

        self.backend.start()

        self.enabled = True

        self.state_changed.emit(True)

        print("[Jarvis ENABLED]")

    # ------------------------------------------------------
    # Stop Jarvis
    # ------------------------------------------------------

    def stop(self):

        if not self.enabled:
            return

        print("\n[Stopping Jarvis]")

        # Hide interface
        self.window.hide()

        # Stop backend process
        self.backend.stop()

        # Stop Ollama
        self.ollama.stop()

        self.enabled = False

        self.state_changed.emit(False)

        print("[Jarvis DISABLED]")

    # ------------------------------------------------------
    # Master toggle
    # ------------------------------------------------------

    def toggle(self):

        if self.enabled:
            self.stop()
        else:
            self.start()

    # ------------------------------------------------------
    # Interface-only toggle
    # ------------------------------------------------------

    def toggle_interface(self):

        # Don't show the UI if the entire
        # Jarvis system is disabled.
        if not self.enabled:
            return

        if self.window.isVisible():

            self.window.hide()

        else:

            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    # ------------------------------------------------------
    # Backend response forwarding
    # ------------------------------------------------------

    def _forward_response(self, response):

        self.window.on_response(
            response
        )

    def _forward_error(self, error):

        self.window.on_error(
            error
        )

    def _forward_busy(self, busy):

        self.window.on_busy_changed(
            busy
        )