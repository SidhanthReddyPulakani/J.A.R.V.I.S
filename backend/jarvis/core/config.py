import os
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"


@dataclass(frozen=True)
class Settings:
    llm_model: str = os.getenv(
        "JARVIS_LLM_MODEL",
        "qwen3:4b",
    )

    ollama_host: str = os.getenv(
        "JARVIS_OLLAMA_HOST",
        "http://127.0.0.1:11434",
    )

    # --------------------------------------------------
    # Context Window
    # --------------------------------------------------

    context_size: int = int(
        os.getenv(
            "JARVIS_CONTEXT_SIZE",
            "8192",
        )
    )

    retrieval_budget: int = int(
        os.getenv(
            "JARVIS_RETRIEVAL_BUDGET",
            "4096",
        )
    )

    think: bool = os.getenv(
        "JARVIS_THINK",
        "false",
    ).lower() == "true"

    keep_alive: str = os.getenv(
        "JARVIS_KEEP_ALIVE",
        "10m",
    )

    start_with_windows: bool = os.getenv(
        "JARVIS_START_WITH_WINDOWS",
        "true",
    ).lower() == "true"

    hotkey: str = os.getenv(
        "JARVIS_HOTKEY",
        "ctrl+alt+j",
    )

    def ensure_directories(self) -> None:
        DATA_DIR.mkdir(
            exist_ok=True
        )

        LOG_DIR.mkdir(
            exist_ok=True
        )


settings = Settings()
print(f"[CONFIG DEBUG] JARVIS_THINK={settings.think}", file=sys.stderr)