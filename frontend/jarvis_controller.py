from pathlib import Path
import sys

from PySide6.QtCore import (
    QObject,
    Signal,
    QTimer,
)

from frontend.backend_bridge import BackendBridge


# ------------------------------------------------------
# Backend path
# ------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# NOTE: PROJECT_ROOT (parents[1] of this file, i.e. .../backend) *is*
# already the directory that contains the "jarvis" package directly
# (backend/jarvis). It must NOT be joined with another "backend" —
# that pointed sys.path at a non-existent backend/backend folder,
# which is why "jarvis" could never be found.
BACKEND_DIR = PROJECT_ROOT

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jarvis.core.llm import LLMClient


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
        # Ollama is a standalone service (see jarvis.core.llm
        # / jarvis.core.config): the backend connects to it
        # over HTTP, it does not spawn or manage it. The
        # frontend's job here is only to check it's reachable
        # before starting the backend subprocess — not to
        # start Ollama itself.
        # --------------------------------------------------

        if not self._ollama_reachable():

            self.starting = False

            print(
                "[Jarvis failed: Ollama is not reachable]"
            )

            self._broadcast_error(
                "Couldn't reach Ollama. Make sure the "
                "Ollama app/service is running, then try "
                "again."
            )

            self.state_changed.emit(False)

            return

        # --------------------------------------------------
        # Small delay purely so the UI has a moment to show
        # a "connecting" state before the backend subprocess
        # spins up; not waiting on anything to start.
        # --------------------------------------------------

        QTimer.singleShot(
            150,
            self._start_backend
        )

    # ======================================================
    # OLLAMA REACHABILITY CHECK
    # ======================================================

    def _ollama_reachable(self) -> bool:

        try:

            client = LLMClient()

            return client.check_connection()

        except Exception as exc:

            print(
                f"[JarvisController] "
                f"Ollama check failed: {exc}"
            )

            return False

    # ======================================================
    # START BACKEND
    # ======================================================

    def _start_backend(self):

        # --------------------------------------------------
        # A shutdown may have been requested while the
        # reachability check / delay was in flight.
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
        # Main interface stays on the desktop.
        #
        # It is a persistent widget, not a session window —
        # disabling Jarvis should not make it disappear. It's
        # told about the offline state below (state_changed)
        # so it can reflect "Jarvis is offline" instead.
        # --------------------------------------------------

        # --------------------------------------------------
        # Hide the overlay.
        #
        # The overlay IS a transient, hotkey-summoned popup,
        # so dismissing it when the backend goes down is
        # correct.
        # --------------------------------------------------

        if self.overlay is not None:

            self.overlay.hide()

        # --------------------------------------------------
        # Stop backend.
        #
        # Ollama itself is left running — it's a standalone
        # service the frontend never owned the lifecycle of.
        # --------------------------------------------------

        try:

            self.backend.stop()

        except Exception as exc:

            print(
                f"[JarvisController] "
                f"Backend shutdown error: {exc}"
            )

        # --------------------------------------------------
        # Tell frontend about final state.
        # --------------------------------------------------

        self.state_changed.emit(False)

        self.stopping = False

        print(
            "[Jarvis DISABLED]"
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
        # The main widget is a persistent desktop fixture and
        # can be shown/hidden on demand regardless of whether
        # the backend is currently enabled — it just shows an
        # offline state when it is (see on_backend_state_changed).
        # --------------------------------------------------

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