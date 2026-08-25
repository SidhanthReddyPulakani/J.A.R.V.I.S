import subprocess


class OllamaController:

    PROCESS_NAME = "ollama.exe"

    def is_running(self):

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {self.PROCESS_NAME}",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return (
            self.PROCESS_NAME.lower()
            in result.stdout.lower()
        )

    def start(self):

        if self.is_running():
            print("[Ollama already running]")
            return True

        print("[Starting Ollama]")

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

        print("[Ollama start requested]")

        return True

    def stop(self):

        if not self.is_running():

            print("[Ollama already stopped]")
            return

        print("[Stopping Ollama]")

        subprocess.run(
            [
                "taskkill",
                "/F",
                "/IM",
                self.PROCESS_NAME,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        print("[Ollama stopped]")