import sys

from ollama import Client, ResponseError
from jarvis.core.config import Settings
import time

class LLMClient:
    def __init__(self) -> None:
        self.client = Client(host=Settings().ollama_host)

    def chat(self, messages: list, tools: list):
        settings = Settings()

        started_at = time.perf_counter()

        response = self.client.chat(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            stream=False,
            think=settings.think,
            keep_alive=settings.keep_alive,
            options={
                "num_ctx": settings.context_size,
            },
        )

        elapsed = time.perf_counter() - started_at

        print(
            f"[LLM DEBUG] chat() completed in {elapsed:.2f}s",
            file=sys.stderr,
        )

        print(
            "[CONFIG DEBUG] JARVIS_THINK=",
            settings.think,
            file=sys.stderr,
        )

        print(
            "[LLM DEBUG] tool_calls:",
            getattr(response.message, "tool_calls", None),
        )

        print(
            "[LLM DEBUG] content:",
            getattr(response.message, "content", None),
        )

        return response

    def check_connection(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False
