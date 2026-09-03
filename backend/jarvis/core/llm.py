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

    def stream(self, messages: list, tools: list):
        """
        Stream raw LLM observations to the caller.

        This method deliberately contains no reasoning or continuation
        decisions. The caller owns stream termination.
        """
        response_stream = self.client.chat(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            stream=True,
            think=settings.think,
            keep_alive=settings.keep_alive,
            options={
                "num_ctx": settings.context_size,
            },
        )

        for chunk in response_stream:
            message = getattr(chunk, "message", None)

            yield {
                "thinking": getattr(message, "thinking", "") or "",
                "content": getattr(message, "content", "") or "",
                "tool_calls": getattr(message, "tool_calls", None) or [],
                "done": bool(getattr(chunk, "done", False)),
                "timing": {
                    "total_duration": getattr(
                        chunk,
                        "total_duration",
                        None,
                    ),
                    "load_duration": getattr(
                        chunk,
                        "load_duration",
                        None,
                    ),
                    "prompt_eval_count": getattr(
                        chunk,
                        "prompt_eval_count",
                        None,
                    ),
                    "prompt_eval_duration": getattr(
                        chunk,
                        "prompt_eval_duration",
                        None,
                    ),
                    "eval_count": getattr(
                        chunk,
                        "eval_count",
                        None,
                    ),
                    "eval_duration": getattr(
                        chunk,
                        "eval_duration",
                        None,
                    ),
                },
            }

    def check_connection(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False