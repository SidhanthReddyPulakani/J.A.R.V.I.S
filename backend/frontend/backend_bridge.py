import json
from pathlib import Path
import time
from PySide6.QtCore import QObject, Signal, QProcess


class BackendBridge(QObject):

    response_ready = Signal(str)
    error = Signal(str)
    busy_changed = Signal(bool)

    started = Signal()
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._request_started_at = None
        self.process = None
        self._buffer = ""
        self._busy = False

        # --------------------------------------------------
        # Project paths
        #
        # Actual structure:
        #
        # Jarvis/
        # ├── .venv/
        # └── backend/
        #     ├── main.py
        #     ├── jarvis/
        #     └── frontend/
        #         └── backend_bridge.py
        # --------------------------------------------------

        project_root = Path(__file__).resolve().parents[2]
        self.backend_dir = project_root / "backend"

        self.python_executable = (
            project_root
            / ".venv"
            / "Scripts"
            / "python.exe"
        )

        self.backend_main = (
            self.backend_dir
            / "main.py"
        )

    # ======================================================
    # START
    # ======================================================

    def start(self):

        if self.is_running():
            return

        # --------------------------------------------------
        # Verify Python
        # --------------------------------------------------

        if not self.python_executable.exists():

            self.error.emit(
                "Backend Python executable not found:\n\n"
                f"{self.python_executable}"
            )

            print(
                "[BackendBridge] Python executable missing:"
            )
            print(self.python_executable)

            return

        # --------------------------------------------------
        # Verify backend
        # --------------------------------------------------

        if not self.backend_main.exists():

            self.error.emit(
                "Backend main.py not found:\n\n"
                f"{self.backend_main}"
            )

            print(
                "[BackendBridge] Backend main.py missing:"
            )
            print(self.backend_main)

            return

        print()
        print("[BackendBridge] Starting backend...")
        print(f"[BackendBridge] Python: {self.python_executable}")
        print(f"[BackendBridge] Backend: {self.backend_main}")

        self._buffer = ""

        self.process = QProcess(self)

        self.process.setWorkingDirectory(
            str(self.backend_dir)
        )

        self.process.setProgram(
            str(self.python_executable)
        )

        self.process.setArguments([
            str(self.backend_main)
        ])

        # --------------------------------------------------
        # Signals
        # --------------------------------------------------

        self.process.readyReadStandardOutput.connect(
            self._read_stdout
        )

        self.process.readyReadStandardError.connect(
            self._read_stderr
        )

        self.process.started.connect(
            self._on_started
        )

        self.process.finished.connect(
            self._on_finished
        )

        self.process.errorOccurred.connect(
            self._on_process_error
        )

        self.process.start()

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        if not self.process:
            return

        if not self.is_running():
            return

        print("[BackendBridge] Stopping backend...")

        self._busy = False
        self.busy_changed.emit(False)

        # Ask backend to shut down cleanly.
        self._send({
            "type": "shutdown"
        })

        # Give backend time to exit normally.
        if not self.process.waitForFinished(1500):

            print(
                "[BackendBridge] Backend did not exit cleanly."
            )

            self.process.kill()
            self.process.waitForFinished(1000)

    # ======================================================
    # ASK
    # ======================================================

    def ask(self, text):

        if not self.is_running():

            self.error.emit(
                "Jarvis backend is not running."
            )

            return

        if self._busy:
            return

        text = str(text).strip()

        if not text:
            return

        print(
            f"[BackendBridge] Sending: {text}"
        )

        self._busy = True
        self.busy_changed.emit(True)
        self._request_started_at = time.perf_counter()
        self._send({
            "type": "ask",
            "text": text,
        })

    # ======================================================
    # SEND
    # ======================================================

    def _send(self, message):

        if not self.process:
            return

        if not self.is_running():
            return

        try:

            payload = (
                json.dumps(message)
                + "\n"
            )

            self.process.write(
                payload.encode("utf-8")
            )

            self.process.waitForBytesWritten(
                1000
            )

        except Exception as exc:

            self._busy = False
            self.busy_changed.emit(False)

            self.error.emit(
                f"Failed to communicate with backend:\n{exc}"
            )

    # ======================================================
    # STDOUT
    # ======================================================

    def _read_stdout(self):

        if not self.process:
            return

        data = self.process.readAllStandardOutput()

        text = bytes(data).decode(
            "utf-8",
            errors="replace"
        )

        self._buffer += text

        while "\n" in self._buffer:

            line, self._buffer = self._buffer.split(
                "\n",
                1
            )

            line = line.strip()

            if not line:
                continue

            print(
                f"[BackendBridge] ← {line}"
            )

            try:

                message = json.loads(line)

            except json.JSONDecodeError:

                # Ignore normal backend console output.
                print(
                    f"[BackendBridge] Non-JSON output: {line}"
                )

                continue

            self._handle_message(message)

    # ======================================================
    # HANDLE MESSAGE
    # ======================================================

    def _handle_message(self, message):

        message_type = message.get("type")

        if message_type == "ready":

            print(
                "[BackendBridge] Backend READY."
            )

            self.started.emit()

            return

        if message_type == "response":

            elapsed = None

            if self._request_started_at is not None:
                elapsed = time.perf_counter() - self._request_started_at

            self._request_started_at = None

            self._busy = False
            self.busy_changed.emit(False)

            response = message.get(
                "response",
                ""
            )

            if elapsed is not None:
                print(
                    f"[BackendBridge] Response received "
                    f"in {elapsed:.2f}s"
                )
            else:
                print(
                    "[BackendBridge] Response received."
                )

            self.response_ready.emit(
                str(response)
            )

            return
            self._busy = False
            self.busy_changed.emit(False)

            response = message.get(
                "response",
                ""
            )

            print(
                "[BackendBridge] Response received."
            )

            self.response_ready.emit(
                str(response)
            )

            return

        if message_type == "error":

            elapsed = None

            if self._request_started_at is not None:
                elapsed = time.perf_counter() - self._request_started_at

            self._request_started_at = None

            self._busy = False
            self.busy_changed.emit(False)

            error = message.get(
                "error",
                "Unknown backend error."
            )

            if elapsed is not None:
                print(
                    f"[BackendBridge] Backend error after "
                    f"{elapsed:.2f}s: {error}"
                )
            else:
                print(
                    f"[BackendBridge] Backend error: {error}"
                )

            self.error.emit(
                str(error)
            )

            return
        
        print(
            f"[BackendBridge] Unknown message: {message}"
        )

    # ======================================================
    # STDERR
    # ======================================================

    def _read_stderr(self):

        if not self.process:
            return

        data = self.process.readAllStandardError()

        text = bytes(data).decode(
            "utf-8",
            errors="replace"
        ).strip()

        if text:

            print(
                f"[Backend STDERR] {text}"
            )

    # ======================================================
    # PROCESS STARTED
    # ======================================================

    def _on_started(self):

        print(
            "[BackendBridge] Backend process started."
        )

    # ======================================================
    # PROCESS FINISHED
    # ======================================================

    def _on_finished(
        self,
        exit_code,
        exit_status,
    ):

        print(
            f"[BackendBridge] Backend stopped "
            f"(exit code: {exit_code})"
        )

        self._busy = False
        self.busy_changed.emit(False)

        self.stopped.emit()

        if self.process:

            self.process.deleteLater()
            self.process = None

    # ======================================================
    # PROCESS ERROR
    # ======================================================

    def _on_process_error(
        self,
        process_error,
    ):

        print(
            f"[BackendBridge] Process error: {process_error}"
        )

        self.error.emit(
            f"Backend process error: {process_error}"
        )

    # ======================================================
    # STATE
    # ======================================================

    def is_running(self):

        return (
            self.process is not None
            and self.process.state()
            == QProcess.Running
        )