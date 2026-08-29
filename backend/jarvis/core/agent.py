from ollama import ResponseError

from jarvis.core.llm import LLMClient
from jarvis.state.models import AgentState
from jarvis.core.tools import AVAILABLE_TOOLS

from jarvis.storage.database import database

from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)

from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)

from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)

from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)

from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)
from jarvis.storage.repositories.diary import (
    DiaryRepository,
)
from jarvis.context import (
    ContextCompiler,
    ContextRequest,
    ContextWindowManager,
)

from jarvis.recall.service import RecallService

from jarvis.memory import (
    CoreMemoryService,
)
from jarvis.diary.service import (
    DiaryService,
)
from jarvis.memory.long_term import (
    LongTermMemoryService,
)

from jarvis.knowledge import (
    KnowledgeService,
)

from jarvis.relationships.store import (
    RelationshipStore,
)

from jarvis.retrieval import (
    KnowledgeProvider,
    MemoryProvider,
    RecallProvider,
    RelationshipProvider,
    RetrievalService,
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

        # --------------------------------------------------
        # Database
        # --------------------------------------------------

        database.initialize()

        # --------------------------------------------------
        # LLM
        # --------------------------------------------------

        self.llm = LLMClient()

        self.enabled = True

        # --------------------------------------------------
        # State
        # --------------------------------------------------

        self.state_repository = (
            AgentStateRepository(
                database
            )
        )

        # --------------------------------------------------
        # Recall
        # --------------------------------------------------

        self.recall = RecallService(
            ConversationRepository(
                database
            )
        )

        # --------------------------------------------------
        # Agent State
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        if self.state.conversation_id is None:

            self.state.conversation_id = (
                self.recall.create_conversation()
            )

            self.state_repository.save(
                self.state
            )

        # --------------------------------------------------
        # Core Memory
        # --------------------------------------------------

        self.core_memory = (
            CoreMemoryService(
                CoreMemoryRepository(
                    database
                ),
                agent_id=self.AGENT_ID,
            )
        )

        self.core_memory.ensure_default_blocks()


        # --------------------------------------------------
        # Long-Term Memory
        # --------------------------------------------------

        self.memory = (
            LongTermMemoryService(
                LongTermMemoryRepository(
                    database
                ),
                agent_id=self.AGENT_ID,
            )
        )

        # --------------------------------------------------
        # Knowledge
        # --------------------------------------------------

        self.knowledge = (
            KnowledgeService(
                KnowledgeRepository(
                    database
                )
            )
        )
        # --------------------------------------------------
        # Diary
        # --------------------------------------------------

        self.diary = (
            DiaryService(
                DiaryRepository(
                    database
                ),
                agent_id=self.AGENT_ID,
            )
        )

        self.retrieval = RetrievalService(
            providers=[
                RecallProvider(
                    recall_service=self.recall,
                    conversation_id=(
                        self.state.conversation_id
                    ),
                ),
                MemoryProvider(
                    memory_service=self.memory,
                ),
                RelationshipProvider(
                    relationship_store=(
                        self.relationships
                    ),
                ),
                KnowledgeProvider(
                    knowledge_service=(
                        self.knowledge
                    ),
                ),
            ]
        )
        # --------------------------------------------------
        # Relationships
        # --------------------------------------------------

        self.relationships = (
            RelationshipStore()
        )

        # --------------------------------------------------
        # Unified Retrieval
        #
        # R2.4G:
        #
        # Recall
        # Memory
        # Relationship
        # Knowledge
        #
        # all participate in the same RetrievalService.
        # --------------------------------------------------

        self.retrieval = RetrievalService(
            providers=[
                RecallProvider(
                    recall_service=self.recall,
                    conversation_id=(
                        self.state.conversation_id
                    ),
                ),
                MemoryProvider(
                    memory_service=self.memory,
                ),
                RelationshipProvider(
                    relationship_store=(
                        self.relationships
                    ),
                ),
                KnowledgeProvider(
                    knowledge_service=(
                        self.knowledge
                    ),
                ),
            ]
        )

        # --------------------------------------------------
        # Context
        # --------------------------------------------------

        self.context_compiler = (
            ContextCompiler(
                system_prompt=SYSTEM_PROMPT
            )
        )

        self.context_window = (
            ContextWindowManager()
        )

        # --------------------------------------------------
        # In-memory conversation representation
        # --------------------------------------------------

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

    # ======================================================
    # CONTEXT
    # ======================================================
    def _build_context(
        self,
        user_input: str = "",
    ):
        """
        Compile the temporary context for the current
        reasoning step.

        Context receives:

        - current Agent State,
        - Core Memory,
        - conversation history,
        - unified Retrieval results,
        - relevant Diary events.

        Retrieval remains automatic at the Agent boundary.
        Agent-controlled retrieval belongs to the later
        Agent ↔ Information ↔ Capability reasoning loop.
        """

        retrieval_results = []

        if user_input.strip():
            retrieval_results = (
                self.retrieval.search(
                    user_input,
                    limit=10,
                )
            )

        diary_results = []

        if user_input.strip():
            diary_results = (
                self.diary.search(
                    user_input,
                    conversation_id=(
                        self.state.conversation_id
                    ),
                    limit=10,
                )
            )

        else:
            diary_results = (
                self.diary.recent(
                    conversation_id=(
                        self.state.conversation_id
                    ),
                    limit=10,
                )
            )

        request = ContextRequest(
            user_input=user_input,
            state=self.state,
            conversation=list(
                self.messages
            ),
            core_memory=(
                self.core_memory.list_blocks()
            ),
            diary=diary_results,
            retrieval_results=(
                retrieval_results
            ),
            operation_results=[],
        )

        compiled = (
            self.context_compiler.compile(
                request
            )
        )

        return self.context_window.prepare(
            compiled
        )
    # ======================================================
    # RUN
    # ======================================================

    def run(
        self,
        user_input: str,
    ) -> str:

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

        context = self._build_context(
             user_input=user_input
        )

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

            for call in (
                response.message.tool_calls
            ):

                name = call.function.name

                args = dict(
                    call.function.arguments
                )

                function = (
                    AVAILABLE_TOOLS.get(
                        name
                    )
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

    # ======================================================
    # STATE
    # ======================================================

    def _persist_state(self) -> None:
        """
        Persist the current Agent State.
        """

        self.state_repository.save(
            self.state
        )

    # ======================================================
    # ENABLE / DISABLE
    # ======================================================

    def toggle(self) -> bool:

        self.enabled = (
            not self.enabled
        )

        return self.enabled