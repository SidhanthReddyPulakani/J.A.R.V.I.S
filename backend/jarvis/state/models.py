"""
Jarvis Agent State models.

Agent State represents what is currently true about Jarvis.
It is separate from memory, recall/history, diary, and
capability-specific state.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentState:
    """
    Persistent runtime state for the Jarvis agent.

    State represents the agent's current situation.
    It does not represent long-term memory or historical events.
    """

    agent_id: str = "jarvis"

    conversation_id: int | None = None

    current_task: str | None = None
    current_goal: str | None = None

    mode: str = "idle"

    active_project: str | None = None

    active_operation: str | None = None
    operation_status: str = "idle"

    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = _utc_now()

    def touch(self) -> None:
        """Update the state's modification timestamp."""
        self.updated_at = _utc_now()

    def set_task(self, task: str | None) -> None:
        self.current_task = task
        self.touch()

    def set_goal(self, goal: str | None) -> None:
        self.current_goal = goal
        self.touch()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.touch()

    def set_active_project(
        self,
        project: str | None,
    ) -> None:
        self.active_project = project
        self.touch()

    def set_operation(
        self,
        operation: str | None,
        status: str = "idle",
    ) -> None:
        self.active_operation = operation
        self.operation_status = status
        self.touch()

    def clear_operation(self) -> None:
        self.active_operation = None
        self.operation_status = "idle"
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the state."""
        return {
            "agent_id": self.agent_id,
            "conversation_id": self.conversation_id,
            "current_task": self.current_task,
            "current_goal": self.current_goal,
            "mode": self.mode,
            "active_project": self.active_project,
            "active_operation": self.active_operation,
            "operation_status": self.operation_status,
            "updated_at": self.updated_at,
        }