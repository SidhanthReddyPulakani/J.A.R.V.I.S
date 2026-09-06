import sys
import time

from ollama import Client, ResponseError

from jarvis.computation.profile import (
    ComputationMode,
    ComputationProfile,
)
from jarvis.core.config import Settings


class LLMClient:
    def __init__(self) -> None:
        self.client = Client(
            host=Settings().ollama_host
        )

    # ==========================================================
    # COMPUTATION PROFILE
    # ==========================================================

    @staticmethod
    def profile_for_mode(
        mode: ComputationMode,
    ) -> ComputationProfile:
        """
        Convert an O1 computation mode into the runtime profile.

        This method intentionally contains no model-specific
        assumptions.
        """

        return ComputationProfile.from_mode(
            mode
        )

    # ==========================================================
    # RUNTIME THINKING SUPPORT
    # ==========================================================

    def _model_supports_thinking(
        self,
        model: str,
    ) -> bool:
        """
        Determine whether the configured Ollama model exposes
        thinking capability.

        The runtime must never assume that every model supports
        the `think` parameter.
        """

        try:
            details = self.client.show(
                model
            )

        except Exception as exc:
            print(
                "[LLM DEBUG] Unable to inspect model "
                f"capabilities: {exc}",
                file=sys.stderr,
            )

            return False

        capabilities = getattr(
            details,
            "capabilities",
            None,
        )

        if capabilities is None:
            return False

        if isinstance(
            capabilities,
            (list, tuple, set),
        ):
            normalized = {
                str(value).lower()
                for value in capabilities
            }

            return "thinking" in normalized

        return False

    # ==========================================================
    # RUNTIME PROFILE
    # ==========================================================

    def _build_runtime_parameters(
        self,
        settings: Settings,
        profile: ComputationProfile,
    ) -> dict:
        """
        Translate a computation profile into actual Ollama
        request parameters.

        Only parameters whose semantics are established by the
        current project are applied here.
        """

        parameters = {
            "model": settings.llm_model,
            "keep_alive": settings.keep_alive,
            "options": {
                "num_ctx": (
                    profile.context_budget
                    if profile.context_budget is not None
                    else settings.context_size
                ),
            },
        }

        supports_thinking = (
            self._model_supports_thinking(
                settings.llm_model
            )
        )

        if supports_thinking:

            if profile.thinking_policy == "disabled":
                parameters["think"] = False

            elif profile.thinking_policy == "enabled":
                parameters["think"] = True

            else:
                # "default" preserves the configured runtime
                # behavior for NORMAL mode.
                parameters["think"] = settings.think

        else:
            # Do not send `think=True` to a model that does not
            # advertise thinking support.
            parameters["think"] = False

        print(
            "[LLM DEBUG] O1 runtime profile:",
            profile.mode.value,
            file=sys.stderr,
        )

        print(
            "[LLM DEBUG] O1 thinking policy:",
            profile.thinking_policy,
            file=sys.stderr,
        )

        print(
            "[LLM DEBUG] model supports thinking:",
            supports_thinking,
            file=sys.stderr,
        )

        print(
            "[LLM DEBUG] runtime think:",
            parameters["think"],
            file=sys.stderr,
        )

        return parameters

    # ==========================================================
    # CHAT
    # ==========================================================

    def chat(
        self,
        messages: list,
        tools: list,
        profile: ComputationProfile | None = None,
    ):
        settings = Settings()

        if profile is None:
            profile = self.profile_for_mode(
                ComputationMode.NORMAL
            )
        print(
            "[LLM DEBUG] model:",
            settings.llm_model,
            file=sys.stderr,
        )
        runtime_parameters = (
            self._build_runtime_parameters(
                settings=settings,
                profile=profile,
            )
        )

        started_at = time.perf_counter()

        response = self.client.chat(
            model=runtime_parameters["model"],
            messages=messages,
            tools=tools,
            stream=False,
            think=runtime_parameters["think"],
            keep_alive=runtime_parameters["keep_alive"],
            options=runtime_parameters["options"],
        )

        elapsed = (
            time.perf_counter()
            - started_at
        )

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
            getattr(
                response.message,
                "tool_calls",
                None,
            ),
        )

        print(
            "[LLM DEBUG] content:",
            getattr(
                response.message,
                "content",
                None,
            ),
        )

        return response

    # ==========================================================
    # CONNECTION
    # ==========================================================

    def check_connection(self) -> bool:
        try:
            self.client.list()
            return True

        except Exception:
            return False