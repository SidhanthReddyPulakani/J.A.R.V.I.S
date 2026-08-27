"""
Repository for persistent Agent State.
"""

from jarvis.state.models import AgentState
from jarvis.storage.repositories.base import BaseRepository


class AgentStateRepository(BaseRepository):
    """
    Persists and retrieves the current AgentState.

    The repository owns database interaction.
    AgentState itself remains storage-agnostic.
    """

    def get(self, agent_id: str = "jarvis") -> AgentState | None:
        row = self.database.fetch_one(
            """
            SELECT
                agent_id,
                conversation_id,
                current_task,
                current_goal,
                mode,
                active_project,
                active_operation,
                operation_status,
                updated_at
            FROM agent_state
            WHERE agent_id = ?
            """,
            (agent_id,),
        )

        if row is None:
            return None

        return AgentState(
            agent_id=row[0],
            conversation_id=row[1],
            current_task=row[2],
            current_goal=row[3],
            mode=row[4],
            active_project=row[5],
            active_operation=row[6],
            operation_status=row[7],
            updated_at=row[8],
        )

    def save(self, state: AgentState) -> None:
        state.touch()

        self.database.execute(
            """
            INSERT INTO agent_state (
                agent_id,
                conversation_id,
                current_task,
                current_goal,
                mode,
                active_project,
                active_operation,
                operation_status,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(agent_id)
            DO UPDATE SET
                conversation_id = excluded.conversation_id,
                current_task = excluded.current_task,
                current_goal = excluded.current_goal,
                mode = excluded.mode,
                active_project = excluded.active_project,
                active_operation = excluded.active_operation,
                operation_status = excluded.operation_status,
                updated_at = excluded.updated_at
            """,
            (
                state.agent_id,
                state.conversation_id,
                state.current_task,
                state.current_goal,
                state.mode,
                state.active_project,
                state.active_operation,
                state.operation_status,
                state.updated_at,
            ),
        )

    def delete(self, agent_id: str = "jarvis") -> None:
        self.database.execute(
            """
            DELETE FROM agent_state
            WHERE agent_id = ?
            """,
            (agent_id,),
        )