from ollama import Client, ResponseError
from jarvis.core.config import settings

class LLMClient:
    def __init__(self) -> None:
        self.client = Client(host=settings.ollama_host)

    def chat(self, messages: list, tools: list):
        return self.client.chat(
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

    def check_connection(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False
