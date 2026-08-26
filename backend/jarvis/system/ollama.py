import json
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import URLError


class OllamaController:

    OLLAMA_PROCESS = "ollama.exe"
    OLLAMA_APP_PROCESS = "ollama app.exe"
    LLAMA_SERVER_PROCESS = "llama-server.exe"

    API_URL = "http://127.0.0.1:11434"

    # ======================================================
    # PROCESS CHECK
    # ======================================================

    def _process_exists(self, process_name):

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {process_name}",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return (
            process_name.lower()
            in result.stdout.lower()
        )

    def is_running(self):

        return self._process_exists(
            self.OLLAMA_PROCESS
        )

    # ======================================================
    # START
    # ======================================================

    def start(self):

        if self.is_running():

            print(
                "[Ollama already running]"
            )

            return True

        print(
            "[Starting Ollama]"
        )

        try:

            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        except FileNotFoundError:

            print(
                "[ERROR] Could not find 'ollama'."
            )

            return False

        # --------------------------------------------------
        # Wait for API
        # --------------------------------------------------

        for _ in range(20):

            if self._api_available():

                print(
                    "[Ollama API READY]"
                )

                return True

            time.sleep(0.25)

        print(
            "[ERROR] Ollama did not become ready."
        )

        return False

    # ======================================================
    # API
    # ======================================================

    def _api_available(self):

        try:

            request = Request(
                f"{self.API_URL}/api/ps",
                method="GET",
            )

            with urlopen(
                request,
                timeout=1,
            ) as response:

                return response.status == 200

        except Exception:

            return False

    # ======================================================
    # LOADED MODELS
    # ======================================================

    def loaded_models(self):

        try:

            request = Request(
                f"{self.API_URL}/api/ps",
                method="GET",
            )

            with urlopen(
                request,
                timeout=2,
            ) as response:

                data = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            models = data.get(
                "models",
                []
            )

            names = []

            for model in models:

                name = model.get(
                    "name"
                )

                if name:
                    names.append(
                        name
                    )

            return names

        except Exception as exc:

            print(
                f"[Ollama] Could not query loaded models: {exc}"
            )

            return []

    # ======================================================
    # UNLOAD MODELS
    # ======================================================

    def unload_models(self):

        models = self.loaded_models()

        if not models:

            print(
                "[Ollama] No loaded models."
            )

            return True

        success = True

        for model in models:

            print(
                f"[Ollama] Unloading model: {model}"
            )

            try:

                payload = json.dumps(
                    {
                        "model": model,
                        "prompt": "",
                        "keep_alive": 0,
                    }
                ).encode(
                    "utf-8"
                )

                request = Request(
                    f"{self.API_URL}/api/generate",
                    data=payload,
                    headers={
                        "Content-Type":
                        "application/json"
                    },
                    method="POST",
                )

                with urlopen(
                    request,
                    timeout=10,
                ) as response:

                    response.read()

                print(
                    f"[Ollama] Unload requested: {model}"
                )

            except Exception as exc:

                success = False

                print(
                    f"[Ollama] Failed to unload "
                    f"{model}: {exc}"
                )

        return success

    # ======================================================
    # STOP MODEL VIA CLI
    # ======================================================

    def stop_models_cli(self):

        models = self.loaded_models()

        if not models:
            return True

        success = True

        for model in models:

            print(
                f"[Ollama] Stopping model: {model}"
            )

            result = subprocess.run(
                [
                    "ollama",
                    "stop",
                    model,
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:

                success = False

                print(
                    "[Ollama] ollama stop failed:"
                )

                if result.stderr:
                    print(
                        result.stderr.strip()
                    )

        return success

    # ======================================================
    # STOP SERVER PROCESSES
    # ======================================================

    def _kill_process(
        self,
        process_name,
    ):

        if not self._process_exists(
            process_name
        ):
            return True

        print(
            f"[Ollama] Terminating {process_name}"
        )

        subprocess.run(
            [
                "taskkill",
                "/F",
                "/IM",
                process_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # --------------------------------------------------
        # Verify termination
        # --------------------------------------------------

        for _ in range(20):

            if not self._process_exists(
                process_name
            ):
                return True

            time.sleep(0.1)

        return False

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        print(
            "\n[Ollama shutdown requested]"
        )

        # --------------------------------------------------
        # 1. Gracefully unload loaded models.
        # --------------------------------------------------

        self.unload_models()

        # --------------------------------------------------
        # 2. Give llama-server a moment to exit.
        # --------------------------------------------------

        time.sleep(0.5)

        # --------------------------------------------------
        # 3. CLI stop as a second graceful mechanism.
        # --------------------------------------------------

        self.stop_models_cli()

        time.sleep(0.5)

        # --------------------------------------------------
        # 4. Kill any remaining llama-server.
        #
        # This is our stale-process protection.
        # --------------------------------------------------

        llama_stopped = self._kill_process(
            self.LLAMA_SERVER_PROCESS
        )

        # --------------------------------------------------
        # 5. Stop Ollama itself.
        # --------------------------------------------------

        self._kill_process(
            self.OLLAMA_PROCESS
        )

        # --------------------------------------------------
        # 6. Stop Ollama Windows app if present.
        # --------------------------------------------------

        self._kill_process(
            self.OLLAMA_APP_PROCESS
        )

        # --------------------------------------------------
        # 7. Final verification.
        # --------------------------------------------------

        ollama_alive = self._process_exists(
            self.OLLAMA_PROCESS
        )

        app_alive = self._process_exists(
            self.OLLAMA_APP_PROCESS
        )

        llama_alive = self._process_exists(
            self.LLAMA_SERVER_PROCESS
        )

        print(
            "[Ollama shutdown verification]"
        )

        print(
            f"  ollama.exe: "
            f"{'RUNNING' if ollama_alive else 'STOPPED'}"
        )

        print(
            f"  ollama app.exe: "
            f"{'RUNNING' if app_alive else 'STOPPED'}"
        )

        print(
            f"  llama-server.exe: "
            f"{'RUNNING' if llama_alive else 'STOPPED'}"
        )

        if (
            not ollama_alive
            and not app_alive
            and not llama_alive
            and llama_stopped
        ):

            print(
                "[Ollama shutdown COMPLETE]"
            )

            return True

        print(
            "[WARNING] Ollama shutdown "
            "was not completely clean."
        )

        return False