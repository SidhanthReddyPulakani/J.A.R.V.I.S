from ollama import ResponseError

from jarvis.core.llm import LLMClient
from jarvis.state.models import AgentState
from jarvis.core.tools import AVAILABLE_TOOLS
from jarvis.storage.database import database
from jarvis.storage.repositories.agent_state import AgentStateRepository
from jarvis.context import (
    ContextCompiler,
    ContextRequest,
    ContextWindowManager,
)
from jarvis.recall.service import RecallService

from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)

from jarvis.memory import CoreMemoryService
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)

SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Your priorities:
1. Be concise and conversational.
2. Use tools when the user's request requires a desktop action.
3. Never claim an action was completed unless the tool result confirms it.
4. Do not explain your internal reasoning.
5. For simple commands, respond briefly.
"""


class JarvisAgent:

    AGENT_ID = "jarvis"

    def __init__(self) -> None:
        # Ensure the persistent database exists and migrations
        # have been applied before any repository is used.
        database.initialize()

        self.llm = LLMClient()

        self.enabled = True

        self.state_repository = AgentStateRepository(
            database
        )
        self.recall = RecallService(
            ConversationRepository(database)
        )

        self.state = (
            self.state_repository.get(
                self.AGENT_ID
            )
        )

        if self.state is None:
            self.state = AgentState(
                agent_id=self.AGENT_ID,
            )

            self.state_repository.save(
                self.state
            )

        if self.state.conversation_id is None:

            self.state.conversation_id = (
                self.recall
                .create_conversation()
            )

            self.state_repository.save(
                self.state
            )
        self.context_compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        self.core_memory = CoreMemoryService(
            CoreMemoryRepository(
                database
            ),
            agent_id=self.AGENT_ID,
        )
        self.core_memory.ensure_default_blocks()

        self.context_window = ContextWindowManager()


        self.messages = []

        persisted_messages = (
            self.recall.get_messages(
                self.state.conversation_id
            )
        )

        for message in persisted_messages:

            self.messages.append(
                {
                    "role": message["role"],
                    "content": message["content"],
                }
            )
    def _build_context(self):
        """
        Compile the temporary context for the current
        reasoning step.
        """

        request = ContextRequest(
            user_input="",
            state=self.state,
            conversation=list(
                self.messages
            ),
        )

        compiled = self.context_compiler.compile(
            request
        )

        return self.context_window.prepare(
            compiled
        )
    def run(self, user_input: str) -> str:
        user_message = {
            "role": "user",
            "content": user_input,
        }

        self.messages.append(
            user_message
        )

        self.recall.add_message(
            self.state.conversation_id,
            "user",
            user_input,
        )

        # --------------------------------------------------
        # Reasoning step 1
        # --------------------------------------------------

        context = self._build_context()

        response = self.llm.chat(
            messages=context.as_messages(),
            tools=list(
                AVAILABLE_TOOLS.values()
            ),
        )

        self.messages.append(
            response.message
        )

        if not response.message.tool_calls:
            self.recall.add_message(
                self.state.conversation_id,
                "assistant",
                response.message.content or "",
            )

        # --------------------------------------------------
        # Capability/tool execution
        #
        # This is still the OLD pathway for now.
        # Phase 2/4 will replace it with the
        # Capability Controller.
        # --------------------------------------------------

        if response.message.tool_calls:

            for call in response.message.tool_calls:

                name = call.function.name
                args = dict(
                    call.function.arguments
                )

                function = AVAILABLE_TOOLS.get(
                    name
                )

                if function is None:

                    result = (
                        f"Unknown tool: {name}"
                    )

                else:

                    try:
                        result = str(
                            function(**args)
                        )

                    except Exception as exc:

                        result = (
                            "Tool execution failed: "
                            f"{exc}"
                        )

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": result,
                    }
                )
            # --------------------------------------------------
            # Reasoning step 2
            #
            # Build a NEW context because the conversation
            # changed.
            # --------------------------------------------------

            context = self._build_context()

            final = self.llm.chat(
                messages=context.as_messages(),
                tools=list(
                    AVAILABLE_TOOLS.values()
                ),
            )

            self.messages.append(
                final.message
            )
            self.recall.add_message(
                self.state.conversation_id,
                "assistant",
                final.message.content or "",
            )

            self._persist_state()

            return (
                final.message.content
                or "Done."
            )

        self._persist_state()

        return (
            response.message.content
            or "I'm ready."
        )
    def _persist_state(self) -> None:
        """Persist the current Agent State."""
        self.state_repository.save(
            self.state
        )

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled