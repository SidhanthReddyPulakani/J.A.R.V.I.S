from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel


class MessageLabel(QLabel):

    def __init__(self, text="", is_user=False, opacity=1.0):
        super().__init__(text)

        self.setWordWrap(True)

        if is_user:
            self.setAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        else:
            self.setAlignment(
                Qt.AlignLeft | Qt.AlignVCenter
            )

        font = QFont("Segoe UI")
        font.setPointSize(13)
        self.setFont(font)

        self.setStyleSheet(
            f"""
            QLabel {{
                color: rgba(245, 248, 255, {int(opacity * 255)});
                background: transparent;
                padding: 6px 16px;
            }}
            """
        )