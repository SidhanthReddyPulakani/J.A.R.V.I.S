from ollama import ResponseError

from jarvis.core.llm import LLMClient
from jarvis.core.tools import AVAILABLE_TOOLS

from jarvis.storage.database import database

from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)

import time

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
from jarvis.core.agent_turn import (
    AgentToolCall,
    AgentTurnResult,
)
from jarvis.core.capability_request import (
    CapabilityRequest,
)
from jarvis.capabilities.registry import (
    CapabilityRegistry,
)
from jarvis.capabilities.controller import (
    CapabilityController,
)
from jarvis.capabilities.bootstrap import (
    build_default_registry,
)
from jarvis.core.agent_trace import (
    AgentExecutionTrace,
    AgentTraceStep,
    AgentTerminationReason,
)
from jarvis.core.agent_observation import (
    AgentOperationObservation,
)

from jarvis.computation import (
    ComputationController,
    ComputationPhase,
    ComputationState,
    DemandSignal,
    DemandSignalStatus,
    DemandSignals,
)

SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Your priorities:
1. Be concise and conversational.
2. Use tools whenever the user's request requires a desktop action.
3. When the user asks you to open, launch, run, or start an application, use the `apps.launch` tool with the application's name as the `query`.
4. Do not tell the user that you cannot launch desktop applications when an appropriate tool is available.
5. Never claim an action was completed unless the tool result confirms it.
6. If a tool reports failure, use that result to decide what to do next.
7. Do not explain your internal reasoning.
8. For simple commands, respond briefly.
"""


class JarvisAgent:

    AGENT_ID = "jarvis"
    MAX_REASONING_STEPS = 10

    # --------------------------------------------------
    # P8 — the set of operation names handled by the Agent
    # Memory Operation surface (P1) rather than an existing
    # application tool (jarvis.core.tools).
    #
    # This is the same membership test that used to live
    # inline in run() as an `if name in {...}` literal. P8
    # names it so both `_execute_capability_request` and the
    # tool-message formatting logic can share one definition
    # instead of two copies drifting apart.
    #
    # This is still an internal detail of routing between two
    # hand-rolled registries, not a real capability registry.
    # A real, discoverable registry is P11's job.
    # --------------------------------------------------

    MEMORY_OPERATION_NAMES = frozenset(
        {
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
        }
    )

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
            RelationshipStore(database)
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
        # Capabilities (P9-P15)
        #
        # The Capability Registry and Controller are the single
        # governed path for every capability operation (currently:
        # apps.find / apps.resolve / apps.launch). Adding a new
        # capability never touches this constructor — see
        # jarvis.capabilities.bootstrap.build_default_registry.
        #
        # Memory operations (above) remain a separate, intentionally
        # different surface and are not routed through here.
        # --------------------------------------------------

        self.capability_registry = (
            build_default_registry()
        )

        self.capability_controller = (
            CapabilityController(
                self.capability_registry
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

        self.computation_controller = (
            ComputationController()
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
        the Agent-managed information operations, plus every
        operation exposed by a registered Capability.

        The three surfaces remain separate internally:

        - AVAILABLE_TOOLS contains legacy application tools not yet
          migrated behind a Capability.
        - memory operation definitions describe operations
          executed through AgentMemoryOperations.
        - capability_registry.discover() returns every operation
          exposed by a registered Capability (P9-P15) — a new
          Capability shows up here automatically the moment it is
          registered in jarvis.capabilities.bootstrap, with no
          change needed in this method.

        All three are presented to the LLM using the same
        model-compatible function-definition format.
        """

        return (
            list(
                AVAILABLE_TOOLS.values()
            )
            + get_memory_operation_definitions()
            + [
                definition.to_llm_tool_definition()
                for definition in (
                    self.capability_registry.discover()
                )
            ]
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

    def _execute_application_tool(
        self,
        request: CapabilityRequest,
    ) -> OperationResult:
        """
        Execute one existing application tool (jarvis.core.tools)
        and normalize its outcome into an OperationResult.

        This performs exactly the same lookup and execution the
        Agent Execution Loop previously did inline inside run().
        P8 only moves it behind the CapabilityRequest contract so
        there is a single call site instead of a duplicated branch
        living directly in the loop.

        This is packaging, not a rewrite of the Apps subsystem —
        AVAILABLE_TOOLS itself is untouched here. Migrating Apps
        into a real Capability behind the P12 Controller is P13.
        """

        function = (
            AVAILABLE_TOOLS.get(
                request.operation
            )
        )

        if function is None:

            return (
                OperationResult.failure_result(
                    operation=request.operation,
                    error_code=(
                        OperationErrorCode.NOT_FOUND
                    ),
                    error_message=(
                        f"Unknown tool: {request.operation}"
                    ),
                )
            )

        try:

            result = function(
                **request.arguments
            )

            return (
                OperationResult.success_result(
                    operation=request.operation,
                    data=result,
                )
            )

        except Exception as exc:

            return (
                OperationResult.failure_result(
                    operation=request.operation,
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

    def _execute_capability_request(
        self,
        request: CapabilityRequest,
    ) -> OperationResult:
        """
        Execute one normalized CapabilityRequest and return its
        OperationResult.

        This is the single entry point the Agent Execution Loop
        (P7) uses to run a requested operation. Three internal
        surfaces can end up handling it, checked in this order:

        1. The Agent Memory Operation surface (P1) — unchanged,
           still a separate, intentionally different surface.
        2. The Capability Registry/Controller (P9-P15) — anything
           whose address is registered by
           jarvis.capabilities.bootstrap.build_default_registry is
           routed through the real governed gateway,
           `CapabilityController.execute(request)`. Adding a new
           Capability never requires touching this method.
        3. The legacy AVAILABLE_TOOLS registry — the fallback for
           any tool not yet migrated behind a Capability.
        """

        if request.operation in self.MEMORY_OPERATION_NAMES:

            return (
                self._execute_memory_operation(
                    name=request.operation,
                    args=request.arguments,
                )
            )

        if (
            self.capability_registry.resolve_operation(
                request.operation
            )
            is not None
        ):

            return (
                self.capability_controller.execute(
                    request
                )
            )

        return (
            self._execute_application_tool(
                request
            )
        )

    def _build_tool_message_content(
        self,
        request: CapabilityRequest,
        operation_result: OperationResult,
    ) -> str:
        """
        Render one OperationResult into the string content that is
        fed back to the model as a "tool" message.

        On success, this is always the operation's data.

        On failure:

        - A Capability-produced result (P10's OperationState, e.g.
          REQUIRES_INPUT or NOT_FOUND) is shown exactly as the
          Capability reported it — "Found 3 matching applications"
          is not an exception and must never be dressed up as one.
        - A legacy AVAILABLE_TOOLS exception keeps the
          "Tool execution failed: ..." framing the model has always
          seen for that case.
        - Everything else (unknown operation, memory operation
          failure) is shown as the operation's own error message,
          unprefixed.
        """

        if operation_result.status == OperationStatus.SUCCESS:

            return str(
                operation_result.data
            )

        error_message = (
            operation_result.error_message
            or "Operation failed."
        )

        if operation_result.state is not None:

            # A Capability always reports through OperationState —
            # its message is the intended, final wording, not raw
            # exception text to be re-framed.
            return error_message

        is_legacy_tool_exception = (
            request.operation
            not in self.MEMORY_OPERATION_NAMES
            and operation_result.error_code
            != OperationErrorCode.NOT_FOUND
        )

        if is_legacy_tool_exception:

            return (
                "Tool execution failed: "
                f"{error_message}"
            )

        return error_message

    def _run_agent_turn(
        self,
        context,
    ) -> AgentTurnResult:
        """
        Execute exactly one LLM interaction and normalize
        the provider response into the Agent Turn contract.

        This method does not execute tools, mutate memory,
        persist messages, rebuild context, or control the
        reasoning loop.

        Those responsibilities remain with the Agent runtime.

        The method therefore establishes the boundary:

            provider response
                ↓
            AgentTurnResult
        """

        response = self.llm.chat(
            messages=context.as_messages(),
            tools=self._get_llm_tools(),
        )

        message = response.message

        assistant_message = {
            "role": "assistant",
            "content": (
                message.content
                or ""
            ),
        }

        tool_calls = []

        for call in (
            message.tool_calls
            or []
        ):
            tool_calls.append(
                AgentToolCall(
                    id=getattr(
                        call,
                        "id",
                        None,
                    ),
                    name=call.function.name,
                    arguments=dict(
                        call.function.arguments
                    ),
                )
            )

        return AgentTurnResult(
            assistant_message=assistant_message,
            tool_calls=tuple(
                tool_calls
            ),
        )
    
    @staticmethod
    def _strip_thinking(content: str) -> str:
        if not content:
            return ""

        if "</think>" in content:
            return content.split("</think>", 1)[1].strip()

        return content.strip()
    
    def _record_agent_turn(
        self,
        turn: AgentTurnResult,
    ) -> None:
        """
        Record one normalized Agent turn in the runtime
        conversation representation.

        The representation remains provider-independent while
        preserving the model's requested tool calls so that a
        subsequent Context build can reconstruct the complete
        model/tool interaction.

        This method does not execute operations.
        """

        assistant_message = dict(
            turn.assistant_message
        )
        assistant_message["content"] = (
            self._strip_thinking(
                assistant_message.get("content", "")
            )
        )

        if turn.tool_calls:

            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": dict(
                            call.arguments
                        ),
                    },
                }
                for call in turn.tool_calls
            ]

        self.messages.append(
            assistant_message
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

    # ======================================================
    # ADAPTIVE COMPUTATION
    # ======================================================

    @staticmethod
    def _build_initial_computation_signals(
        user_input: str,
    ) -> DemandSignals:
        """
        Build the initial computation-demand snapshot.

        O1 deliberately starts conservatively. The initial
        controller evaluation should use only information
        already available before the first LLM call.

        More sophisticated runtime signals are populated
        after LLM/tool execution.
        """

        return DemandSignals(
            goal_resolution=DemandSignal(
                name="goal_resolution",
                value=False,
                status=DemandSignalStatus.AVAILABLE,
            ),
            unresolved_requirements=DemandSignal(
                name="unresolved_requirements",
                value=True,
                status=DemandSignalStatus.AVAILABLE,
            ),
            reasoning_step=DemandSignal(
                name="reasoning_step",
                value=0,
                status=DemandSignalStatus.AVAILABLE,
            ),
        )

    @staticmethod
    def _build_pre_llm_computation_signals(
        computation_state: ComputationState,
    ) -> DemandSignals:
        """
        Build the computation snapshot immediately before
        an LLM call.
        """

        return DemandSignals(
            reasoning_step=DemandSignal(
                name="reasoning_step",
                value=computation_state.reasoning_step,
                status=DemandSignalStatus.AVAILABLE,
            ),
            elapsed_computation=DemandSignal(
                name="elapsed_computation",
                value=computation_state.elapsed_seconds(),
                status=DemandSignalStatus.AVAILABLE,
            ),
        )

    @staticmethod
    def _build_post_llm_computation_signals(
        computation_state: ComputationState,
        tool_requested: bool,
    ) -> DemandSignals:
        """
        Build the computation snapshot after an LLM response.

        This does not attempt to infer hidden reasoning.
        It only exposes observable Agent-level information.
        """

        return DemandSignals(
            reasoning_step=DemandSignal(
                name="reasoning_step",
                value=computation_state.reasoning_step,
                status=DemandSignalStatus.AVAILABLE,
            ),
            elapsed_computation=DemandSignal(
                name="elapsed_computation",
                value=computation_state.elapsed_seconds(),
                status=DemandSignalStatus.AVAILABLE,
            ),
            unresolved_requirements=DemandSignal(
                name="unresolved_requirements",
                value=tool_requested,
                status=DemandSignalStatus.AVAILABLE,
            ),
        )

    @staticmethod
    def _build_post_execution_computation_signals(
        computation_state: ComputationState,
        operation_result: OperationResult,
    ) -> DemandSignals:
        """
        Build the computation snapshot after capability/tool
        execution.
        """

        failed = (
            operation_result.status
            == OperationStatus.FAILURE
        )

        return DemandSignals(
            tool_execution_status=DemandSignal(
                name="tool_execution_status",
                value=(
                    "failed"
                    if failed
                    else "success"
                ),
                status=DemandSignalStatus.AVAILABLE,
            ),
            tool_failure_count=DemandSignal(
                name="tool_failure_count",
                value=computation_state.tool_failure_count,
                status=DemandSignalStatus.AVAILABLE,
            ),
            reasoning_step=DemandSignal(
                name="reasoning_step",
                value=computation_state.reasoning_step,
                status=DemandSignalStatus.AVAILABLE,
            ),
            elapsed_computation=DemandSignal(
                name="elapsed_computation",
                value=computation_state.elapsed_seconds(),
                status=DemandSignalStatus.AVAILABLE,
            ),
        )

    @staticmethod
    def _update_computation_execution_state(
        computation_state: ComputationState,
        operation_result: OperationResult,
    ) -> None:
        """
        Update transient computation counters from an
        executed operation.
        """

        if (
            operation_result.status
            == OperationStatus.FAILURE
        ):
            computation_state.tool_failure_count += 1

    def _apply_computation_decision(
        self,
        decision,
        computation_state: ComputationState,
    ) -> bool:
        """
        Apply the controller's decision at the Agent boundary.

        Returns True when the Agent must terminate the
        current reasoning run.
        """

        if decision.action.value == "abort":
            computation_state.terminal = True
            computation_state.aborted = True
            return True

        if decision.action.value == "finish":
            computation_state.terminal = True
            return True

        # CONTINUE, ESCALATE, and DEESCALATE are non-terminal.
        #
        # ComputationState.apply_decision() has already updated
        # the active mode when the controller evaluated the
        # decision. The resulting mode therefore governs the
        # next computation cycle.
        return False
    # ======================================================
    # RUN
    # ======================================================
    def run(
        self,
        user_input: str,
        
    ) -> str:
        
        computation_state = ComputationState()

        initial_signals = (
            self._build_initial_computation_signals(
                user_input
            )
        )

        initial_decision = (
            self.computation_controller.initial(
                state=computation_state,
                signals=initial_signals,
            )
        )

        if initial_decision.terminal:
            return
        # --------------------------------------------------
        # Execution trace
        #
        # A new trace is created for every Agent run.
        # The trace contains observable execution events only.
        # It does not contain hidden chain-of-thought.
        # --------------------------------------------------

        self.last_execution_trace = (
            AgentExecutionTrace()
        )

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
        # user message so Recall cannot retrieve the message
        # currently being processed.
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
        # Operation results are ephemeral to this Agent run.
        # --------------------------------------------------

        self.operation_results = []

        # --------------------------------------------------
        # Bounded Agent Execution Loop
        # --------------------------------------------------

        final_text = None

        for step in range(
            self.MAX_REASONING_STEPS
        ):

            computation_state.advance_reasoning_step()

            pre_llm_signals = (
                self._build_pre_llm_computation_signals(
                    computation_state
                )
            )

            pre_llm_decision = (
                self.computation_controller.pre_llm(
                    state=computation_state,
                    signals=pre_llm_signals,
                )
            )

            if self._apply_computation_decision(
                pre_llm_decision,
                computation_state,
            ):
                break
            # --------------------------------------------------
            # Rebuild context after the first reasoning step.
            #
            # The initial context was deliberately assembled
            # before current-turn memory formation.
            # --------------------------------------------------

            if step > 0:

                context = self._build_context()

            # --------------------------------------------------
            # Execute exactly one model turn.
            # --------------------------------------------------

            turn = self._run_agent_turn(
                context
            )
            post_llm_signals = (
                self._build_post_llm_computation_signals(
                    computation_state=computation_state,
                    tool_requested=bool(turn.tool_calls),
                )
            )

            post_llm_decision = (
                self.computation_controller.post_llm(
                    state=computation_state,
                    signals=post_llm_signals,
                )
            )

            if (
                post_llm_decision.action.value
                == "finish"
            ):
                final_text = (
                    turn.assistant_message.get(
                        "content",
                        "",
                    )
                    or "I'm ready."
                )

                self.last_execution_trace.terminate(
                    AgentTerminationReason.MODEL_COMPLETED
                )

                computation_state.terminal = True

                break

            if self._apply_computation_decision(
                post_llm_decision,
                computation_state,
            ):
                break   
            # --------------------------------------------------
            # Preserve the assistant turn, including tool calls.
            # --------------------------------------------------

            self._record_agent_turn(
                turn
            )

            # --------------------------------------------------
            # Create a trace entry for this reasoning step.
            # --------------------------------------------------

            trace_step = AgentTraceStep(
                step=step + 1
            )

            self.last_execution_trace.add_step(
                trace_step
            )

            # --------------------------------------------------
            # Normal termination:
            #
            # The model requested no further operations.
            # --------------------------------------------------

            if turn.completed:

                final_text = (
                    turn.assistant_message.get(
                        "content",
                        ""
                    )
                    or "I'm ready."
                )

                self.last_execution_trace.terminate(
                    AgentTerminationReason.MODEL_COMPLETED
                )

                break

            # --------------------------------------------------
            # Execute every operation requested by this
            # model turn.
            # --------------------------------------------------
            execution_aborted = False
            for call in turn.tool_calls:

                # --------------------------------------------------
                # P8 — normalize the model's raw tool call into the
                # one request shape every operation is executed
                # through, regardless of which internal registry
                # (Agent Memory Operations or existing application
                # tools) ultimately handles it.
                # --------------------------------------------------

                request = (
                    CapabilityRequest.from_tool_call(
                        call,
                        step=step + 1,
                    )
                )

                operation_result = (
                    self._execute_capability_request(
                        request
                    )
                )

                self.operation_results.append(
                    operation_result
                )
                self._update_computation_execution_state(
                    computation_state,
                    operation_result,
                )

                post_execution_signals = (
                    self._build_post_execution_computation_signals(
                        computation_state=computation_state,
                        operation_result=operation_result,
                    )
                )

                post_execution_decision = (
                    self.computation_controller.post_execution(
                        state=computation_state,
                        signals=post_execution_signals,
                    )
                )

                if (
                    post_execution_decision.action.value
                    == "finish"
                ):
                    execution_aborted = True

                    final_text = (
                        turn.assistant_message.get(
                            "content",
                            "",
                        )
                        or "The operation completed successfully."
                    )

                    computation_state.terminal = True

                    self.last_execution_trace.terminate(
                        AgentTerminationReason.MODEL_COMPLETED
                    )

                    break

                if self._apply_computation_decision(
                    post_execution_decision,
                    computation_state,
                ):
                    execution_aborted = True
                    break

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_name": request.operation,
                        "content": (
                            self._build_tool_message_content(
                                request,
                                operation_result,
                            )
                        ),
                    }
                )

                # --------------------------------------------------
                # Record observable operation outcome.
                # --------------------------------------------------

                trace_step.observations.append(
                    AgentOperationObservation(
                        tool_call_id=call.id,
                        operation=request.operation,
                        result=operation_result,
                    )
                )
            if execution_aborted:
                break
        # --------------------------------------------------
        # Safety termination
        #
        # Reaching this point means every permitted reasoning
        # step requested further operations and none produced
        # normal model completion.
        # --------------------------------------------------

        if final_text is None:

            final_text = (
                "I wasn't able to finish reasoning "
                "about that within the allowed number "
                "of steps."
            )

            self.last_execution_trace.terminate(
                AgentTerminationReason.MAX_STEPS_REACHED
            )

        # --------------------------------------------------
        # Persist final conversational response.
        # --------------------------------------------------

        self.recall.add_message(
            self.state.conversation_id,
            "assistant",
            final_text,
        )

        # --------------------------------------------------
        # Diary
        # --------------------------------------------------

        self.diary.record(
            event_type="conversation_turn",
            description=(
                "Completed conversation turn. "
                f"User: {user_input} "
                f"Jarvis: {final_text}"
            ),
            conversation_id=(
                self.state.conversation_id
            ),
            source="agent",
        )

        self._persist_state()

        return final_text


# ======================================================