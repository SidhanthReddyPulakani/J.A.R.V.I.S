from pathlib import Path
import sys

from PySide6.QtCore import (
    QObject,
    Signal,
    QTimer,
)

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

        # --------------------------------------------------
        # Interfaces
        # --------------------------------------------------

        self.window = window
        self.overlay = None

        # --------------------------------------------------
        # Backend
        # --------------------------------------------------

        self.backend = BackendBridge(self)

        # --------------------------------------------------
        # Ollama
        # --------------------------------------------------

        self.ollama = OllamaController()

        # --------------------------------------------------
        # State
        # --------------------------------------------------

        self.enabled = False
        self.starting = False
        self.stopping = False

        # --------------------------------------------------
        # Shared request state
        # --------------------------------------------------

        self.last_query = ""

        # --------------------------------------------------
        # Backend → Controller
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

    # ======================================================
    # INTERFACES
    # ======================================================

    def set_overlay(self, overlay):

        self.overlay = overlay

    # ======================================================
    # START
    # ======================================================

    def start(self):

        if self.enabled or self.starting:
            return

        self.starting = True
        self.stopping = False

        print(
            "\n[Starting Jarvis]"
        )

        # --------------------------------------------------
        # Start Ollama
        # --------------------------------------------------

        if not self.ollama.start():

            self.starting = False

            print(
                "[Jarvis failed: Ollama could not start]"
            )

            self.state_changed.emit(False)

            return

        # --------------------------------------------------
        # Give Ollama time to initialize.
        # --------------------------------------------------

        QTimer.singleShot(
            1000,
            self._start_backend
        )

    # ======================================================
    # START BACKEND
    # ======================================================

    def _start_backend(self):

        # --------------------------------------------------
        # A shutdown may have been requested while Ollama
        # was starting.
        # --------------------------------------------------

        if self.stopping:

            self.starting = False

            print(
                "[Jarvis] Startup cancelled."
            )

            return

        if self.enabled:

            self.starting = False

            return

        print(
            "[JarvisController] Starting backend."
        )

        self.backend.start()

        self.starting = False
        self.enabled = True

        self.state_changed.emit(True)

        print(
            "[Jarvis ENABLED]"
        )

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        # --------------------------------------------------
        # Prevent duplicate shutdown requests.
        # --------------------------------------------------

        if self.stopping:
            return

        self.stopping = True

        print(
            "\n[Stopping Jarvis]"
        )

        # --------------------------------------------------
        # Immediately mark the logical state disabled.
        #
        # This prevents new requests while shutdown occurs.
        # --------------------------------------------------

        self.enabled = False
        self.starting = False
        self.last_query = ""

        # --------------------------------------------------
        # Hide main interface.
        # --------------------------------------------------

        if self.window is not None:

            self.window.hide()

        # --------------------------------------------------
        # Hide overlay.
        # --------------------------------------------------

        if self.overlay is not None:

            self.overlay.hide()

        # --------------------------------------------------
        # Stop backend.
        # --------------------------------------------------

        try:

            self.backend.stop()

        except Exception as exc:

            print(
                f"[JarvisController] "
                f"Backend shutdown error: {exc}"
            )

        # --------------------------------------------------
        # Stop Ollama + unload models + clean stale
        # llama-server processes.
        # --------------------------------------------------

        try:

            ollama_clean = self.ollama.stop()

        except Exception as exc:

            ollama_clean = False

            print(
                f"[JarvisController] "
                f"Ollama shutdown error: {exc}"
            )

        # --------------------------------------------------
        # Tell frontend about final state.
        # --------------------------------------------------

        self.state_changed.emit(False)

        self.stopping = False

        if ollama_clean:

            print(
                "[Jarvis DISABLED]"
            )

        else:

            print(
                "[Jarvis DISABLED - "
                "Ollama cleanup reported a problem]"
            )

    # ======================================================
    # MASTER TOGGLE
    # ======================================================

    def toggle(self):

        if (
            self.enabled
            or self.starting
        ):

            self.stop()

        else:

            self.start()

    # ======================================================
    # MAIN INTERFACE TOGGLE
    # ======================================================

    def toggle_interface(self):

        # --------------------------------------------------
        # Interface cannot appear while Jarvis is disabled.
        # --------------------------------------------------

        if not self.enabled:
            return

        if self.window.isVisible():

            self.window.hide()

        else:

            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    # ======================================================
    # ASK
    # ======================================================

    def ask(self, text):

        text = str(text).strip()

        if not text:
            return

        # --------------------------------------------------
        # Jarvis disabled.
        # --------------------------------------------------

        if not self.enabled:

            self._broadcast_error(
                "Jarvis backend is not running."
            )

            return

        # --------------------------------------------------
        # Backend process unavailable.
        # --------------------------------------------------

        if not self.backend.is_running():

            self._broadcast_error(
                "Jarvis backend is not running."
            )

            return

        # --------------------------------------------------
        # Store query centrally.
        # --------------------------------------------------

        self.last_query = text

        print(
            f"[JarvisController] Query: {text}"
        )

        # --------------------------------------------------
        # ONE backend.
        # --------------------------------------------------

        self.backend.ask(text)

    # ======================================================
    # RESPONSE
    # ======================================================

    def _forward_response(self, response):

        query = self.last_query

        print(
            "[JarvisController] "
            "Broadcasting response."
        )

        # --------------------------------------------------
        # Main interface.
        # --------------------------------------------------

        if self.window is not None:

            self.window.on_response(
                query,
                response
            )

        # --------------------------------------------------
        # Overlay interface.
        # --------------------------------------------------

        if self.overlay is not None:

            self.overlay.on_response(
                query,
                response
            )

        self.last_query = ""

    # ======================================================
    # ERROR
    # ======================================================

    def _forward_error(self, error):

        query = self.last_query

        print(
            "[JarvisController] "
            "Broadcasting error."
        )

        # --------------------------------------------------
        # Main interface.
        # --------------------------------------------------

        if self.window is not None:

            self.window.on_error(
                query,
                error
            )

        # --------------------------------------------------
        # Overlay interface.
        # --------------------------------------------------

        if self.overlay is not None:

            self.overlay.on_error(
                query,
                error
            )

        self.last_query = ""

    # ======================================================
    # BUSY
    # ======================================================

    def _forward_busy(self, busy):

        # --------------------------------------------------
        # Main interface.
        # --------------------------------------------------

        if self.window is not None:

            self.window.on_busy_changed(
                busy
            )

        # --------------------------------------------------
        # Overlay interface.
        # --------------------------------------------------

        if self.overlay is not None:

            self.overlay.on_busy_changed(
                busy
            )

    # ======================================================
    # INTERNAL ERROR BROADCAST
    # ======================================================

    def _broadcast_error(self, error):

        self._forward_error(
            error
        )