from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
)

from widgets.message import MessageLabel


class OverlayConversationSlot(QFrame):

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
        response
    ):

        self.query.setText(
            query
        )

        self.response.setText(
            response
        )

        # No fading.
        # Everything currently visible has the same opacity.

        self.query.setStyleSheet(
            """
            QLabel {
                color: rgba(
                    245,
                    248,
                    255,
                    255
                );

                background: transparent;

                padding: 2px 16px;
            }
            """
        )

        self.response.setStyleSheet(
            """
            QLabel {
                color: rgba(
                    245,
                    248,
                    255,
                    255
                );

                background: transparent;

                padding: 2px 16px;
            }
            """
        )

        self.query.adjustSize()
        self.response.adjustSize()

        self.layout.activate()

        self.adjustSize()

        self.updateGeometry()


class OverlayConversation(QWidget):

    def __init__(
        self,
        parent=None
    ):
        super().__init__(
            parent
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # --------------------------------------------------
        # Complete conversation history
        #
        # There is deliberately NO maximum here.
        # --------------------------------------------------

        self.conversations = []

        # --------------------------------------------------
        # Layout
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

        # Important:
        # Conversations are anchored to the bottom.
        self.layout.addStretch(
            1
        )

        self.slots = []

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

        self.refresh()

    # ======================================================
    # REFRESH
    # ======================================================

    def refresh(self):

        # --------------------------------------------------
        # Remove old widgets
        # --------------------------------------------------

        for slot in self.slots:

            self.layout.removeWidget(
                slot
            )

            slot.deleteLater()

        self.slots.clear()

        # --------------------------------------------------
        # Available height
        # --------------------------------------------------

        available_height = self.height()

        if available_height <= 0:
            return

        # --------------------------------------------------
        # Build from NEWEST → OLDEST.
        #
        # This is the important part.
        #
        # We keep adding messages upward until the
        # available viewport is full.
        # --------------------------------------------------

        visible = []

        used_height = 0

        for conversation in reversed(
            self.conversations
        ):

            slot = OverlayConversationSlot()

            slot.set_content(
                conversation["query"],
                conversation["response"]
            )

            slot.adjustSize()

            height = slot.sizeHint().height()

            # If this conversation would exceed the
            # available viewport, discard it.
            if (
                used_height + height
                > available_height
            ):

                slot.deleteLater()

                break

            visible.append(
                (
                    slot,
                    height
                )
            )

            used_height += height

        # --------------------------------------------------
        # Put them back in chronological order.
        # --------------------------------------------------

        visible.reverse()

        # The first item in the layout is the stretch.
        # Remove it temporarily.
        stretch_item = self.layout.takeAt(0)

        for slot, _ in visible:

            self.layout.addWidget(
                slot
            )

            self.slots.append(
                slot
            )

        # Stretch goes BEFORE the conversations.
        self.layout.insertStretch(
            0,
            1
        )

        # --------------------------------------------------
        # Clean up the old stretch item if necessary.
        # --------------------------------------------------

        if stretch_item is not None:
            del stretch_item

        self.update()