from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
)

from widgets.message import MessageLabel


class ConversationSlot(QFrame):

    def __init__(self):
        super().__init__()

        self.setFrameShape(
            QFrame.NoFrame
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum
        )

        self.layout = QVBoxLayout(
            self
        )

        self.layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        self.layout.setSpacing(
            0
        )

        # --------------------------------------------------
        # User query
        # --------------------------------------------------

        self.query = MessageLabel(
            "",
            is_user=True
        )

        self.query.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )

        # --------------------------------------------------
        # Jarvis response
        # --------------------------------------------------

        self.response = MessageLabel(
            "",
            is_user=False
        )

        self.response.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )

        self.layout.addWidget(
            self.query
        )

        self.layout.addWidget(
            self.response
        )

    # ======================================================
    # CONTENT
    # ======================================================

    def set_content(
        self,
        query,
        response,
        opacity
    ):

        self.query.setText(
            query
        )

        self.response.setText(
            response
        )

        alpha = int(
            opacity * 255
        )

        # --------------------------------------------------
        # Query styling
        # --------------------------------------------------

        self.query.setStyleSheet(
            f"""
            QLabel {{
                color: rgba(
                    245,
                    248,
                    255,
                    {alpha}
                );
                background: transparent;
                padding: 2px 16px;
            }}
            """
        )

        # --------------------------------------------------
        # Response styling
        # --------------------------------------------------

        self.response.setStyleSheet(
            f"""
            QLabel {{
                color: rgba(
                    245,
                    248,
                    255,
                    {alpha}
                );
                background: transparent;
                padding: 2px 16px;
            }}
            """
        )

        # Let the labels calculate their actual
        # content dimensions.
        self.query.adjustSize()
        self.response.adjustSize()

        self.updateGeometry()


class ConversationStack(QWidget):

    MAX_SLOTS = 5

    OPACITIES = [
        0.20,
        0.35,
        0.55,
        0.75,
        1.00,
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum
        )

        self.conversations = []

        # --------------------------------------------------
        # Main layout
        # --------------------------------------------------

        self.layout = QVBoxLayout(
            self
        )

        self.layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        self.layout.setSpacing(
            0
        )

        # --------------------------------------------------
        # Create five reusable slots
        # --------------------------------------------------

        self.slots = []

        for _ in range(
            self.MAX_SLOTS
        ):

            slot = ConversationSlot()

            self.slots.append(
                slot
            )

            self.layout.addWidget(
                slot
            )

        self.refresh()

    # ======================================================
    # ADD CONVERSATION
    # ======================================================

    def add_conversation(
        self,
        query,
        response
    ):

        self.conversations.append(
            {
                "query": query,
                "response": response,
            }
        )

        # Keep only the newest five.
        if len(
            self.conversations
        ) > self.MAX_SLOTS:

            self.conversations.pop(
                0
            )

        self.refresh()

    # ======================================================
    # REFRESH
    # ======================================================

    def refresh(self):

        # --------------------------------------------------
        # Hide and clear all slots
        # --------------------------------------------------

        for slot in self.slots:

            slot.setVisible(
                False
            )

            slot.set_content(
                "",
                "",
                0
            )

        # --------------------------------------------------
        # Position conversations into the five slots
        # --------------------------------------------------

        count = len(
            self.conversations
        )

        first_slot = (
            self.MAX_SLOTS - count
        )

        for (
            queue_index,
            conversation
        ) in enumerate(
            self.conversations
        ):

            slot_index = (
                first_slot
                + queue_index
            )

            slot = self.slots[
                slot_index
            ]

            slot.set_content(
                conversation["query"],
                conversation["response"],
                self.OPACITIES[
                    slot_index
                ]
            )

            slot.setVisible(
                True
            )

        # --------------------------------------------------
        # Recalculate actual content height
        # --------------------------------------------------

        self.adjustSize()
        self.updateGeometry()