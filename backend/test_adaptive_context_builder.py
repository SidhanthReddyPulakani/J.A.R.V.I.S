
from types import SimpleNamespace

from jarvis.computation import (
    ComputationMode,
    ComputationState,
    DemandSignal,
    DemandSignalStatus,
    DemandSignals,
)
from jarvis.context import (
    ContextCompiler,
    ContextDemandPolicy,
    ContextWindowManager,
)
from jarvis.context.selector import AdaptiveContextBuilder
from jarvis.core.agent import JarvisAgent
from jarvis.retrieval.models import RetrievalResult


class FakeRetrieval:
    def search(self, query, limit=10):
        return [
            RetrievalResult(
                source="retrieval",
                identifier="test-1",
                content="retrieved information",
                score=0.95,
            )
        ]


class FakeDiary:
    def search(self, query, conversation_id, limit=10):
        return [
            {
                "content": "diary information",
            }
        ]

    def recent(self, conversation_id, limit=10):
        return [
            {
                "content": "recent diary information",
            }
        ]


class FakeCoreMemory:
    def list_blocks(self):
        return [
            {
                "label": "test",
                "value": "core memory information",
            }
        ]


def build_agent():
    """
    Construct the real JarvisAgent object without running its
    infrastructure-heavy constructor.

    The production _build_context() method and all real Context
    components are used. Only external persistence/retrieval
    dependencies are replaced with deterministic test doubles.
    """

    agent = JarvisAgent.__new__(JarvisAgent)

    agent.state = SimpleNamespace(
        agent_id="jarvis",
        conversation_id=1,
        current_task=None,
        current_goal=None,
        mode="idle",
        active_project=None,
        active_operation=None,
        operation_status="idle",
    )

    agent.messages = [
        {
            "role": "user",
            "content": "previous message",
        }
    ]

    agent.operation_results = []

    agent.retrieval = FakeRetrieval()
    agent.diary = FakeDiary()
    agent.core_memory = FakeCoreMemory()

    # REAL production context components.
    agent.context_compiler = ContextCompiler(
        system_prompt="Test system prompt"
    )

    agent.context_window = ContextWindowManager()

    agent.context_policy = ContextDemandPolicy()

    agent.context_builder = AdaptiveContextBuilder(
        compiler=agent.context_compiler,
        window_manager=agent.context_window,
    )

    return agent


def test_jarvis_agent_build_context_uses_real_adaptive_pipeline():
    """
    Exercise the real JarvisAgent._build_context() path.

    The call must pass through:

        JarvisAgent
            -> ContextDemandPolicy
            -> AdaptiveContextBuilder
            -> ContextSelector
            -> ContextCompiler
            -> ContextWindowManager
    """

    agent = build_agent()

    state = ComputationState()
    state.mode = ComputationMode.FAST

    context = agent._build_context(
        computation_state=state,
        demand_signals=DemandSignals(),
        user_input="hello jarvis",
    )

    assert context is not None

    messages = context.as_messages()

    assert messages

    system_message = messages[0]

    assert system_message["role"] == "system"
    assert "Agent ID: jarvis" in system_message["content"]


def test_jarvis_agent_changes_context_depth_with_demand():
    """
    Verify that the real JarvisAgent runtime changes its selected
    context profile when contextual demand changes.
    """

    agent = build_agent()

    state = ComputationState()
    state.mode = ComputationMode.NORMAL

    low_demand = DemandSignals()

    low_context = agent._build_context(
        computation_state=state,
        demand_signals=low_demand,
        user_input="hello jarvis",
    )

    high_demand = DemandSignals(
        missing_information=DemandSignal(
            name="missing_information",
            value=0.9,
            status=DemandSignalStatus.AVAILABLE,
        )
    )

    expanded_context = agent._build_context(
        computation_state=state,
        demand_signals=high_demand,
        user_input="I need more information",
    )

    assert low_context is not None
    assert expanded_context is not None

    low_text = str(
        low_context.as_messages()
    )

    expanded_text = str(
        expanded_context.as_messages()
    )

    # Diary is excluded from minimal demand but available to
    # expanded demand.
    assert "diary information" not in low_text
    assert "diary information" in expanded_text


def test_jarvis_agent_preserves_required_state_across_profiles():
    """
    Current Agent State is REQUIRED by every ContextDemandProfile.

    Therefore adaptive context selection must preserve it for
    FAST, NORMAL, and DEEP computation modes.
    """

    agent = build_agent()

    for mode in (
        ComputationMode.FAST,
        ComputationMode.NORMAL,
        ComputationMode.DEEP,
    ):
        state = ComputationState()
        state.mode = mode

        context = agent._build_context(
            computation_state=state,
            demand_signals=DemandSignals(),
            user_input="test",
        )

        messages = context.as_messages()

        assert messages
        assert messages[0]["role"] == "system"
        assert "Agent ID: jarvis" in messages[0]["content"]


def test_jarvis_agent_context_window_is_applied_after_adaptive_selection():
    """
    Verify that the real AdaptiveContextBuilder completes the
    context-window stage after adaptive selection and compilation.
    """

    agent = build_agent()

    state = ComputationState()
    state.mode = ComputationMode.NORMAL

    context = agent._build_context(
        computation_state=state,
        demand_signals=DemandSignals(),
        user_input="test context window",
    )

    assert context is not None

    messages = context.as_messages()

    assert isinstance(messages, list)

    estimated_tokens = (
        agent.context_window.estimate_context_tokens(
            context
        )
    )

    assert estimated_tokens <= (
        agent.context_window.get_budget()
    )
