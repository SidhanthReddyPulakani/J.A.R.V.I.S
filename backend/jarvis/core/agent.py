from ollama import ResponseError

from jarvis.core.llm import LLMClient
from jarvis.core.tools import AVAILABLE_TOOLS

from jarvis.storage.database import database

from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)


from jarvis.memory.operation_results import (
    OperationResult,
    OperationErrorCode,
    OperationStatus,
    classify_operation_exception,
)

from jarvis.memory.operations import (
    AgentMemoryOperations,
)

from jarvis.memory.operation_definitions import (
    get_memory_operation_definitions,
)

from jarvis.state import (
    AgentState,
)
from jarvis.memory.formation import (
    MemoryCandidateExtractor,
    MemoryFormationService,
    MemorySource,
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

from jarvis.memory.service import (
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

from jarvis.retrieval.container import (
    build_retrieval_service,
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
        # Memory Formation
        #
        # Converts eligible experience into Long-Term
        # Memory through the existing:
        #
        # Extractor → Formation Service
        #
        # The Formation Service owns evaluation and
        # persistence.
        # --------------------------------------------------

        self.memory_extractor = (
            MemoryCandidateExtractor()
        )

        self.memory_formation = (
            MemoryFormationService(
                memory_service=self.memory,
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

        # --------------------------------------------------
        # Relationships
        # --------------------------------------------------
        #
        # Must be created before any RetrievalProvider
        # references it.
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
        # all participate in one RetrievalService.
        # --------------------------------------------------

        self.retrieval = build_retrieval_service(
            recall_service=self.recall,
            memory_service=self.memory,
            relationship_store=self.relationships,
            knowledge_service=self.knowledge,
            conversation_id=self.state.conversation_id,
        )
        # --------------------------------------------------
        # Agent Memory Operations
        #
        # This is the LLM-callable information-operation
        # surface. It uses the existing memory, Recall,
        # Knowledge, and Retrieval services rather than
        # accessing repositories directly.
        # --------------------------------------------------

        self.memory_operations = (
            AgentMemoryOperations(
                core_memory=self.core_memory,
                long_term_memory=self.memory,
                recall=self.recall,
                knowledge=self.knowledge,
                retrieval=self.retrieval,
                conversation_id=(
                    self.state.conversation_id
                ),
            )
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
        #
        # Recall remains the persistence source.
        # self.messages is the Agent's current runtime
        # representation used by the existing reasoning path.
        # --------------------------------------------------
        self.operation_results = []

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
    def _form_memories(
        self,
        user_input: str,
    ) -> None:
        """
        Run the current user experience through the
        Long-Term Memory formation pipeline.

        Pipeline:

            user input
                ↓
            candidate extraction
                ↓
            memory formation
                ↓
            evaluate
                ↓
            create / update / discard

        MemoryFormationService owns evaluation and
        persistence. This method only coordinates the
        Agent-level integration.
        """

        candidates = (
            self.memory_extractor.extract(
                text=user_input,
                source=MemorySource.USER,
            )
        )

        for candidate in candidates:

            self.memory_formation.form(
                candidate
            )
    def _get_llm_tools(self) -> list[dict]:
        """
        Return all tools available to the LLM.

        This combines the existing executable tools with
        the Agent-managed information operations.

        The two surfaces remain separate internally:

        - AVAILABLE_TOOLS contains normal application tools.
        - memory operation definitions describe operations
          executed through AgentMemoryOperations.

        Both are presented to the LLM using the same
        model-compatible function-definition format.
        """

        return (
            list(
                AVAILABLE_TOOLS.values()
            )
            + get_memory_operation_definitions()
        )
    
    def _execute_memory_operation(
        self,
        name: str,
        args: dict,
    ) -> OperationResult:
        """
        Execute one LLM-requested Agent Memory Operation.

        The operation definitions describe the public LLM
        surface, while AgentMemoryOperations owns validation
        and service-level execution.

        Every outcome is converted into an OperationResult
        so the result can enter the normal Agent Context
        pipeline.
        """

        handlers = {
            "memory_read_core": (
                self.memory_operations.read_core_memory
            ),
            "memory_list_core": (
                self.memory_operations.list_core_memory
            ),
            "memory_replace_core": (
                self.memory_operations.replace_core_memory
            ),
            "memory_append_core": (
                self.memory_operations.append_core_memory
            ),
            "memory_create": (
                self.memory_operations.create_memory
            ),
            "memory_get": (
                self.memory_operations.get_memory
            ),
            "memory_list": (
                self.memory_operations.list_memories
            ),
            "memory_delete": (
                self.memory_operations.delete_memory
            ),
            "recall_search": (
                self.memory_operations.search_recall
            ),
            "knowledge_search": (
                self.memory_operations.search_knowledge
            ),
            "memory_search": (
                self.memory_operations.search_memory
            ),
        }

        handler = handlers.get(
            name
        )

        if handler is None:

            return (
                OperationResult.failure_result(
                    operation=name,
                    error_code=(
                        OperationErrorCode.NOT_FOUND
                    ),
                    error_message=(
                        f"Unknown memory operation: {name}"
                    ),
                )
            )

        try:

            result = handler(
                **args
            )

            return (
                OperationResult.success_result(
                    operation=name,
                    data=result,
                )
            )

        except Exception as exc:

            return (
                OperationResult.failure_result(
                    operation=name,
                    error_code=(
                        classify_operation_exception(
                            exc
                        )
                    ),
                    error_message=str(
                        exc
                    ),
                )
            )
    def _build_context(
        self,
        user_input: str = "",
        operation_results=None,
    ):
        """
        Build the complete temporary Context for one
        Agent reasoning step.

        This is the single authoritative context-assembly
        operation.

        Information is collected through Agent-owned
        services/providers and passed into ContextRequest.

        Context itself never accesses persistence.

        Assembly order:

        1. Current input
        2. Current Agent State
        3. Core Memory
        4. Current conversation
        5. Relevant unified Retrieval results
        6. Relevant Diary events
        7. Operation results

        Retrieval remains a unified boundary for:
        Recall, Long-Term Memory, Knowledge, and Relationships.

        P5.5:
            Retrieved information is bounded by the
            configured retrieval token budget before
            Context compilation.

        P5.6:
            Context eviction remains temporary. No persistent
            information is deleted by this method.
        """

        # --------------------------------------------------
        # Current query-dependent information
        # --------------------------------------------------

        if user_input.strip():

            retrieval_results = (
                self.retrieval.search(
                    user_input,
                    limit=10,
                )
            )

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

            retrieval_results = []

            diary_results = (
                self.diary.recent(
                    conversation_id=(
                        self.state.conversation_id
                    ),
                    limit=10,
                )
            )

        # --------------------------------------------------
        # P5.5 — Retrieval token budget
        #
        # RetrievalService already returns globally ranked
        # results. ContextWindowManager only decides how much
        # of that ranked information can enter this context.
        # --------------------------------------------------

        retrieval_results = (
            self.context_window.fit_retrieval_budget(
                retrieval_results
            )
        )

        # --------------------------------------------------
        # Assemble the Context request
        # --------------------------------------------------

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
            operation_results=(
                list(
                    getattr(
                        self,
                        "operation_results",
                        [],
                    )
                    if operation_results is None
                    else operation_results
                )
            ),
        )

        # --------------------------------------------------
        # Compile
        # --------------------------------------------------

        compiled = (
            self.context_compiler.compile(
                request
            )
        )

        # --------------------------------------------------
        # Apply the total Context Window boundary.
        #
        # P5.4 token-aware eviction occurs here.
        # P5.6 guarantees that this only changes the
        # temporary context representation.
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Initial context
        #
        # Retrieval happens before persisting the current
        # user message so Recall cannot retrieve the
        # message currently being processed.
        # --------------------------------------------------

        context = self._build_context(
            user_input=user_input
        )

        # --------------------------------------------------
        # Persist current user message after initial
        # retrieval has been performed.
        # --------------------------------------------------

        self.recall.add_message(
            self.state.conversation_id,
            "user",
            user_input,
        )

        # --------------------------------------------------
        # Long-Term Memory Formation
        # --------------------------------------------------

        self._form_memories(
            user_input
        )

        # --------------------------------------------------
        # Reset ephemeral operation results for this turn.
        # --------------------------------------------------

        self.operation_results = []

        # --------------------------------------------------
        # Reasoning step 1
        # --------------------------------------------------

        response = self.llm.chat(
            messages=context.as_messages(),
            tools=self._get_llm_tools(),
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
            # Diary
            # --------------------------------------------------

            self.diary.record(
                event_type="conversation_turn",
                description=(
                    "Completed conversation turn. "
                    f"User: {user_input} "
                    f"Jarvis: "
                    f"{response.message.content or ''}"
                ),
                conversation_id=(
                    self.state.conversation_id
                ),
                source="agent",
            )

            self._persist_state()

            return (
                response.message.content
                or "I'm ready."
            )

        # --------------------------------------------------
        # Tool / Agent Memory Operation execution
        # --------------------------------------------------

        for call in (
            response.message.tool_calls
        ):

            name = call.function.name

            args = dict(
                call.function.arguments
            )

            # --------------------------------------------------
            # Agent Memory Operation
            # --------------------------------------------------

            if name in {
                "memory_read_core",
                "memory_list_core",
                "memory_replace_core",
                "memory_append_core",
                "memory_create",
                "memory_get",
                "memory_list",
                "memory_delete",
                "recall_search",
                "knowledge_search",
                "memory_search",
            }:

                operation_result = (
                    self._execute_memory_operation(
                        name=name,
                        args=args,
                    )
                )

                self.operation_results.append(
                    operation_result
                )

                # Keep a normal tool-role message so the
                # existing LLM conversation protocol remains
                # intact.
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": (
                            str(
                                operation_result.data
                            )
                            if operation_result.status
                            == OperationStatus.SUCCESS
                            else (
                                operation_result.error_message
                                or "Operation failed."
                            )
                        ),
                    }
                )

                continue

            # --------------------------------------------------
            # Existing application tool
            # --------------------------------------------------

            function = (
                AVAILABLE_TOOLS.get(
                    name
                )
            )

            if function is None:

                result = (
                    f"Unknown tool: {name}"
                )

                operation_result = (
                    OperationResult.failure_result(
                        operation=name,
                        error_code=(
                            OperationErrorCode.NOT_FOUND
                        ),
                        error_message=result,
                    )
                )

            else:

                try:

                    result = function(
                        **args
                    )

                    operation_result = (
                        OperationResult.success_result(
                            operation=name,
                            data=result,
                        )
                    )

                    result = str(
                        result
                    )

                except Exception as exc:

                    error_code = (
                        classify_operation_exception(
                            exc
                        )
                    )

                    result = (
                        "Tool execution failed: "
                        f"{exc}"
                    )

                    operation_result = (
                        OperationResult.failure_result(
                            operation=name,
                            error_code=error_code,
                            error_message=str(
                                exc
                            ),
                        )
                    )

            self.operation_results.append(
                operation_result
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
        # The newly created OperationResults are now part
        # of the Agent-owned Context.
        # --------------------------------------------------

        context = self._build_context()

        final = self.llm.chat(
            messages=context.as_messages(),
            tools=self._get_llm_tools(),
        )

        self.messages.append(
            final.message
        )

        self.recall.add_message(
            self.state.conversation_id,
            "assistant",
            final.message.content or "",
        )

        # --------------------------------------------------
        # Diary
        # --------------------------------------------------

        self.diary.record(
            event_type="conversation_turn",
            description=(
                "Completed conversation turn. "
                f"User: {user_input} "
                f"Jarvis: "
                f"{final.message.content or ''}"
            ),
            conversation_id=(
                self.state.conversation_id
            ),
            source="agent",
        )

        self._persist_state()

        return (
            final.message.content
            or "Done."
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